
"""Evaluate the effect of LSA dimensionality on review similarity."""

from pathlib import Path

import pandas as pd

from nlp.lsa_similarity import compute_lsa_similarity


DATA_PATH = Path("data/processed/reviews_2025_nlp.csv")
OUTPUT_PATH = Path("data/processed/lsa_dimension_results.csv")

df = pd.read_csv(DATA_PATH, low_memory=False)

selected_asins = (
    df.groupby("asin")
    .size()
    .sort_values(ascending=False)
    .head(50)
    .index
)

sample = df[df["asin"].isin(selected_asins)].copy()

dimensions = [10, 20, 40, 60, 80]
records = []

print("=== LSA Dimension Experiment ===")
print("Reviews:", len(sample))
print("Products:", sample["asin"].nunique())

for dimension in dimensions:
    print(f"\nRunning LSA with {dimension} dimensions...")

    result = compute_lsa_similarity(
        sample,
        n_components=dimension,
        threshold=0.85,
        min_text_length=50,
    )

    flagged = result["lsa_similar_count"] > 0

    records.append({
        "dimensions": dimension,
        "flagged_reviews": int(flagged.sum()),
        "flagged_percentage": round(
            flagged.mean() * 100, 3
        ),
        "mean_similarity": round(
            result["lsa_max_similarity"].mean(), 4
        ),
        "median_similarity": round(
            result["lsa_max_similarity"].median(), 4
        ),
        "max_similarity": round(
            result["lsa_max_similarity"].max(), 4
        ),
    })

summary = pd.DataFrame(records)

print("\n=== Dimension Comparison ===")
print(summary.to_string(index=False))

OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
summary.to_csv(OUTPUT_PATH, index=False)

print(f"\nSaved to: {OUTPUT_PATH}")
