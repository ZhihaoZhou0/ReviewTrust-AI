"""Run B2 Pros & Cons extraction.

Examples (from the repository root):

    # B1 NLP view (prepare_nlp_data.py -> reviews_b1_nlp.csv), all products
    python run_pros_cons.py

    # Quick run on the 50 most-reviewed products (same selection as run_similarity.py)
    python run_pros_cons.py --top-products 50

    # A1 cleaned table directly (same keys as the B1 view)
    python run_pros_cons.py --input data/processed/reviews_clean.csv

    # Optional: rank by B1 text-reliability weights (run_weighted_rating.py output)
    python run_pros_cons.py --weights data/processed/weighted_review_results.csv
"""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from nlp.pros_cons import (
    METHOD_VERSION,
    build_product_cards,
    extract_aspect_mentions,
    prepare_reviews,
    summarize_pros_cons,
)
from nlp.pros_cons.schema import attach_review_weights
from nlp.pros_cons.sentiment import get_sentiment_scorer


DEFAULT_INPUT = Path("data/processed/reviews_b1_nlp.csv")
DEFAULT_OUTPUT_DIR = Path("data/processed")


def load_reviews(
    path: Path,
    id_column: str | None = None,
    top_products: int = 0,
    weights_path: Path | None = None,
    weights_id_column: str = "source_row_number",
) -> pd.DataFrame:
    """Read a review CSV and return it in the B2 internal schema."""
    if not path.exists():
        raise FileNotFoundError(f"Missing {path}. Run prepare_nlp_data.py first (or pass --input).")
    raw = pd.read_csv(path, low_memory=False)
    reviews = prepare_reviews(raw, id_column=id_column)

    if top_products > 0:
        top = reviews.groupby("asin").size().sort_values(ascending=False).head(top_products).index
        reviews = reviews[reviews["asin"].isin(top)].reset_index(drop=True)

    if weights_path is not None:
        weights = pd.read_csv(weights_path, low_memory=False)
        reviews = attach_review_weights(reviews, weights, weight_id_column=weights_id_column)
    return reviews


def parse_args():
    parser = argparse.ArgumentParser(description="B2 Pros & Cons extraction")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--id-column", default=None, help="Unique review key column (auto-detected if omitted)")
    parser.add_argument("--top-products", type=int, default=0, help="Limit to the N most-reviewed products (0 = all)")
    parser.add_argument("--weights", type=Path, default=None, help="Optional B1 weighted_review_results.csv")
    parser.add_argument("--weights-id-column", default="source_row_number")
    parser.add_argument("--sentiment", choices=["lexicon", "vader"], default="lexicon")
    parser.add_argument("--top-k", type=int, default=5, help="Pros / cons kept per product")
    parser.add_argument("--min-reviews", type=int, default=3)
    parser.add_argument("--min-share", type=float, default=0.03)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args()


def main():
    args = parse_args()
    start = time.time()

    reviews = load_reviews(args.input, args.id_column, args.top_products, args.weights, args.weights_id_column)
    print("=== B2 Pros & Cons Extraction ===")
    print(f"Reviews with text: {len(reviews):,}")
    print(f"Distinct source records: {reviews['record_key'].nunique():,}")
    print(f"Products: {reviews['asin'].nunique():,}")

    scorer = get_sentiment_scorer(args.sentiment)
    mentions = extract_aspect_mentions(reviews, scorer=scorer)
    summary = summarize_pros_cons(
        mentions, reviews, top_k=args.top_k, min_reviews=args.min_reviews, min_share=args.min_share
    )
    cards = build_product_cards(summary, reviews)

    print(f"Opinion mentions: {len(mentions):,}")
    print(f"Ranked pros / cons rows: {len(summary):,}")
    print("\n=== Most frequent aspects ===")
    print(mentions.groupby(["aspect_label", "polarity"]).size().unstack(fill_value=0)
          .sort_values("pro", ascending=False).head(10).to_string())

    args.output_dir.mkdir(parents=True, exist_ok=True)
    mentions.to_csv(args.output_dir / "pros_cons_mentions.csv", index=False)
    summary.to_csv(args.output_dir / "product_pros_cons.csv", index=False)
    cards.to_csv(args.output_dir / "product_pros_cons_cards.csv", index=False)

    run_info = {
        "method_version": METHOD_VERSION,
        "sentiment_backend": args.sentiment,
        "input": str(args.input),
        "weights": str(args.weights) if args.weights else None,
        "id_column": args.id_column,
        "top_products": args.top_products,
        "reviews": int(len(reviews)),
        "products": int(reviews["asin"].nunique()),
        "mentions": int(len(mentions)),
        "summary_rows": int(len(summary)),
        "parameters": {"top_k": args.top_k, "min_reviews": args.min_reviews, "min_share": args.min_share},
        "created_at": datetime.now(timezone.utc).isoformat(),
        "seconds": round(time.time() - start, 1),
    }
    (args.output_dir / "pros_cons_run.json").write_text(json.dumps(run_info, indent=2))

    print(f"\nSaved to {args.output_dir}/: pros_cons_mentions.csv, product_pros_cons.csv, "
          "product_pros_cons_cards.csv, pros_cons_run.json")
    print(f"Done in {run_info['seconds']}s")


if __name__ == "__main__":
    main()
