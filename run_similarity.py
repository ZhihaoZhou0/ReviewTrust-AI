import argparse
from pathlib import Path

import pandas as pd

from nlp.features import build_anomaly_features
from nlp.isolation_forest import compute_ml_anomaly_score
from nlp.reliability import compute_rule_anomaly_score
from nlp.similarity import compute_review_similarity

DATA_PATH = Path("data/processed/reviews_b1_nlp.csv")
OUTPUT_PATH = Path("data/processed/similarity_results.csv")

parser = argparse.ArgumentParser(
    description="Run review similarity and anomaly detection."
)

selection = parser.add_mutually_exclusive_group()

selection.add_argument(
    "--top-products",
    type=int,
    default=5,
    help="Analyze the N products with the most reviews (default: 5).",
)

selection.add_argument(
    "--all-products",
    action="store_true",
    help="Analyze all products.",
)

args = parser.parse_args()

if args.top_products is not None and args.top_products < 1:
    parser.error("--top-products must be at least 1")

OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

# Load actual 2025 Amazon reviews
df = pd.read_csv(
    DATA_PATH,
    low_memory=False,
    keep_default_na=False,
)

print(f"Total reviews: {len(df):,}")

# Select complete products rather than arbitrary individual reviews.
# This preserves within-product similarity comparisons.
if args.all_products:
    sample = df.copy()
else:
    selected_asins = (
        df.groupby("asin")
        .size()
        .sort_values(ascending=False)
        .head(args.top_products)
        .index
    )

    sample = df[df["asin"].isin(selected_asins)].copy()

# Verify that selected records have unique source identifiers.
if sample["source_row_number"].isna().any():
    raise ValueError("Missing source_row_number values")

if not sample["source_row_number"].is_unique:
    raise ValueError("Duplicate source_row_number values")

print(f"Selected reviews: {len(sample):,}")
print(f"Selected products: {sample['asin'].nunique():,}")

# Run TF-IDF similarity detection
result = compute_review_similarity(
    sample,
    threshold=0.85,
)

if len(result) != len(sample):
    raise AssertionError(
        "Similarity detection changed the review count"
    )

if not result["source_row_number"].is_unique:
    raise AssertionError(
        "Similarity results contain duplicate source_row_number values"
    )

if set(result["source_row_number"]) != set(sample["source_row_number"]):
    raise AssertionError(
        "Similarity detection lost or changed source review identifiers"
    )

# Apply rule-based anomaly scoring
result = compute_rule_anomaly_score(result)
result = build_anomaly_features(result)
result = compute_ml_anomaly_score(
    result,
    contamination=0.02,
)

print("\n=== Rule-Based Anomaly Results ===")

print("Total reviews:", len(result))
print("Flagged reviews:", result["rule_anomaly_flag"].sum())

print("\nScore distribution:")
print(
    result["rule_anomaly_score"]
    .value_counts()
    .sort_index()
)

print("\nFlagged examples:")
print(
    result.loc[
        result["rule_anomaly_flag"],
        [
            "source_row_number",
            "asin",
            "body",
            "max_text_similarity",
            "is_exact_duplicate",
            "rule_anomaly_score",
        ],
    ]
    .head(10)
    .to_string(index=False, max_colwidth=70)
)

# Summary
flagged = result[result["similar_review_count"] > 0]

print("\n=== Similarity Detection Results ===")
print(f"Flagged reviews: {len(flagged):,}")
print(f"Flagged percentage: {len(flagged) / len(result):.2%}")

print("\nTop similar reviews:")
print(
    flagged[
        ["asin", "body", "max_text_similarity", "similar_review_count"]
    ]
    .sort_values("max_text_similarity", ascending=False)
    .head(10)
    .to_string(index=False, max_colwidth=75)
)

# Anomaly feature summary
print("\n=== Anomaly Feature Summary ===")

feature_columns = [
    "text_length",
    "max_text_similarity",
    "similar_review_count",
    "rating_deviation",
    "verified_purchase_numeric",
    "helpful_votes_log",
]

print(result[feature_columns].describe().round(3))

print("\nMissing feature values:")
print(result[feature_columns].isna().sum())

print("\n=== Isolation Forest Results ===")

print("ML flagged:", result["ml_anomaly_flag"].sum())
print("Rule flagged:", result["rule_anomaly_flag"].sum())

both_flagged = (
    result["ml_anomaly_flag"]
    & result["rule_anomaly_flag"]
)

print("Flagged by both:", both_flagged.sum())

print("\nTop ML anomalies:")

print(
    result[
        [
            "source_row_number",
            "asin",
            "stars",
            "text_length",
            "max_text_similarity",
            "rating_deviation",
            "ml_anomaly_score",
            "ml_anomaly_flag",
        ]
    ]
    .sort_values("ml_anomaly_score", ascending=False)
    .head(10)
    .to_string(index=False)
)

# Save results
result.to_csv(OUTPUT_PATH, index=False)

print(f"\nResults saved to: {OUTPUT_PATH}")
