
"""Conservative, evidence-based product rating adjustment.

The adjusted rating is an experimental sensitivity metric,
not a verified estimate of true product quality.
"""

from __future__ import annotations

import pandas as pd


def compute_review_weights(
    df: pd.DataFrame,
    similarity_threshold: float = 0.85,
    duplicate_weight: float = 0.80,
    exact_duplicate_weight: float = 0.60,
    min_text_length: int = 50,
) -> pd.DataFrame:
    """Assign text reliability and source deduplication weights."""

    required = {
        "asin",
        "stars",
        "max_text_similarity",
        "text_length",
        "is_exact_duplicate",
    }

    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Missing columns: {sorted(missing)}")

    if not 0 <= similarity_threshold <= 1:
        raise ValueError("similarity_threshold must be in [0, 1]")

    if min_text_length < 1:
        raise ValueError("min_text_length must be at least 1")

    for name, value in [
        ("duplicate_weight", duplicate_weight),
        ("exact_duplicate_weight", exact_duplicate_weight),
    ]:
        if not 0 < value <= 1:
            raise ValueError(f"{name} must be in (0, 1]")

    if exact_duplicate_weight > duplicate_weight:
        raise ValueError(
            "exact_duplicate_weight cannot exceed duplicate_weight"
        )

    result = df.copy()

    result["stars"] = pd.to_numeric(
        result["stars"], errors="coerce"
    )

    result["max_text_similarity"] = pd.to_numeric(
        result["max_text_similarity"], errors="coerce"
    ).fillna(0.0)

    result["text_length"] = pd.to_numeric(
        result["text_length"], errors="coerce"
    ).fillna(0)

    exact = result["is_exact_duplicate"].eq(True).fillna(False)
    eligible = result["text_length"] >= min_text_length

    near_duplicate = (
        eligible
        & (
            result["max_text_similarity"]
            >= similarity_threshold
        )
    )

    exact_duplicate = eligible & exact

    # Step 1: Text-based reliability weight.
    result["text_weight"] = 1.0
    result.loc[near_duplicate, "text_weight"] = duplicate_weight
    result.loc[
        exact_duplicate, "text_weight"
    ] = exact_duplicate_weight

    result["weight_reason"] = "no_duplicate_evidence"
    result.loc[
        near_duplicate, "weight_reason"
    ] = "high_text_similarity"
    result.loc[
        exact_duplicate, "weight_reason"
    ] = "exact_text_duplicate"

    # Step 2: Source-level deduplication weight.
    result["source_duplicate_count"] = 1

    if "source_row_hash" in result.columns:
        hashes = result["source_row_hash"]

        if hashes.isna().any() or hashes.astype(str).str.strip().eq("").any():
            raise ValueError("source_row_hash contains missing values")

        inconsistent_products = (
            result.groupby("source_row_hash")["asin"]
            .nunique(dropna=False)
            .gt(1)
        )

        if inconsistent_products.any():
            raise ValueError(
                "Identical source_row_hash values appear "
                "under different products"
            )

        result["source_duplicate_count"] = (
            result.groupby("source_row_hash")["asin"]
            .transform("size")
        )

    result["source_duplicate_weight"] = (
        1.0 / result["source_duplicate_count"]
    )

    # Step 3: Final weight.
    result["review_weight"] = (
        result["text_weight"]
        * result["source_duplicate_weight"]
    )

    # ML anomaly flags are deliberately excluded.
    # Statistical outliers are not necessarily fake reviews.

    return result



def compute_product_ratings(
    df: pd.DataFrame,
    min_reviews: int = 1,
) -> pd.DataFrame:
    """Compare raw, source-deduplicated, and adjusted product ratings."""

    required = {"asin", "stars", "review_weight"}
    missing = required - set(df.columns)

    if missing:
        raise ValueError(f"Missing columns: {sorted(missing)}")

    if min_reviews < 1:
        raise ValueError("min_reviews must be >= 1")

    valid = df.copy()

    valid["stars"] = pd.to_numeric(
        valid["stars"], errors="coerce"
    )
    valid["review_weight"] = pd.to_numeric(
        valid["review_weight"], errors="coerce"
    )

    if "source_duplicate_weight" not in valid.columns:
        valid["source_duplicate_weight"] = 1.0

    valid["source_duplicate_weight"] = pd.to_numeric(
        valid["source_duplicate_weight"], errors="coerce"
    )

    valid = valid.dropna(
        subset=[
            "asin",
            "stars",
            "review_weight",
            "source_duplicate_weight",
        ]
    )

    valid = valid[
        valid["stars"].between(1, 5)
        & valid["review_weight"].between(
            0, 1, inclusive="right"
        )
        & valid["source_duplicate_weight"].between(
            0, 1, inclusive="right"
        )
    ].copy()

    valid["weighted_stars"] = (
        valid["stars"] * valid["review_weight"]
    )

    valid["deduplicated_stars"] = (
        valid["stars"] * valid["source_duplicate_weight"]
    )

    grouped = valid.groupby("asin")

    summary = grouped.agg(
        review_count=("stars", "size"),
        original_rating=("stars", "mean"),
        weighted_sum=("weighted_stars", "sum"),
        weight_sum=("review_weight", "sum"),
        deduplicated_sum=("deduplicated_stars", "sum"),
        deduplicated_weight_sum=(
            "source_duplicate_weight", "sum"
        ),
        adjusted_review_count=(
            "review_weight",
            lambda x: int((x < 1).sum()),
        ),
    ).reset_index()

    summary = summary[
        summary["review_count"] >= min_reviews
    ].copy()

    summary["deduplicated_rating"] = (
        summary["deduplicated_sum"]
        / summary["deduplicated_weight_sum"]
    )

    summary["adjusted_rating"] = (
        summary["weighted_sum"]
        / summary["weight_sum"]
    )

    summary["rating_difference"] = (
        summary["adjusted_rating"]
        - summary["original_rating"]
    )

    summary["deduplication_difference"] = (
        summary["deduplicated_rating"]
        - summary["original_rating"]
    )

    summary["text_adjustment_difference"] = (
        summary["adjusted_rating"]
        - summary["deduplicated_rating"]
    )

    summary["adjusted_review_percentage"] = (
        summary["adjusted_review_count"]
        / summary["review_count"]
        * 100
    )

    return summary[
        [
            "asin",
            "review_count",
            "original_rating",
            "deduplicated_rating",
            "adjusted_rating",
            "rating_difference",
            "deduplication_difference",
            "text_adjustment_difference",
            "adjusted_review_count",
            "adjusted_review_percentage",
        ]
    ].sort_values(
        "rating_difference",
        key=lambda x: x.abs(),
        ascending=False,
    ).reset_index(drop=True)
