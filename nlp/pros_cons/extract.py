"""Pros & Cons extraction and per-product aggregation.

Pipeline (per review):
    text -> sentences -> clauses (split at "but", "however", ...)
         -> aspect terms in each clause -> clause sentiment
         -> one mention per (clause, aspect) with polarity pro / con

Per product:
    count distinct reviews per (aspect, polarity), rank, attach evidence.
"""

from __future__ import annotations

import json

import pandas as pd

from nlp.pros_cons.aspects import AspectMatcher
from nlp.pros_cons.schema import METHOD_VERSION
from nlp.pros_cons.sentiment import LexiconSentiment, is_negated
from nlp.pros_cons.text import split_clauses, split_sentences, tokenize


POLARITY_THRESHOLD = 0.2   # |score| below this is treated as neutral
INHERENT_WEIGHT = 0.5      # how much an aspect term's own polarity adds

MENTION_COLUMNS = [
    "review_id", "record_key", "asin", "sentence_index", "clause_index", "clause_text",
    "aspect", "aspect_label", "matched_terms", "sentiment_score", "polarity",
    "stars", "review_weight", "found_helpful", "method_version",
]


def _polarity(score: float, threshold: float) -> str:
    if score >= threshold:
        return "pro"
    if score <= -threshold:
        return "con"
    return "neutral"


def analyze_clause(clause: str, scorer, matcher: AspectMatcher, threshold: float) -> list[dict]:
    """Return one dict per aspect found in a clause, with its polarity."""
    tokens = tokenize(clause)
    hits = matcher.find(tokens)
    if not hits:
        return []

    base = scorer.score(clause)

    # Several terms of the same aspect in one clause count once.
    by_aspect: dict[str, dict] = {}
    for hit in hits:
        signed = hit.inherent * (-1 if is_negated(tokens, hit.start) else 1)
        entry = by_aspect.setdefault(hit.aspect, {"terms": [], "inherent": 0})
        entry["terms"].append(hit.term)
        entry["inherent"] += signed

    results = []
    for aspect, entry in by_aspect.items():
        signal = entry["inherent"] + matcher.cue_polarity(aspect, tokens)
        score = base + INHERENT_WEIGHT * signal
        score = max(-1.0, min(1.0, score))
        results.append({
            "aspect": aspect,
            "aspect_label": matcher.label(aspect),
            "matched_terms": ";".join(entry["terms"]),
            "sentiment_score": round(score, 4),
            "polarity": _polarity(score, threshold),
        })
    return results


def extract_aspect_mentions(
    reviews: pd.DataFrame,
    scorer=None,
    matcher: AspectMatcher | None = None,
    threshold: float = POLARITY_THRESHOLD,
    keep_neutral: bool = False,
) -> pd.DataFrame:
    """Extract aspect mentions from prepared reviews (see schema.prepare_reviews).

    The star rating is copied to the output for evaluation, but it is never
    used to decide polarity.
    """
    required = {"review_id", "record_key", "asin", "text", "stars", "review_weight", "found_helpful"}
    missing = required - set(reviews.columns)
    if missing:
        raise ValueError(f"Missing columns: {sorted(missing)}. Run prepare_reviews first.")

    scorer = scorer or LexiconSentiment()
    matcher = matcher or AspectMatcher()

    rows = []
    for review in reviews.itertuples(index=False):
        for s_idx, sentence in enumerate(split_sentences(review.text)):
            for c_idx, clause in enumerate(split_clauses(sentence)):
                for result in analyze_clause(clause, scorer, matcher, threshold):
                    if result["polarity"] == "neutral" and not keep_neutral:
                        continue
                    rows.append({
                        "review_id": review.review_id,
                        "record_key": review.record_key,
                        "asin": review.asin,
                        "sentence_index": s_idx,
                        "clause_index": c_idx,
                        "clause_text": clause,
                        **result,
                        "stars": review.stars,
                        "review_weight": review.review_weight,
                        "found_helpful": review.found_helpful,
                        "method_version": METHOD_VERSION,
                    })

    return pd.DataFrame(rows, columns=MENTION_COLUMNS)


def _support_level(count: int) -> str:
    if count >= 15:
        return "high"
    if count >= 5:
        return "medium"
    return "low"


def _evidence_rank_key(df: pd.DataFrame) -> pd.DataFrame:
    """Prefer clear, helpful, readable clauses as evidence."""
    out = df.copy()
    out["_strength"] = out["sentiment_score"].abs()
    length = out["clause_text"].str.len()
    out["_readable"] = length.between(25, 220).astype(int)
    return out.sort_values(
        ["_readable", "_strength", "found_helpful"], ascending=[False, False, False]
    )


