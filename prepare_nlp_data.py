
"""Prepare A1 cleaned reviews for downstream B1 NLP analysis."""

from pathlib import Path

import pandas as pd

INPUT_PATH = Path("data/processed/reviews_clean.csv")
OUTPUT_PATH = Path("data/processed/reviews_b1_nlp.csv")

REQUIRED_COLUMNS = {
    "source_row_number",
    "source_review_id",
    "asin",
    "body",
    "stars",
    "user_id",
    "review_date",
    "verified_purchase",
    "found_helpful",
}


def prepare_nlp_data(
    input_path: Path = INPUT_PATH,
    output_path: Path = OUTPUT_PATH,
) -> pd.DataFrame:
    """Retain all source reviews and add text-analysis metadata."""

    df = pd.read_csv(
        input_path,
        low_memory=False,
        keep_default_na=False,
    )

    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        raise ValueError(f"Missing required columns: {sorted(missing)}")

    if df["source_row_number"].isna().any():
        raise ValueError("Missing source_row_number values")

    if not df["source_row_number"].is_unique:
        raise ValueError("source_row_number must be unique")

    original_count = len(df)

    # Preserve original review text; do not deduplicate by ID or content.
    df["has_text"] = (
        df["body"].notna()
        & df["body"].astype("string").str.strip().ne("").fillna(False)
    )

    # Text length is zero for missing or blank review bodies.
    df["text_length"] = (
        df["body"].fillna("").astype(str).str.len()
    )

    # Flag repeated source review IDs without removing any records.
    df["repeated_source_id"] = df.duplicated(
        subset=["source_review_id"],
        keep=False,
    )

    # Exact text matches within the same product are useful
    # for downstream anomaly analysis, not proof of fraud.
    nonempty = df["has_text"]

    df["same_product_exact_text"] = False
    df.loc[nonempty, "same_product_exact_text"] = (
        df.loc[nonempty].duplicated(
            subset=["asin", "body"],
            keep=False,
        )
    )

    if len(df) != original_count:
        raise AssertionError("Source review rows were lost")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False)

    print("=== B1 NLP Data Preparation ===")
    print(f"Source reviews: {original_count:,}")
    print(f"Output reviews: {len(df):,}")
    print(f"Reviews with text: {int(df['has_text'].sum()):,}")
    print(f"Reviews without text: {int((~df['has_text']).sum()):,}")
    print(
        "Rows with repeated source IDs: "
        f"{int(df['repeated_source_id'].sum()):,}"
    )
    print(
        "Rows with exact same-product text matches: "
        f"{int(df['same_product_exact_text'].sum()):,}"
    )
    print(f"Saved to: {output_path}")

    return df


if __name__ == "__main__":
    prepare_nlp_data()
