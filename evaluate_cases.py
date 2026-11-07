
from pathlib import Path

import pandas as pd

from nlp.isolation_forest import compute_ml_anomaly_score


INPUT_PATH = Path("data/processed/similarity_results.csv")
OUTPUT_PATH = Path("data/processed/manual_review_cases.csv")

df = pd.read_csv(INPUT_PATH)

full = compute_ml_anomaly_score(df, contamination=0.02)

no_length = compute_ml_anomaly_score(
    df,
    contamination=0.02,
    feature_columns=[
        "max_text_similarity",
        "similar_review_count",
        "rating_deviation",
        "helpful_votes_log",
    ],
)

# Full model: top 10 anomalous reviews
full_cases = (
    full.sort_values("ml_anomaly_score", ascending=False)
    .head(10)
    .copy()
)
full_cases["source_model"] = "full"

# No-length model: top 10 anomalous reviews
no_length_cases = (
    no_length.sort_values("ml_anomaly_score", ascending=False)
    .head(10)
    .copy()
)
no_length_cases["source_model"] = "no_length"

# Control group: 10 reviews not flagged by either model
normal_mask = (
    ~full["ml_anomaly_flag"]
    & ~no_length["ml_anomaly_flag"]
)

normal_cases = (
    full.loc[normal_mask]
    .sample(n=10, random_state=42)
    .copy()
)
normal_cases["source_model"] = "control"

cases = pd.concat(
    [full_cases, no_length_cases, normal_cases],
    ignore_index=True,
)

# One review may be selected by multiple models.
cases["selected_by"] = cases["source_model"]

cases = cases.drop_duplicates(
    subset=["id"],
    keep="first",
).copy()

cases["manual_label"] = ""
cases["manual_reason"] = ""

columns = [
    "id",
    "asin",
    "source_model",
    "stars",
    "body",
    "text_length",
    "max_text_similarity",
    "rating_deviation",
    "ml_anomaly_score",
    "manual_label",
    "manual_reason",
]

cases = cases[columns]

OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
cases.to_csv(OUTPUT_PATH, index=False)

print("=== Manual Review Evaluation ===")
print("Total unique cases:", len(cases))
print("\nCases by source:")
print(cases["source_model"].value_counts())
print("\nSaved to:", OUTPUT_PATH)
