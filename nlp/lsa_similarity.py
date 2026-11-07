
"""LSA-based review similarity detection."""

import numpy as np
import pandas as pd

from sklearn.decomposition import TruncatedSVD
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.preprocessing import normalize


def compute_lsa_similarity(
    df: pd.DataFrame,
    n_components: int = 20,
    threshold: float = 0.85,
    min_text_length: int = 50,
) -> pd.DataFrame:
    """
    Compute within-product review similarity using
    TF-IDF + Latent Semantic Analysis (Truncated SVD).

    Scores represent similarity, not fake-review probabilities.
    """

    required = {"id", "asin", "body"}
    missing = required - set(df.columns)

    if missing:
        raise ValueError(f"Missing columns: {missing}")

    if n_components < 1:
        raise ValueError("n_components must be positive")

    if not 0 <= threshold <= 1:
        raise ValueError("threshold must be between 0 and 1")

    result = df.copy().reset_index(drop=True)

    result["body"] = result["body"].fillna("").astype(str)
    result["text_length"] = result["body"].str.strip().str.len()

    result["lsa_max_similarity"] = 0.0
    result["lsa_similar_count"] = 0
    result["lsa_matched_review_id"] = None

    valid = result["text_length"] >= min_text_length

    for asin, group in result[valid].groupby(
        "asin", sort=False
    ):
        if len(group) < 3:
            continue

        vectorizer = TfidfVectorizer(
            lowercase=True,
            stop_words="english",
            max_features=5000,
        )

        try:
            tfidf = vectorizer.fit_transform(
                group["body"]
            )
        except ValueError:
            continue

        # TruncatedSVD requires fewer components
        # than the number of available features.
        max_components = min(
            n_components,
            tfidf.shape[0] - 1,
            tfidf.shape[1] - 1,
        )

        if max_components < 1:
            continue

        svd = TruncatedSVD(
            n_components=max_components,
            random_state=42,
        )

        embeddings = svd.fit_transform(tfidf)
        embeddings = normalize(embeddings)

        similarity = cosine_similarity(embeddings)

        np.fill_diagonal(similarity, 0.0)

        # Guard against small floating-point overshoots
        similarity = np.clip(similarity, 0.0, 1.0)

        result.loc[
            group.index, "lsa_max_similarity"
        ] = similarity.max(axis=1)

        result.loc[
            group.index, "lsa_similar_count"
        ] = (similarity >= threshold).sum(axis=1)

        nearest = similarity.argmax(axis=1)
        ids = group["id"].to_numpy()

        result.loc[
            group.index, "lsa_matched_review_id"
        ] = ids[nearest]

    return result
