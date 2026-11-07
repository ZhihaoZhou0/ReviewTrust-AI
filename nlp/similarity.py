
import numpy as np
import pandas as pd

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


def compute_review_similarity(
    df: pd.DataFrame,
    threshold: float = 0.85,
    min_text_length: int = 50,
) -> pd.DataFrame:
    """
    Detect highly similar reviews within the same product.

    Only reviews with at least min_text_length characters
    participate in text similarity detection.
    """

    required = {"id", "asin", "body"}
    missing = required - set(df.columns)

    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    if not 0 <= threshold <= 1:
        raise ValueError("threshold must be between 0 and 1")

    result = df.copy().reset_index(drop=True)

    result["body"] = result["body"].fillna("").astype(str)
    result["text_length"] = result["body"].str.strip().str.len()

    result["max_text_similarity"] = 0.0
    result["similar_review_count"] = 0
    result["most_similar_review_id"] = None
    result["is_exact_duplicate"] = False

    valid_mask = result["text_length"] >= min_text_length

    for asin, group in result[valid_mask].groupby(
        "asin", sort=False
    ):
        if len(group) < 2:
            continue

        texts = group["body"].tolist()

        vectorizer = TfidfVectorizer(
            lowercase=True,
            stop_words="english",
            max_features=5000,
        )

        try:
            vectors = vectorizer.fit_transform(texts)
        except ValueError:
            continue

        similarity_matrix = cosine_similarity(vectors)
        np.fill_diagonal(similarity_matrix, 0.0)

        max_similarity = similarity_matrix.max(axis=1)
        similar_count = (
            similarity_matrix >= threshold
        ).sum(axis=1)

        nearest_positions = similarity_matrix.argmax(axis=1)
        review_ids = group["id"].to_numpy()

        result.loc[
            group.index, "max_text_similarity"
        ] = max_similarity

        result.loc[
            group.index, "similar_review_count"
        ] = similar_count

        result.loc[
            group.index, "most_similar_review_id"
        ] = review_ids[nearest_positions]

        # Exact duplicates are identified within the same ASIN.
        normalized_text = group["body"].str.strip().str.casefold()

        result.loc[
            group.index, "is_exact_duplicate"
        ] = normalized_text.duplicated(keep=False).to_numpy()

    return result
