"""B2 NLP evaluation for Pros & Cons extraction.

Three layers, from strongest to weakest evidence:

1. Gold-label metrics: precision / recall / F1 against human-labeled
   sentences (aspect detection, and aspect + polarity).
2. Automatic sanity checks on the full dataset (no labels needed):
   star-rating consistency, coverage, evidence faithfulness and stability
   under subsampling. Polarity never uses stars, so stars are an independent
   check.
3. Human product-level review: annotators judge the top pros / cons of
   sampled products; scored as precision@k.

Helpers here also export the CSV templates annotators fill in.
"""

from __future__ import annotations

import json

import numpy as np
import pandas as pd

from nlp.pros_cons.aspects import AspectMatcher
from nlp.pros_cons.extract import analyze_clause, summarize_pros_cons, POLARITY_THRESHOLD
from nlp.pros_cons.sentiment import LexiconSentiment
from nlp.pros_cons.text import clean_text, split_clauses, split_sentences

POLARITIES = ("pro", "con")


# ---------------------------------------------------------------------------
# 1. Gold-label metrics
# ---------------------------------------------------------------------------

def parse_gold_labels(value) -> set[tuple[str, str]]:
    """Parse 'leaks:con;cleaning:pro' into {('leaks','con'), ('cleaning','pro')}.

    An empty cell means the sentence has no aspect opinion.
    """
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return set()
    labels = set()
    for part in str(value).split(";"):
        part = part.strip()
        if not part:
            continue
        if ":" not in part:
            raise ValueError(f"Bad gold label '{part}', expected aspect:polarity")
        aspect, polarity = (x.strip().lower() for x in part.split(":", 1))
        if polarity not in POLARITIES:
            raise ValueError(f"Bad polarity in '{part}', expected pro or con")
        labels.add((aspect, polarity))
    return labels


def predict_labels(text: str, scorer=None, matcher=None, threshold=POLARITY_THRESHOLD) -> set[tuple[str, str]]:
    """Run the extractor on one piece of text; return its (aspect, polarity) set."""
    scorer = scorer or LexiconSentiment()
    matcher = matcher or AspectMatcher()
    labels = set()
    for sentence in split_sentences(text):
        for clause in split_clauses(sentence):
            for r in analyze_clause(clause, scorer, matcher, threshold):
                if r["polarity"] in POLARITIES:
                    labels.add((r["aspect"], r["polarity"]))
    return labels


def _prf(tp: int, fp: int, fn: int) -> dict:
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"precision": precision, "recall": recall, "f1": f1, "tp": tp, "fp": fp, "fn": fn}


def evaluate_against_gold(gold: pd.DataFrame, scorer=None, matcher=None) -> dict:
    """Compare predictions with gold labels.

    gold columns: item_id, text, gold_labels.
    Returns micro metrics for aspect detection and aspect+polarity, polarity
    accuracy on correctly detected aspects, a per-aspect table and an error list.
    """
    for col in ("item_id", "text", "gold_labels"):
        if col not in gold.columns:
            raise ValueError(f"gold file is missing column '{col}'")

    scorer = scorer or LexiconSentiment()
    matcher = matcher or AspectMatcher()

    strict = {"tp": 0, "fp": 0, "fn": 0}
    detect = {"tp": 0, "fp": 0, "fn": 0}
    polarity_hits = polarity_total = 0
    per_aspect: dict[str, dict] = {}
    errors = []

    for row in gold.itertuples(index=False):
        truth = parse_gold_labels(row.gold_labels)
        pred = predict_labels(row.text, scorer, matcher)

        # Strict: aspect and polarity must both match.
        strict["tp"] += len(truth & pred)
        strict["fp"] += len(pred - truth)
        strict["fn"] += len(truth - pred)

        # Detection: aspect only.
        truth_aspects = {a for a, _ in truth}
        pred_aspects = {a for a, _ in pred}
        detect["tp"] += len(truth_aspects & pred_aspects)
        detect["fp"] += len(pred_aspects - truth_aspects)
        detect["fn"] += len(truth_aspects - pred_aspects)

        # Polarity accuracy among aspects both sides found.
        for aspect in truth_aspects & pred_aspects:
            polarity_total += 1
            if {p for a, p in truth if a == aspect} == {p for a, p in pred if a == aspect}:
                polarity_hits += 1

        for aspect in truth_aspects | pred_aspects:
            stats = per_aspect.setdefault(aspect, {"tp": 0, "fp": 0, "fn": 0})
            stats["tp"] += len({x for x in truth & pred if x[0] == aspect})
            stats["fp"] += len({x for x in pred - truth if x[0] == aspect})
            stats["fn"] += len({x for x in truth - pred if x[0] == aspect})

        if truth != pred:
            errors.append({
                "item_id": row.item_id,
                "text": row.text,
                "gold": ";".join(sorted(f"{a}:{p}" for a, p in truth)),
                "predicted": ";".join(sorted(f"{a}:{p}" for a, p in pred)),
            })

    aspect_table = pd.DataFrame([
        {"aspect": a, **_prf(s["tp"], s["fp"], s["fn"])} for a, s in sorted(per_aspect.items())
    ])

    return {
        "n_items": int(len(gold)),
        "aspect_polarity": _prf(**strict),
        "aspect_detection": _prf(**detect),
        "polarity_accuracy": polarity_hits / polarity_total if polarity_total else 0.0,
        "per_aspect": aspect_table,
        "errors": pd.DataFrame(errors, columns=["item_id", "text", "gold", "predicted"]),
    }


