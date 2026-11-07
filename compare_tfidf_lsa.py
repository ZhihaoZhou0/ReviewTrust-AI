
"""Compare TF-IDF and LSA review similarity."""

from pathlib import Path

import pandas as pd

from nlp.similarity import compute_review_similarity
from nlp.lsa_similarity import compute_lsa_similarity


DATA_PATH = Path("data/processed/reviews_2025_nlp.csv")
OUTPUT_PATH = Path("data/processed/tfidf_lsa_comparison.csv")

# Load cleaned reviews
df = pd.read_csv(DATA_PATH, low_memory=False)

# Select the same 50 products used in previous experiments
selected_asins = (
    df.groupby("asin")
    .size()
    .sort_values(ascending=False)
    .head(50)
    .index
)

sample = df[df["asin"].isin(selected_asins)].copy()

print("=== Dataset ===")
print(f"Reviews: {len(sample):,}")
print(f"Products: {sample['asin'].nunique():,}")

# Baseline: TF-IDF
print("\nRunning TF-IDF...")
tfidf_result = compute_review_similarity(
    sample,
    threshold=0.85,
    min_text_length=50,
)

# LSA
print("Running LSA...")
lsa_result = compute_lsa_similarity(
    sample,
    n_components=20,
    threshold=0.85,
    min_text_length=50,
)

# Combine results using row order
result = tfidf_result.copy()

result["lsa_max_similarity"] = (
    lsa_result["lsa_max_similarity"].to_numpy()
)

result["lsa_similar_count"] = (
    lsa_result["lsa_similar_count"].to_numpy()
)

result["lsa_matched_review_id"] = (
    lsa_result["lsa_matched_review_id"].to_numpy()
)

# Flags
result["tfidf_flag"] = result["similar_review_count"] > 0
result["lsa_flag"] = result["lsa_similar_count"] > 0

both = result["tfidf_flag"] & result["lsa_flag"]
either = result["tfidf_flag"] | result["lsa_flag"]

print("\n=== Comparison Results ===")

print("TF-IDF flagged:", result["tfidf_flag"].sum())
print("LSA flagged:", result["lsa_flag"].sum())
print("Flagged by both:", both.sum())

print(
    "Jaccard similarity:",
    round(both.sum() / either.sum(), 3)
    if either.sum() else 1.0,
)

print("\n=== Similarity Statistics ===")

print(
    result[
        ["max_text_similarity", "lsa_max_similarity"]
    ].describe().round(3)
)

print("\n=== LSA-Only Examples ===")

lsa_only = result[
    result["lsa_flag"] & ~result["tfidf_flag"]
]

print(
    lsa_only[
        [
            "id",
            "asin",
            "body",
            "max_text_similarity",
            "lsa_max_similarity",
        ]
    ]
    .sort_values("lsa_max_similarity", ascending=False)
    .head(10)
    .to_string(index=False, max_colwidth=75)
)

# Save comparison
OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
result.to_csv(OUTPUT_PATH, index=False)

print(f"\nSaved to: {OUTPUT_PATH}")
