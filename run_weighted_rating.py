
"""Run experimental weighted product rating analysis."""

from pathlib import Path

import pandas as pd

from nlp.weighted_rating import (
    compute_review_weights,
    compute_product_ratings,
)


INPUT_PATH = Path("data/processed/similarity_results.csv")

REVIEW_OUTPUT = Path(
    "data/processed/weighted_review_results.csv"
)

PRODUCT_OUTPUT = Path(
    "data/processed/product_rating_comparison.csv"
)


def main():
    if not INPUT_PATH.exists():
        raise FileNotFoundError(
            f"Missing {INPUT_PATH}. Run run_similarity.py first."
        )

    df = pd.read_csv(INPUT_PATH, low_memory=False)

    print("=== Weighted Product Rating ===")
    print(f"Input reviews: {len(df):,}")
    print(f"Products: {df['asin'].nunique():,}")

    weighted = compute_review_weights(df)

    products = compute_product_ratings(
        weighted,
        min_reviews=2,
    )

    print("\n=== Review Weight Distribution ===")
    print(
        weighted["weight_reason"]
        .value_counts()
        .to_string()
    )

    print("\n=== Product Rating Summary ===")
    print(f"Products evaluated: {len(products):,}")

    changed = products[
        products["rating_difference"].abs() > 1e-9
    ]

    print(f"Products with rating changes: {len(changed):,}")

    print("\n=== Largest Rating Changes ===")

    print(
        products.head(10).round(4).to_string(index=False)
    )

    REVIEW_OUTPUT.parent.mkdir(
        parents=True, exist_ok=True
    )

    weighted.to_csv(REVIEW_OUTPUT, index=False)
    products.to_csv(PRODUCT_OUTPUT, index=False)

    print(f"\nSaved reviews: {REVIEW_OUTPUT}")
    print(f"Saved products: {PRODUCT_OUTPUT}")


if __name__ == "__main__":
    main()
