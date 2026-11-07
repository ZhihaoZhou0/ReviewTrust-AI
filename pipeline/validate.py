
"""
ReviewTrust AI - Batch Data Quality Validation.

Validates cleaned Amazon review records before database loading.

This module detects quality problems but does not modify data.
Any critical validation failure stops the downstream ETL load.
"""

import json
from pathlib import Path

import polars as pl

from pipeline.clean_dataset import (
    PRODUCT_OUTPUT,
    REVIEW_OUTPUT,
)
from pipeline.source import expected_counts, snapshot_manifest


ROOT = Path(__file__).resolve().parents[1]
PROCESSED_DIR = ROOT / "data" / "processed"

# Use the same batch size as the incremental loading MVP.
BATCH_SIZE = 10000


def check_schema(df, required_columns):
    """
    Ensure all required columns exist in the cleaned dataset.

    Missing columns indicate a broken upstream data contract.
    """
    if df.columns != required_columns:
        raise ValueError(
            f"Cleaned CSV columns differ from the A1 contract: {df.columns}"
        )


def validate_batch(batch, product_asins, batch_id):
    """
    Apply row-level quality checks to a single review batch.

    Args:
        batch: Polars DataFrame containing cleaned reviews.
        product_asins: Set of known product identifiers.
        batch_id: Sequential number used for reporting.

    Returns:
        Dictionary with row count, validation status, and issues.
    """
    issues = {}

    def count_invalid(valid_expression):
        """
        Count records that fail a validation expression.

        Null validation results are treated as invalid
        unless the specific field explicitly allows NULL.
        """
        return batch.filter(
            ~valid_expression.fill_null(False)
        ).height

    # Check that ASIN follows Amazon's 10-character format.
    asin_valid = (
        pl.col("asin")
        .fill_null("")
        .str.contains(r"^[A-Z0-9]{10}$")
    )

    # A source review ID must exist, but it is not assumed
    # to be globally unique in this dataset.
    id_valid = (
        pl.col("source_review_id")
        .fill_null("")
        .str.strip_chars()
        .str.len_chars() > 0
    )

    # Source row hashes must contain 64 lowercase hex characters.
    hash_valid = (
        pl.col("source_row_hash")
        .fill_null("")
        .str.contains(r"^[0-9a-f]{64}$")
    )

    issues["invalid_asin"] = count_invalid(asin_valid)
    issues["missing_review_id"] = count_invalid(id_valid)
    issues["invalid_hash"] = count_invalid(hash_valid)

    row_number = pl.col("source_row_number").cast(pl.Int64, strict=False)
    issues["invalid_source_row_number"] = count_invalid(
        row_number.is_not_null() & (row_number > 0)
    )

    # Review star ratings must be integers from 1 to 5.
    stars = pl.col("stars").cast(
        pl.Int16, strict=False
    )

    issues["invalid_stars"] = count_invalid(
        stars.is_between(1, 5)
    )

    # Reject malformed or missing review dates.
    parsed_dates = (
        pl.col("review_date")
        .str.strptime(
            pl.Date,
            format="%Y-%m-%d",
            strict=False,
        )
    )

    issues["invalid_dates"] = count_invalid(
        parsed_dates.is_not_null()
    )

    # Source positions must be unique; repeated content is valid evidence.
    row_numbers = batch["source_row_number"].to_list()
    issues["duplicate_source_row_numbers"] = (
        len(row_numbers) - len(set(row_numbers))
    )
    hashes = batch["source_row_hash"].to_list()
    repeated_content_rows = len(hashes) - len(set(hashes))

    # Reviews must reference an existing product.
    issues["unknown_asin"] = count_invalid(
        pl.col("asin").is_in(list(product_asins))
    )

    # Helpful-vote counts must be nonnegative integers.
    helpful = pl.col("found_helpful").cast(
        pl.Int64, strict=False
    )

    issues["invalid_helpful"] = count_invalid(
        helpful.is_not_null() & (helpful >= 0)
    )

    # Verified purchase may be true, false, or unknown (NULL).
    # Unknown purchase status is not a validation failure.
    verified_valid = (
        pl.col("verified_purchase")
        .fill_null("")
        .is_in(["true", "false", ""])
    )

    issues["invalid_verified"] = count_invalid(
        verified_valid
    )

    # Keep only failed checks to simplify the quality report.
    issues = {
        key: value
        for key, value in issues.items()
        if value > 0
    }

    return {
        "batch_id": batch_id,
        "row_count": batch.height,
        "valid": len(issues) == 0,
        "issues": issues,
        "repeated_content_rows": repeated_content_rows,
    }


