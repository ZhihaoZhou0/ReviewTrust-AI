
"""Fixed-sample SBERT ablation for Amazon media placeholder cleaning.

Exploratory analysis only. Does not modify B1 reliability scores.
"""

from pathlib import Path

import numpy as np
import pandas as pd
import torch
from sentence_transformers import SentenceTransformer


DATA_PATH = Path("data/processed/reviews_b1_nlp.csv")
OUTPUT_DIR = Path("data/processed/sbert_cleaning_ablation")

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

N_PRODUCTS = 50
MAX_REVIEWS_PER_PRODUCT = 100
MIN_TEXT_LENGTH = 50
RANDOM_STATE = 42
SBERT_THRESHOLD = 0.80

MEDIA_MARKER = r"The media could not be loaded\."


def clean_text(series):
    return (
        series.astype(str)
        .str.replace(MEDIA_MARKER, "", regex=True, case=False)
        .str.replace(r"\s+", " ", regex=True)
        .str.strip()
    )


def load_fixed_sample():
    print("Loading Amazon reviews...")

    df = pd.read_csv(
        DATA_PATH,
        usecols=[
            "asin",
            "body",
            "source_row_hash",
            "source_row_number",
        ],
    )

    df = df.dropna(subset=["asin", "body"]).copy()

    df["original_text"] = (
        df["body"].astype(str).str.strip()
    )
    df["cleaned_text"] = clean_text(df["original_text"])

    # Apply the same eligibility criteria to both conditions.
    df = df[
        (df["original_text"].str.len() >= MIN_TEXT_LENGTH)
        & (df["cleaned_text"].str.len() >= MIN_TEXT_LENGTH)
    ].copy()

    df = df.drop_duplicates(subset=["source_row_hash"])

    counts = df.groupby("asin").size()
    eligible = counts[counts >= 2].index.to_numpy()

    rng = np.random.default_rng(RANDOM_STATE)

    selected = rng.choice(
        eligible,
        size=min(N_PRODUCTS, len(eligible)),
        replace=False,
    )

    sample = df[df["asin"].isin(selected)].copy()

    sample = (
        sample.groupby("asin", group_keys=False)
        .head(MAX_REVIEWS_PER_PRODUCT)
        .reset_index(drop=True)
    )

    print("Selected products:", sample["asin"].nunique())
    print("Selected reviews:", len(sample))

    return sample


def encode_similarity(model, texts):
    embeddings = model.encode(
        texts,
        batch_size=64,
        normalize_embeddings=True,
        convert_to_numpy=True,
        show_progress_bar=False,
    )

    return embeddings @ embeddings.T


def compare_product(group, model):
    original = group["original_text"].tolist()
    cleaned = group["cleaned_text"].tolist()

    n = len(group)

    if n < 2:
        return []

    original_sim = encode_similarity(model, original)
    cleaned_sim = encode_similarity(model, cleaned)

    asin = group["asin"].iloc[0]
    rows = []

    for i in range(n):
        for j in range(i + 1, n):
            before = float(original_sim[i, j])
            after = float(cleaned_sim[i, j])

            rows.append({
                "asin": asin,
                "source_row_number_a": group.iloc[i]["source_row_number"],
                "source_row_number_b": group.iloc[j]["source_row_number"],
                "original_text_a": original[i],
                "original_text_b": original[j],
                "cleaned_text_a": cleaned[i],
                "cleaned_text_b": cleaned[j],
                "similarity_before": before,
                "similarity_after": after,
                "similarity_change": after - before,
                "high_before": before >= SBERT_THRESHOLD,
                "high_after": after >= SBERT_THRESHOLD,
            })

    return rows


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    sample = load_fixed_sample()

    device = "cuda" if torch.cuda.is_available() else "cpu"
    print("Device:", device)
    print("Loading model:", MODEL_NAME)

    model = SentenceTransformer(MODEL_NAME, device=device)

    all_results = []
    groups = list(sample.groupby("asin", sort=True))

    for idx, (_, group) in enumerate(groups, start=1):
        results = compare_product(
            group.reset_index(drop=True),
            model,
        )
        all_results.extend(results)

        if idx % 10 == 0 or idx == len(groups):
            print(f"Processed {idx}/{len(groups)} products")

    df = pd.DataFrame(all_results)

    if df.empty:
        print("No review pairs available.")
        return

    before_count = int(df["high_before"].sum())
    after_count = int(df["high_after"].sum())

    removed = df[
        df["high_before"] & ~df["high_after"]
    ].copy()

    added = df[
        ~df["high_before"] & df["high_after"]
    ].copy()

    unchanged_high = df[
        df["high_before"] & df["high_after"]
    ].copy()

    print("\n=== Fixed-Sample Cleaning Ablation ===")
    print("Total review pairs:", len(df))

    print(
        "Mean similarity before:",
        round(df["similarity_before"].mean(), 4),
    )
    print(
        "Mean similarity after:",
        round(df["similarity_after"].mean(), 4),
    )

    print("High-similarity pairs before:", before_count)
    print("High-similarity pairs after:", after_count)
    print("No longer flagged:", len(removed))
    print("Newly flagged:", len(added))
    print("Flagged in both:", len(unchanged_high))

    print(
        "Mean similarity change:",
        round(df["similarity_change"].mean(), 4),
    )

    # Full pair-level comparison.
    df.to_csv(
        OUTPUT_DIR / "all_pair_comparisons.csv",
        index=False,
    )

    # Largest decreases after cleaning.
    removed.sort_values(
        "similarity_change",
        ascending=True,
    ).head(200).to_csv(
        OUTPUT_DIR / "removed_candidates.csv",
        index=False,
    )

    # Newly flagged pairs.
    added.sort_values(
        "similarity_change",
        ascending=False,
    ).head(200).to_csv(
        OUTPUT_DIR / "added_candidates.csv",
        index=False,
    )

    summary = pd.DataFrame([{
        "products": sample["asin"].nunique(),
        "reviews": len(sample),
        "pairs": len(df),
        "mean_before": df["similarity_before"].mean(),
        "mean_after": df["similarity_after"].mean(),
        "high_before": before_count,
        "high_after": after_count,
        "no_longer_flagged": len(removed),
        "newly_flagged": len(added),
        "flagged_in_both": len(unchanged_high),
    }])

    summary.to_csv(
        OUTPUT_DIR / "summary.csv",
        index=False,
    )

    print("\nResults saved to:", OUTPUT_DIR)
    print("Experiment completed.")


if __name__ == "__main__":
    main()