def summarize_pros_cons(
    mentions: pd.DataFrame,
    reviews: pd.DataFrame,
    top_k: int = 5,
    min_reviews: int = 3,
    min_share: float = 0.03,
    evidence_k: int = 3,
    use_weights: bool = True,
) -> pd.DataFrame:
    """Rank pros and cons per product.

    Counts are distinct source records (record_key), so neither one long
    review nor exact source repeats can dominate an aspect.
    With use_weights=True, ranking uses the sum of review_weight over those
    records (B1 text weights; all 1.0 when B1 output is not attached).
    """
    if min_reviews < 1 or not 0 <= min_share <= 1:
        raise ValueError("min_reviews must be >= 1 and min_share in [0, 1]")

    n_reviews = reviews.groupby("asin")["record_key"].nunique().rename("n_text_reviews")

    voted = mentions[mentions["polarity"].isin(["pro", "con"])]
    if voted.empty:
        return pd.DataFrame(columns=SUMMARY_COLUMNS)

    # One row per (source record, aspect, polarity): keep its best clause.
    ranked = _evidence_rank_key(voted)
    per_review = ranked.drop_duplicates(["asin", "record_key", "aspect", "polarity"])

    rows = []
    for (asin, aspect, polarity), group in per_review.groupby(
        ["asin", "aspect", "polarity"], sort=False
    ):
        # Distinct snippets only: repeated text (common in this dataset) is weak evidence.
        snippet_key = group["clause_text"].str.casefold().str.strip(" .!?")
        distinct = group[~snippet_key.duplicated()]
        evidence = [
            {"review_id": str(r.review_id), "text": r.clause_text, "stars": int(r.stars) if pd.notna(r.stars) else None}
            for r in distinct.head(evidence_k).itertuples(index=False)
        ]
        rows.append({
            "asin": asin,
            "aspect": aspect,
            "aspect_label": group["aspect_label"].iloc[0],
            "polarity": polarity,
            "review_count": int(group["record_key"].nunique()),
            "weighted_review_count": float(group["review_weight"].sum()),
            "avg_stars": float(group["stars"].mean()),
            "evidence": json.dumps(evidence, ensure_ascii=False),
        })

    summary = pd.DataFrame(rows).merge(n_reviews, on="asin", how="left")
    summary["mention_share"] = summary["review_count"] / summary["n_text_reviews"]

    # How one-sided is the aspect? 1.0 = everyone agrees, 0.5 = split opinion.
    opposite = summary[["asin", "aspect", "polarity", "review_count"]].copy()
    opposite["polarity"] = opposite["polarity"].map({"pro": "con", "con": "pro"})
    opposite = opposite.rename(columns={"review_count": "opposing_review_count"})
    summary = summary.merge(opposite, on=["asin", "aspect", "polarity"], how="left")
    summary["opposing_review_count"] = summary["opposing_review_count"].fillna(0).astype(int)
    summary["consensus"] = summary["review_count"] / (
        summary["review_count"] + summary["opposing_review_count"]
    )

    summary = summary[
        (summary["review_count"] >= min_reviews) & (summary["mention_share"] >= min_share)
    ].copy()

    sort_col = "weighted_review_count" if use_weights else "review_count"
    summary = summary.sort_values(
        ["asin", "polarity", sort_col, "review_count", "aspect"],
        ascending=[True, True, False, False, True],
    )
    summary["rank"] = summary.groupby(["asin", "polarity"]).cumcount() + 1
    summary = summary[summary["rank"] <= top_k].copy()

    summary["support_level"] = summary["review_count"].map(_support_level)
    summary["method_version"] = METHOD_VERSION
    return summary[SUMMARY_COLUMNS].reset_index(drop=True)


SUMMARY_COLUMNS = [
    "asin", "polarity", "rank", "aspect", "aspect_label", "review_count",
    "weighted_review_count", "n_text_reviews", "mention_share", "avg_stars",
    "opposing_review_count", "consensus", "support_level", "evidence",
    "method_version",
]


def build_product_cards(summary: pd.DataFrame, reviews: pd.DataFrame) -> pd.DataFrame:
    """One row per product with pros / cons as JSON lists, ready for the dashboard."""
    n_reviews = reviews.groupby("asin")["record_key"].nunique()
    cards = []
    for asin, total in n_reviews.items():
        product = summary[summary["asin"] == asin]
        card = {"asin": asin, "n_text_reviews": int(total)}
        for polarity, key in [("pro", "pros"), ("con", "cons")]:
            items = product[product["polarity"] == polarity].sort_values("rank")
            card[key] = json.dumps([
                {
                    "aspect": r.aspect,
                    "label": r.aspect_label,
                    "review_count": int(r.review_count),
                    "share": round(float(r.mention_share), 4),
                    "consensus": round(float(r.consensus), 4),
                    "support_level": r.support_level,
                    "evidence": json.loads(r.evidence),
                }
                for r in items.itertuples(index=False)
            ], ensure_ascii=False)
        card["method_version"] = METHOD_VERSION
        cards.append(card)
    return pd.DataFrame(cards, columns=["asin", "n_text_reviews", "pros", "cons", "method_version"])