def run_validation():
    """
    Validate all cleaned reviews and generate a JSON report.

    Checks source-position integrity across batches and reports repeated
    content hashes as evidence rather than rejecting them.
    """
    products_path = PROCESSED_DIR / "products_clean.csv"
    reviews_path = PROCESSED_DIR / "reviews_clean.csv"

    # Read cleaned fields as strings to preserve their source
    # representation until explicit validation.
    products = pl.read_csv(
        products_path, infer_schema=False
    )

    reviews = pl.read_csv(
        reviews_path, infer_schema=False
    )

    # Enforce the output schemas defined by the A1 cleaner.
    check_schema(products, PRODUCT_OUTPUT)
    check_schema(reviews, REVIEW_OUTPUT)

    product_asins = set(
        products["asin"].drop_nulls().to_list()
    )

    # Reject duplicate or malformed product identifiers.
    if (
        len(product_asins) != products.height
        or any(
            len(asin) != 10 or not asin.isalnum()
            for asin in product_asins
        )
    ):
        raise ValueError(
            "Product ASIN integrity check failed."
        )

    results = []
    seen_hashes = set()
    seen_row_numbers = set()
    repeated_content_rows = 0
    cross_batch_duplicate_row_numbers = 0

    # Validate the dataset in fixed-size chunks.
    for batch_id, batch in enumerate(
        reviews.iter_slices(n_rows=BATCH_SIZE),
        start=1,
    ):
        result = validate_batch(
            batch, product_asins, batch_id
        )

        # Repeated hashes are a signal; repeated positions are a load error.
        hashes = batch["source_row_hash"].to_list()
        row_numbers = batch["source_row_number"].to_list()
        for row_hash in hashes:
            if row_hash in seen_hashes:
                repeated_content_rows += 1
            seen_hashes.add(row_hash)
        cross_batch_duplicate_row_numbers += sum(
            number in seen_row_numbers for number in row_numbers
        )
        seen_row_numbers.update(row_numbers)
        results.append(result)

        status = "PASS" if result["valid"] else "FAIL"

        print(
            f"Batch {batch_id}: {status} "
            f"({result['row_count']} rows)"
        )

        if result["issues"]:
            print("  Issues:", result["issues"])

    # The historical snapshot has known, audited totals. A truncated or
    # empty clean file must not turn an Airflow run green.
    expected_products, expected_reviews = expected_counts()
    snapshot_issues = {}
    if products.height != expected_products:
        snapshot_issues["product_count"] = {
            "expected": expected_products, "actual": products.height
        }
    if reviews.height != expected_reviews:
        snapshot_issues["review_count"] = {
            "expected": expected_reviews, "actual": reviews.height
        }
    expected_repeated = snapshot_manifest()["reviews"]["exact_duplicate_rows"]
    if repeated_content_rows != expected_repeated:
        snapshot_issues["repeated_content_rows"] = {
            "expected": expected_repeated, "actual": repeated_content_rows
        }

    # Every batch must pass, the audited totals must match, and
    # source positions must never repeat.
    all_valid = (
        all(result["valid"] for result in results)
        and cross_batch_duplicate_row_numbers == 0
        and len(results) > 0
        and not snapshot_issues
    )

    report = {
        "valid": all_valid,
        "total_rows": reviews.height,
        "total_batches": len(results),
        "cross_batch_duplicate_row_numbers": cross_batch_duplicate_row_numbers,
        "repeated_content_rows": repeated_content_rows,
        "snapshot_issues": snapshot_issues,
        "failed_batches": sum(
            not result["valid"] for result in results
        ),
        "batches": results,
    }

    # Save a structured report for ETL monitoring and debugging.
    output_path = (
        PROCESSED_DIR / "validation-report.json"
    )

    output_path.write_text(
        json.dumps(report, indent=2),
        encoding="utf-8",
    )

    print("\n=== VALIDATION SUMMARY ===")
    print("Total rows:", report["total_rows"])
    print("Total batches:", report["total_batches"])
    print("Failed batches:", report["failed_batches"])
    print(
        "Cross-batch duplicate source positions:",
        cross_batch_duplicate_row_numbers,
    )
    print("Repeated-content review rows:", repeated_content_rows)
    print("Overall:", "PASS" if all_valid else "FAIL")

    # Raise an exception so Airflow blocks downstream loading.
    if not all_valid:
        raise ValueError(
            "Data quality validation failed."
        )

    return report


if __name__ == "__main__":
    run_validation()