# ---------------------------------------------------------------------------
# 2. Automatic checks (no labels)
# ---------------------------------------------------------------------------

def star_consistency(mentions: pd.DataFrame) -> dict:
    """Do cons concentrate in low-star reviews and pros in high-star reviews?

    Returns the con share of opinion mentions by star level, the Spearman
    correlation between each review's net opinion and its stars, and the
    share of cons that come from 4-5 star reviews ("hidden cons" that a
    low-star-only approach would miss).
    """
    voted = mentions[mentions["polarity"].isin(POLARITIES)].copy()
    if voted.empty:
        return {"con_share_by_stars": {}, "spearman_net_vs_stars": None, "cons_from_4_5_stars": None}

    voted["is_con"] = (voted["polarity"] == "con").astype(int)
    by_stars = voted.groupby("stars")["is_con"].mean().round(4)

    voted["signed"] = np.where(voted["is_con"] == 1, -1, 1)
    key = "record_key" if "record_key" in voted.columns else "review_id"
    per_review = voted.groupby(key).agg(net=("signed", "mean"), stars=("stars", "first"))
    if per_review["net"].nunique() > 1 and per_review["stars"].nunique() > 1:
        # Spearman = Pearson correlation of ranks.
        rho = per_review["net"].rank().corr(per_review["stars"].rank())
    else:
        rho = None

    cons = voted[voted["is_con"] == 1]
    hidden = float((cons["stars"] >= 4).mean()) if len(cons) else None

    return {
        "con_share_by_stars": {int(k): float(v) for k, v in by_stars.items()},
        "spearman_net_vs_stars": None if rho is None else float(rho),
        "cons_from_4_5_stars": hidden,
    }


def coverage_metrics(mentions: pd.DataFrame, reviews: pd.DataFrame, summary: pd.DataFrame) -> dict:
    """How much of the data produces output?"""
    voted = mentions[mentions["polarity"].isin(POLARITIES)]
    n_reviews = reviews["review_id"].nunique()
    n_products = reviews["asin"].nunique()
    has_pro = set(summary.loc[summary["polarity"] == "pro", "asin"])
    has_con = set(summary.loc[summary["polarity"] == "con", "asin"])
    return {
        "reviews": int(n_reviews),
        "products": int(n_products),
        "reviews_with_opinion": float(voted["review_id"].nunique() / n_reviews) if n_reviews else 0.0,
        "products_with_pros": float(len(has_pro) / n_products) if n_products else 0.0,
        "products_with_cons": float(len(has_con) / n_products) if n_products else 0.0,
        "products_with_both": float(len(has_pro & has_con) / n_products) if n_products else 0.0,
        "aspect_distribution": voted["aspect"].value_counts(normalize=True).round(4).head(10).to_dict(),
    }


def evidence_faithfulness(summary: pd.DataFrame, reviews: pd.DataFrame) -> float:
    """Share of evidence snippets that appear verbatim in their source review.

    Should be 1.0 by construction; a lower value means a bug or a data
    mismatch between the summary and the review table. Sources are cleaned
    the same way as during extraction (curly quotes, HTML breaks).
    """
    texts = dict(zip(reviews["review_id"].astype(str), reviews["text"].astype(str)))
    total = ok = 0
    for evidence in summary["evidence"]:
        for item in json.loads(evidence):
            total += 1
            source = " ".join(clean_text(texts.get(item["review_id"], "")).split())
            snippet = " ".join(item["text"].split())
            ok += int(bool(snippet) and snippet in source)
    return ok / total if total else 1.0


def _top_sets(summary: pd.DataFrame, top_k: int) -> dict:
    top = summary[summary["rank"] <= top_k]
    return {key: set(g["aspect"]) for key, g in top.groupby(["asin", "polarity"])}


def subsample_stability(
    mentions: pd.DataFrame,
    reviews: pd.DataFrame,
    fraction: float = 0.8,
    n_rounds: int = 10,
    top_k: int = 3,
    seed: int = 42,
    **summary_kwargs,
) -> dict:
    """Mean Jaccard similarity of top-k pros / cons between full data and
    random subsamples of each product's reviews. High = robust ranking.
    """
    rng = np.random.default_rng(seed)
    full = _top_sets(summarize_pros_cons(mentions, reviews, top_k=top_k, **summary_kwargs), top_k)
    if not full:
        return {"mean_jaccard": None, "rounds": 0}

    scores = []
    for _ in range(n_rounds):
        keep = reviews.groupby("asin").sample(
            frac=fraction, random_state=int(rng.integers(1_000_000_000))
        )
        sub_mentions = mentions[mentions["review_id"].isin(keep["review_id"])]
        sub = _top_sets(summarize_pros_cons(sub_mentions, keep, top_k=top_k, **summary_kwargs), top_k)
        for key, full_set in full.items():
            sub_set = sub.get(key, set())
            scores.append(len(full_set & sub_set) / len(full_set | sub_set))

    return {"mean_jaccard": float(np.mean(scores)), "rounds": n_rounds, "fraction": fraction, "top_k": top_k}


