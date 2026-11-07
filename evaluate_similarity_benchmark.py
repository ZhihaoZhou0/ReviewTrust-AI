
"""Synthetic near-duplicate benchmark for TF-IDF and LSA."""

from pathlib import Path
import re

import numpy as np
import pandas as pd

from sklearn.decomposition import TruncatedSVD
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import (
    precision_score,
    recall_score,
    f1_score,
    confusion_matrix,
)
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.preprocessing import normalize


DATA_PATH = Path("data/processed/reviews_2025_nlp.csv")
OUTPUT_PATH = Path("data/processed/similarity_benchmark.csv")

RANDOM_SEED = 42
N_POSITIVE = 200
N_NEGATIVE = 200
THRESHOLD = 0.85

rng = np.random.default_rng(RANDOM_SEED)


def create_near_duplicate(text: str) -> str:
    """Create a simple synthetic near-duplicate."""
    text = str(text).strip()

    # Remove repeated whitespace
    text = re.sub(r"\s+", " ", text)

    # Add a small phrase while retaining the original content
    return text + " Overall, this is my experience with the product."


def build_pairs(df: pd.DataFrame) -> pd.DataFrame:
    """Build synthetic positives and weakly labeled negatives."""

    valid = df[
        df["body"].notna()
        & (df["body"].astype(str).str.len() >= 80)
    ].copy()

    valid = valid.drop_duplicates(subset=["id"])

    positives = valid.sample(
        n=N_POSITIVE,
        random_state=RANDOM_SEED,
    )

    records = []

    for _, row in positives.iterrows():
        records.append({
            "text_a": row["body"],
            "text_b": create_near_duplicate(row["body"]),
            "label": 1,
            "pair_type": "synthetic_positive",
        })

    # Sample different reviews from the same product
    groups = [
        group
        for _, group in valid.groupby("asin")
        if len(group) >= 2
    ]

    for _ in range(N_NEGATIVE):
        group = groups[rng.integers(len(groups))]
        selected = group.sample(
            n=2,
            random_state=int(rng.integers(1_000_000)),
        )

        records.append({
            "text_a": selected.iloc[0]["body"],
            "text_b": selected.iloc[1]["body"],
            "label": 0,
            "pair_type": "weak_negative",
        })

    return pd.DataFrame(records)


def evaluate_method(pairs, method, dimensions=None):
    """Evaluate cosine similarity for a text representation."""

    texts = pd.concat(
        [pairs["text_a"], pairs["text_b"]],
        ignore_index=True,
    ).tolist()

    vectorizer = TfidfVectorizer(
        lowercase=True,
        stop_words="english",
        max_features=5000,
    )

    X = vectorizer.fit_transform(texts)

    if method == "lsa":
        max_components = min(
            dimensions,
            X.shape[0] - 1,
            X.shape[1] - 1,
        )

        svd = TruncatedSVD(
            n_components=max_components,
            random_state=RANDOM_SEED,
        )

        X = normalize(svd.fit_transform(X))

    n = len(pairs)

    # Compare corresponding pairs only
    similarities = np.asarray(
        X[:n].multiply(X[n:]).sum(axis=1)
        if method == "tfidf"
        else np.sum(X[:n] * X[n:], axis=1)
    ).ravel()

    similarities = np.clip(similarities, 0, 1)

    predictions = (similarities >= THRESHOLD).astype(int)
    labels = pairs["label"].to_numpy()

    tn, fp, fn, tp = confusion_matrix(
        labels,
        predictions,
        labels=[0, 1],
    ).ravel()

    return {
        "method": (
            "TF-IDF"
            if method == "tfidf"
            else f"LSA-{dimensions}"
        ),
        "precision": precision_score(
            labels, predictions, zero_division=0
        ),
        "recall": recall_score(
            labels, predictions, zero_division=0
        ),
        "f1": f1_score(
            labels, predictions, zero_division=0
        ),
        "false_positive_rate": (
            fp / (fp + tn) if fp + tn else 0
        ),
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
    }


def main():
    df = pd.read_csv(DATA_PATH, low_memory=False)

    pairs = build_pairs(df)

    print("=== Similarity Benchmark ===")
    print("Total pairs:", len(pairs))
    print(pairs["pair_type"].value_counts())

    results = [
        evaluate_method(pairs, "tfidf"),
    ]

    for dimension in [20, 40, 80]:
        results.append(
            evaluate_method(
                pairs,
                "lsa",
                dimensions=dimension,
            )
        )

    summary = pd.DataFrame(results)

    print("\n=== Evaluation Results ===")
    print(summary.round(3).to_string(index=False))

    OUTPUT_PATH.parent.mkdir(
        parents=True, exist_ok=True
    )

    summary.to_csv(OUTPUT_PATH, index=False)

    print(f"\nSaved to: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
