
"""Evaluate TF-IDF and LSA on manually written paraphrase pairs."""

from pathlib import Path

import numpy as np
import pandas as pd

from sklearn.decomposition import TruncatedSVD
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import (
    precision_score,
    recall_score,
    f1_score,
    confusion_matrix,
    roc_auc_score,
)
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.preprocessing import normalize


OUTPUT_DIR = Path("data/processed")
THRESHOLD = 0.85
RANDOM_SEED = 42


# Positive = similar meaning with different wording.
# Negative = different experience or conflicting meaning.
# These are illustrative, manually authored examples,
# not verified Amazon reviews or fake-review labels.
EXAMPLES = [
    (
        "The headphones sound excellent, but the battery dies quickly.",
        "Audio quality is impressive, although the charge doesn't last long.",
        1,
    ),
    (
        "This moisturizer absorbs fast and leaves my skin feeling soft.",
        "The lotion sinks in quickly and makes my face feel smooth.",
        1,
    ),
    (
        "The package arrived damaged, but the product worked perfectly.",
        "Despite the broken shipping box, the item functioned without issues.",
        1,
    ),
    (
        "The microphone captures clear voices with very little background noise.",
        "Speech recordings are crisp and unwanted sounds are barely noticeable.",
        1,
    ),
    (
        "These shoes fit comfortably, but the soles wear out too fast.",
        "The sneakers feel great on my feet, though the bottoms deteriorate quickly.",
        1,
    ),
    (
        "The camera takes sharp pictures even in low light.",
        "Photos remain detailed when shooting in dim environments.",
        1,
    ),
    (
        "The blender is powerful but extremely loud.",
        "It crushes ingredients easily, although the noise is excessive.",
        1,
    ),
    (
        "This sunscreen feels lightweight and does not leave a white cast.",
        "The sun protection cream is barely noticeable and leaves no pale residue.",
        1,
    ),
    (
        "The charger stopped working after only two weeks.",
        "The power adapter failed before I had used it for a month.",
        1,
    ),
    (
        "The keyboard is responsive and comfortable for long typing sessions.",
        "Typing for hours feels pleasant because the keys react quickly.",
        1,
    ),
    (
        "The headphones sound excellent, but the battery dies quickly.",
        "The headphones have terrible audio quality, but the battery lasts all day.",
        0,
    ),
    (
        "This moisturizer absorbs fast and leaves my skin feeling soft.",
        "The cream feels greasy and causes irritation after application.",
        0,
    ),
    (
        "The package arrived damaged, but the product worked perfectly.",
        "The delivery box was intact, but the item was completely defective.",
        0,
    ),
    (
        "The microphone captures clear voices with very little background noise.",
        "The microphone records muffled speech and picks up constant static.",
        0,
    ),
    (
        "These shoes fit comfortably, but the soles wear out too fast.",
        "The shoes are uncomfortable, although the soles are extremely durable.",
        0,
    ),
    (
        "The camera takes sharp pictures even in low light.",
        "Images are blurry whenever the room is dark.",
        0,
    ),
    (
        "The blender is powerful but extremely loud.",
        "The blender struggles with soft fruit but operates almost silently.",
        0,
    ),
    (
        "This sunscreen feels lightweight and does not leave a white cast.",
        "The sunscreen is heavy and leaves a noticeable white residue.",
        0,
    ),
    (
        "The charger stopped working after only two weeks.",
        "The charger has worked reliably for several years.",
        0,
    ),
    (
        "The keyboard is responsive and comfortable for long typing sessions.",
        "The keys frequently miss inputs and typing becomes painful.",
        0,
    ),
]


def build_dataset():
    return pd.DataFrame(
        EXAMPLES,
        columns=["text_a", "text_b", "label"],
    )


def compute_scores(df, method, dimensions=None):
    texts = pd.concat(
        [df["text_a"], df["text_b"]],
        ignore_index=True,
    ).tolist()

    vectorizer = TfidfVectorizer(
        lowercase=True,
        stop_words="english",
        ngram_range=(1, 2),
    )

    X = vectorizer.fit_transform(texts)

    if method == "lsa":
        k = min(
            dimensions,
            X.shape[0] - 1,
            X.shape[1] - 1,
        )

        svd = TruncatedSVD(
            n_components=k,
            random_state=RANDOM_SEED,
        )

        X = normalize(svd.fit_transform(X))

    n = len(df)

    if method == "tfidf":
        scores = np.asarray(
            X[:n].multiply(X[n:]).sum(axis=1)
        ).ravel()
    else:
        scores = np.sum(
            X[:n] * X[n:],
            axis=1,
        )

    return np.clip(scores, 0, 1)


def evaluate(df, scores, name):
    labels = df["label"].to_numpy()
    predictions = (scores >= THRESHOLD).astype(int)

    tn, fp, fn, tp = confusion_matrix(
        labels,
        predictions,
        labels=[0, 1],
    ).ravel()

    return {
        "model": name,
        "precision": precision_score(
            labels, predictions, zero_division=0
        ),
        "recall": recall_score(
            labels, predictions, zero_division=0
        ),
        "f1": f1_score(
            labels, predictions, zero_division=0
        ),
        "roc_auc": roc_auc_score(labels, scores),
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
        "positive_mean_similarity": scores[labels == 1].mean(),
        "negative_mean_similarity": scores[labels == 0].mean(),
    }


def main():
    df = build_dataset()

    print("=== Hard Paraphrase Benchmark ===")
    print("Total pairs:", len(df))
    print("Positive pairs:", int(df["label"].sum()))
    print("Negative pairs:", int((df["label"] == 0).sum()))

    results = []
    detailed = df.copy()

    configurations = [
        ("TF-IDF", "tfidf", None),
        ("LSA-20", "lsa", 20),
        ("LSA-40", "lsa", 40),
        ("LSA-80", "lsa", 80),
    ]

    for name, method, dimensions in configurations:
        scores = compute_scores(df, method, dimensions)

        detailed[name + "_similarity"] = scores

        results.append(
            evaluate(df, scores, name)
        )

    summary = pd.DataFrame(results)

    print("\n=== Model Comparison ===")
    print(summary.round(3).to_string(index=False))

    print("\n=== Positive Pair Similarities ===")
    print(
        detailed[detailed["label"] == 1][
            [
                "TF-IDF_similarity",
                "LSA-20_similarity",
                "LSA-40_similarity",
                "LSA-80_similarity",
            ]
        ].round(3).to_string(index=False)
    )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    summary.to_csv(
        OUTPUT_DIR / "hard_paraphrase_summary.csv",
        index=False,
    )

    detailed.to_csv(
        OUTPUT_DIR / "hard_paraphrase_details.csv",
        index=False,
    )

    print("\nResults saved to data/processed/")


if __name__ == "__main__":
    main()
