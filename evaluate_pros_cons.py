"""B2 NLP evaluation commands.

    # 1. Gold-label metrics (seed set or your own labeled sample)
    python evaluate_pros_cons.py gold --gold tests/fixtures/pros_cons_seed_gold.csv
    python evaluate_pros_cons.py gold --gold data/processed/evaluation/gold_sentences.csv --sentiment lexicon vader

    # 2. Automatic checks on real data (run run_pros_cons.py first)
    python evaluate_pros_cons.py auto            # uses the scope of the last run

    # 3. Export templates for human labeling / review
    python evaluate_pros_cons.py sample --n-per-star 40
    python evaluate_pros_cons.py sheet --n-products 20
    python evaluate_pros_cons.py score-sheet --sheet data/processed/evaluation/product_review_sheet.csv
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from analytics.pros_cons_evaluation import (
    carry_over_judgements,
    build_annotation_sample,
    build_product_review_sheet,
    coverage_metrics,
    evaluate_against_gold,
    evidence_faithfulness,
    score_product_review_sheet,
    star_consistency,
    subsample_stability,
)
from nlp.pros_cons.sentiment import get_sentiment_scorer
from run_pros_cons import DEFAULT_INPUT, load_reviews


PROCESSED = Path("data/processed")
# Annotation files contain review text, so they live under the git-ignored data/ folder.
EVAL_DIR = Path("data/processed/evaluation")


def _print_json(title: str, data: dict):
    print(f"\n=== {title} ===")
    print(json.dumps(data, indent=2, default=str))


def cmd_gold(args):
    gold = pd.read_csv(args.gold, keep_default_na=False)
    report = {}
    for backend in args.sentiment:
        result = evaluate_against_gold(gold, scorer=get_sentiment_scorer(backend))
        report[backend] = {
            "n_items": result["n_items"],
            "aspect_polarity": result["aspect_polarity"],
            "aspect_detection": result["aspect_detection"],
            "polarity_accuracy": result["polarity_accuracy"],
        }
        print(f"\n=== Gold evaluation ({backend}) on {result['n_items']} items ===")
        for key in ("aspect_polarity", "aspect_detection"):
            m = result[key]
            print(f"{key:18s} P={m['precision']:.3f} R={m['recall']:.3f} F1={m['f1']:.3f}")
        print(f"polarity_accuracy  {result['polarity_accuracy']:.3f}")

        PROCESSED.mkdir(parents=True, exist_ok=True)
        result["errors"].to_csv(PROCESSED / f"pros_cons_gold_errors_{backend}.csv", index=False)
        result["per_aspect"].to_csv(PROCESSED / f"pros_cons_gold_per_aspect_{backend}.csv", index=False)

    (PROCESSED / "pros_cons_gold_report.json").write_text(json.dumps(report, indent=2))
    print(f"\nErrors and per-aspect tables saved in {PROCESSED}/")


def cmd_auto(args):
    # Evaluate the same reviews the last run_pros_cons.py run used, unless overridden.
    run_info_path = PROCESSED / "pros_cons_run.json"
    if run_info_path.exists():
        run_info = json.loads(run_info_path.read_text())
        if args.input is None:
            args.input = Path(run_info.get("input", DEFAULT_INPUT))
        if args.id_column is None:
            args.id_column = run_info.get("id_column")
        if args.top_products is None:
            args.top_products = run_info.get("top_products", 0)
        print(f"Evaluating the last run: input={args.input}, top_products={args.top_products}")
    args.input = args.input or DEFAULT_INPUT
    args.top_products = args.top_products or 0
    reviews = load_reviews(args.input, args.id_column, args.top_products)
    mentions = pd.read_csv(PROCESSED / "pros_cons_mentions.csv", dtype={"review_id": "string", "record_key": "string"})
    summary = pd.read_csv(PROCESSED / "product_pros_cons.csv")
    # Evaluate only products present in both (handles --top-products runs).
    mentions = mentions[mentions["asin"].isin(reviews["asin"])]
    summary = summary[summary["asin"].isin(reviews["asin"])]

    report = {
        "star_consistency": star_consistency(mentions),
        "coverage": coverage_metrics(mentions, reviews, summary),
        "evidence_faithfulness": evidence_faithfulness(summary, reviews),
        "stability": subsample_stability(mentions, reviews, n_rounds=args.rounds),
    }
    for key, value in report.items():
        _print_json(key, value if isinstance(value, dict) else {"value": value})
    (PROCESSED / "pros_cons_auto_report.json").write_text(json.dumps(report, indent=2, default=str))
    print(f"\nSaved {PROCESSED}/pros_cons_auto_report.json")


def cmd_sample(args):
    reviews = load_reviews(args.input, args.id_column, args.top_products)
    sample = build_annotation_sample(reviews, n_per_star=args.n_per_star, seed=args.seed)
    EVAL_DIR.mkdir(parents=True, exist_ok=True)
    out = EVAL_DIR / "annotation_sample.csv"
    sample.to_csv(out, index=False)
    print(f"Saved {len(sample)} sentences to {out}. Fill gold_labels, then save as data/processed/evaluation/gold_sentences.csv")


def cmd_sheet(args):
    summary = pd.read_csv(PROCESSED / "product_pros_cons.csv")
    previous = None
    asins = None
    if args.previous is not None:
        # Re-review the same products and keep judgements for unchanged items.
        previous = pd.read_csv(args.previous, keep_default_na=False)
        asins = list(previous["asin"].astype(str).unique())
    sheet = build_product_review_sheet(summary, n_products=args.n_products, seed=args.seed, asins=asins)
    if previous is not None:
        sheet = carry_over_judgements(sheet, previous)

    EVAL_DIR.mkdir(parents=True, exist_ok=True)
    out = args.output or EVAL_DIR / "product_review_sheet.csv"
    sheet.to_csv(out, index=False)
    todo = int((sheet["judgement"] == "").sum())
    print(f"Saved {len(sheet)} items to {out}.")
    print(f"Items still to judge (yes / partial / no): {todo}")


def cmd_score_sheet(args):
    sheet = pd.read_csv(args.sheet, keep_default_na=False)
    _print_json("Product-level human review", score_product_review_sheet(sheet))


def parse_args():
    parser = argparse.ArgumentParser(description="B2 NLP evaluation")
    sub = parser.add_subparsers(dest="command", required=True)

    gold = sub.add_parser("gold", help="P / R / F1 against labeled sentences")
    gold.add_argument("--gold", type=Path, default=Path("tests/fixtures/pros_cons_seed_gold.csv"))
    gold.add_argument("--sentiment", nargs="+", choices=["lexicon", "vader"], default=["lexicon"])
    gold.set_defaults(func=cmd_gold)

    for name, func, helptext in [
        ("auto", cmd_auto, "Label-free checks on run_pros_cons.py output"),
        ("sample", cmd_sample, "Export a stratified sentence sample to label"),
    ]:
        p = sub.add_parser(name, help=helptext)
        # auto: None means "same as the last run_pros_cons.py run".
        default_input = None if name == "auto" else DEFAULT_INPUT
        default_top = None if name == "auto" else 0
        p.add_argument("--input", type=Path, default=default_input)
        p.add_argument("--id-column", default=None)
        p.add_argument("--top-products", type=int, default=default_top)
        p.add_argument("--seed", type=int, default=42)
        p.set_defaults(func=func)
        if name == "auto":
            p.add_argument("--rounds", type=int, default=10)
        else:
            p.add_argument("--n-per-star", type=int, default=40)

    sheet = sub.add_parser("sheet", help="Export product-level review sheet")
    sheet.add_argument("--n-products", type=int, default=20)
    sheet.add_argument("--seed", type=int, default=42)
    sheet.add_argument("--previous", type=Path, default=None,
                       help="Earlier filled sheet: reuse its products and judgements")
    sheet.add_argument("--output", type=Path, default=None)
    sheet.set_defaults(func=cmd_sheet)

    score = sub.add_parser("score-sheet", help="Score a filled product review sheet")
    score.add_argument("--sheet", type=Path, required=True)
    score.set_defaults(func=cmd_score_sheet)
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    args.func(args)
