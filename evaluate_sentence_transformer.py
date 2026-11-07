
"""Evaluate sentence embeddings on the hard paraphrase benchmark."""

from pathlib import Path

import numpy as np
import pandas as pd

from sentence_transformers import SentenceTransformer
from sklearn.metrics import (
    precision_score,
    recall_score,
    f1_score,
    roc_auc_score,
    confusion_matrix,
)


DATA_PATH = Path(
    "data/processed/hard_paraphrase_details.csv"
)

OUTPUT_PATH = Path(
    "data/processed/sentence_transformer_results.csv"
)

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

# Exploratory threshold, not calibrated on a validation set.
THRESHOLD = 0.75


def main():
    df = pd.read_csv(DATA_PATH)

    print("=== Sentence Transformer Evaluation ===")
    print("Loading model:", MODEL_NAME)

    model = SentenceTransformer(MODEL_NAME)

    texts_a = df["text_a"].astype(str).tolist()
    texts_b = df["text_b"].astype(str).tolist()

    embeddings_a = model.encode(
        texts_a,
        normalize_embeddings=True,
        show_progress_bar=False,
    )

    embeddings_b = model.encode(
        texts_b,
        normalize_embeddings=True,
        show_progress_bar=False,
    )

    similarities = np.sum(
        embeddings_a * embeddings_b,
        axis=1,
    )

    similarities = np.clip(similarities, -1, 1)

    labels = df["label"].to_numpy()
    predictions = (
        similarities >= THRESHOLD
    ).astype(int)

    tn, fp, fn, tp = confusion_matrix(
        labels,
        predictions,
        labels=[0, 1],
    ).ravel()

    print("\n=== Results ===")
    print("Threshold:", THRESHOLD)

    print(
        "Precision:",
        round(
            precision_score(
                labels,
                predictions,
                zero_division=0,
            ),
            3,
        ),
    )

    print(
        "Recall:",
        round(
            recall_score(
                labels,
                predictions,
                zero_division=0,
            ),
            3,
        ),
    )

    print(
        "F1:",
        round(
            f1_score(
                labels,
                predictions,
                zero_division=0,
            ),
            3,
        ),
    )

    print(
        "ROC-AUC:",
        round(
            roc_auc_score(
                labels,
                similarities,
            ),
            3,
        ),
    )

    print("TP:", tp)
    print("FP:", fp)
    print("FN:", fn)
    print("TN:", tn)

    print(
        "\nPositive mean similarity:",
        round(similarities[labels == 1].mean(), 3),
    )

    print(
        "Negative mean similarity:",
        round(similarities[labels == 0].mean(), 3),
    )

    df["embedding_similarity"] = similarities
    df["embedding_prediction"] = predictions

    OUTPUT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    df.to_csv(OUTPUT_PATH, index=False)

    print("\n=== Pair Similarities ===")

    print(
        df[
            [
                "label",
                "embedding_similarity",
                "text_a",
                "text_b",
            ]
        ].to_string(
            index=False,
            max_colwidth=45,
        )
    )

    print(f"\nSaved to: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
