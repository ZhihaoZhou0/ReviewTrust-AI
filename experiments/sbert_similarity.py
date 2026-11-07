
"""Compare TF-IDF and SBERT on real Amazon reviews.

Exploratory experiment only: does not change B1 reliability scores.
"""

from pathlib import Path

import numpy as np
import pandas as pd
import torch
from sentence_transformers import SentenceTransformer
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


DATA_PATH = Path("data/processed/reviews_b1_nlp.csv")
OUTPUT_DIR = Path("data/processed/sbert_experiment")

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

N_PRODUCTS = 50
MAX_REVIEWS_PER_PRODUCT = 100
MIN_TEXT_LENGTH = 50
RANDOM_STATE = 42

# Exploratory thresholds, not calibrated classification cutoffs.
TFIDF_THRESHOLD = 0.85
SBERT_THRESHOLD = 0.80


def load_sample():
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
    # Remove Amazon media placeholders before computing similarity.
    df["body"] = (
        df["body"]
        .astype(str)
        .str.replace(
            r"The media could not be loaded\.",
            "",
            regex=True,
            case=False,
        )
        .str.replace(r"\s+", " ", regex=True)
        .str.strip()
    )

    df = df[df["body"].str.len() >= MIN_TEXT_LENGTH]

    # Remove duplicate source records before comparison.
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


def compare_product(group, model):
    texts = group["body"].tolist()
    n = len(texts)

    if n < 2:
        return []

    # TF-IDF lexical similarity.
    tfidf = TfidfVectorizer(
        stop_words="english",
        ngram_range=(1, 2),
    )
    tfidf_vectors = tfidf.fit_transform(texts)
    tfidf_sim = cosine_similarity(tfidf_vectors)

    # SBERT semantic similarity, computed on GPU if available.
    embeddings = model.encode(
        texts,
        batch_size=64,
        normalize_embeddings=True,
        convert_to_numpy=True,
        show_progress_bar=False,
    )
    sbert_sim = embeddings @ embeddings.T

    rows = []
    asin = group["asin"].iloc[0]

    # Compare unique pairs within the same product.
    for i in range(n):
        for j in range(i + 1, n):
            tf_score = float(tfidf_sim[i, j])
            sb_score = float(sbert_sim[i, j])

            rows.append({
                "asin": asin,
                "source_row_number_a": group.iloc[i]["source_row_number"],
                "source_row_number_b": group.iloc[j]["source_row_number"],
                "text_a": texts[i],
                "text_b": texts[j],
                "tfidf_similarity": tf_score,
                "sbert_similarity": sb_score,
                "similarity_gap": sb_score - tf_score,
                "tfidf_high": tf_score >= TFIDF_THRESHOLD,
                "sbert_high": sb_score >= SBERT_THRESHOLD,
            })

    return rows


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    sample = load_sample()

    device = "cuda" if torch.cuda.is_available() else "cpu"
    print("Device:", device)
    print("Loading model:", MODEL_NAME)

    model = SentenceTransformer(MODEL_NAME, device=device)

    all_results = []

    groups = list(sample.groupby("asin", sort=True))

    for idx, (_, group) in enumerate(groups, start=1):
        results = compare_product(group.reset_index(drop=True), model)
        all_results.extend(results)

        if idx % 10 == 0 or idx == len(groups):
            print(f"Processed {idx}/{len(groups)} products")

    df = pd.DataFrame(all_results)

    if df.empty:
        print("No review pairs available.")
        return

    print("\n=== Similarity Comparison ===")
    print("Total review pairs:", len(df))

    print(
        "Mean TF-IDF similarity:",
        round(df["tfidf_similarity"].mean(), 4),
    )
    print(
        "Mean SBERT similarity:",
        round(df["sbert_similarity"].mean(), 4),
    )

    print(
        "TF-IDF high-similarity pairs:",
        int(df["tfidf_high"].sum()),
    )
    print(
        "SBERT high-similarity pairs:",
        int(df["sbert_high"].sum()),
    )

    # High SBERT similarity but low lexical similarity.
    candidates = df[
        (df["sbert_high"])
        & (~df["tfidf_high"])
    ].copy()

    candidates = candidates.sort_values(
        "similarity_gap",
        ascending=False,
    )

    print(
        "SBERT-only candidate pairs:",
        len(candidates),
    )

    # Save all pair scores and top candidates for manual review.
    df.to_csv(
        OUTPUT_DIR / "all_pair_similarities.csv",
        index=False,
    )

    candidates.head(200).to_csv(
        OUTPUT_DIR / "sbert_only_candidates.csv",
        index=False,
    )

    summary = pd.DataFrame([{
        "products": sample["asin"].nunique(),
        "reviews": len(sample),
        "pairs": len(df),
        "tfidf_mean": df["tfidf_similarity"].mean(),
        "sbert_mean": df["sbert_similarity"].mean(),
        "tfidf_high_pairs": int(df["tfidf_high"].sum()),
        "sbert_high_pairs": int(df["sbert_high"].sum()),
        "sbert_only_pairs": len(candidates),
    }])

    summary.to_csv(
        OUTPUT_DIR / "summary.csv",
        index=False,
    )

    print("\nResults saved to:", OUTPUT_DIR)
    print("Experiment completed.")


if __name__ == "__main__":
    main()