# ---------------------------------------------------------------------------
# 3. Annotation templates and human review
# ---------------------------------------------------------------------------

def build_annotation_sample(reviews: pd.DataFrame, n_per_star: int = 40, seed: int = 42) -> pd.DataFrame:
    """Stratified sentence sample for gold labeling.

    Equal numbers per star level, so cons are not swamped by the many 5-star
    reviews. Predictions are deliberately not shown, to avoid anchoring the
    annotator. Fill gold_labels as 'aspect:pro;aspect:con' (empty = none).
    """
    rows = []
    for review in reviews.itertuples(index=False):
        for s_idx, sentence in enumerate(split_sentences(review.text)):
            if len(sentence) >= 15:
                rows.append({
                    "review_id": review.review_id,
                    "asin": review.asin,
                    "stars": review.stars,
                    "sentence_index": s_idx,
                    "text": sentence,
                })
    sentences = pd.DataFrame(rows)
    if sentences.empty:
        return sentences

    # Shuffle, keep the first n per star level, then the order stays mixed.
    sample = (
        sentences.sample(frac=1, random_state=seed)
        .groupby("stars")
        .head(n_per_star)
        .reset_index(drop=True)
    )
    sample.insert(0, "item_id", [f"s{i:04d}" for i in range(len(sample))])
    sample["gold_labels"] = ""
    sample["annotator"] = ""
    sample["notes"] = ""
    return sample


SHEET_MATCH_COLUMNS = ["asin", "polarity", "aspect_label", "evidence_text"]


def build_product_review_sheet(
    summary: pd.DataFrame,
    n_products: int = 20,
    seed: int = 42,
    asins: list[str] | None = None,
) -> pd.DataFrame:
    """Sheet for judging extracted pros / cons with their evidence.

    judgement: yes (correct and useful), partial (right aspect, wrong or vague
    polarity), no (wrong). One row per extracted item.
    Pass asins to review a fixed set of products (for before / after runs).
    """
    if asins is None:
        pool = pd.Series(summary["asin"].unique())
        asins = list(pool.sample(min(len(pool), n_products), random_state=seed))
    sheet = summary[summary["asin"].isin(asins)].copy()
    sheet["evidence_text"] = sheet["evidence"].map(
        lambda e: " | ".join(item["text"] for item in json.loads(e))
    )
    sheet = sheet[["asin", "polarity", "rank", "aspect_label", "review_count", "evidence_text"]]
    sheet["judgement"] = ""
    sheet["notes"] = ""
    return sheet.sort_values(["asin", "polarity", "rank"]).reset_index(drop=True)


def carry_over_judgements(new_sheet: pd.DataFrame, old_sheet: pd.DataFrame) -> pd.DataFrame:
    """Copy judgements from a previous sheet to unchanged items.

    An item is unchanged when its product, polarity, aspect and evidence text
    are identical, so only new or changed items need a fresh judgement.
    """
    old = old_sheet.copy()
    old["judgement"] = old["judgement"].fillna("").astype(str).str.strip().str.lower()
    old = old[old["judgement"].isin(["yes", "partial", "no"])]
    old["notes"] = old["notes"].fillna("") if "notes" in old.columns else ""
    old["asin"] = old["asin"].astype(str)
    lookup = old.drop_duplicates(SHEET_MATCH_COLUMNS)[SHEET_MATCH_COLUMNS + ["judgement", "notes"]]

    out = new_sheet.drop(columns=["judgement", "notes"]).copy()
    out["asin"] = out["asin"].astype(str)
    out = out.merge(lookup, on=SHEET_MATCH_COLUMNS, how="left")
    out["judgement"] = out["judgement"].fillna("")
    out["notes"] = out["notes"].fillna("")
    return out


def score_product_review_sheet(sheet: pd.DataFrame) -> dict:
    """Precision of judged items: yes = 1, partial = 0.5, no = 0."""
    judged = sheet[sheet["judgement"].astype(str).str.strip().str.lower().isin(["yes", "partial", "no"])]
    if judged.empty:
        return {"judged_items": 0, "precision": None}
    values = judged["judgement"].str.strip().str.lower().map({"yes": 1.0, "partial": 0.5, "no": 0.0})
    by_polarity = values.groupby(judged["polarity"]).mean().round(4).to_dict()
    return {
        "judged_items": int(len(judged)),
        "precision": float(values.mean()),
        "strict_precision": float((values == 1.0).mean()),
        "precision_by_polarity": by_polarity,
    }
