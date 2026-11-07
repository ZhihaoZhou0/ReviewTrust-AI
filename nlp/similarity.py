
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

    When source_row_hash is available, compare only one
    representative per unique source record. Map similarity
    results back to all original rows for auditability.

    Source duplicates alone are not treated as evidence
    of suspicious review text.
    """

    required = {"source_row_number", "asin", "body"}
    missing = required - set(df.columns)

    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    if not 0 <= threshold <= 1:
        raise ValueError("threshold must be between 0 and 1")

    if min_text_length < 1:
        raise ValueError("min_text_length must be at least 1")

    result = df.copy().reset_index(drop=True)

    if result["source_row_number"].isna().any():
        raise ValueError("Missing source_row_number values")

    if not result["source_row_number"].is_unique:
        raise ValueError("source_row_number must be unique")

    result["body"] = result["body"].fillna("").astype(str)
    result["text_length"] = result["body"].str.strip().str.len()

    result["max_text_similarity"] = 0.0
    result["similar_review_count"] = 0
    result["most_similar_source_row_number"] = pd.NA
    result["is_exact_duplicate"] = False

    # Work with unique source records when hashes are available.
    if "source_row_hash" in result.columns:
        if (
            result["source_row_hash"].isna().any()
            or result["source_row_hash"].astype(str).str.strip().eq("").any()
        ):
            raise ValueError("source_row_hash contains missing values")

        inconsistent = (
            result.groupby("source_row_hash")[["asin", "body"]]
            .nunique(dropna=False)
            .gt(1)
            .any(axis=1)
        )

        if inconsistent.any():
            raise ValueError(
                "Identical source_row_hash values have inconsistent "
                "product or review text"
            )

        unique_reviews = result.drop_duplicates(
            subset=["source_row_hash"],
            keep="first",
        ).copy()
    else:
        unique_reviews = result.copy()

    valid_mask = (
        unique_reviews["text_length"] >= min_text_length
    )

    for _, group in unique_reviews[valid_mask].groupby(
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
        review_ids = group["source_row_number"].to_numpy()

        unique_reviews.loc[
            group.index, "max_text_similarity"
        ] = max_similarity

        unique_reviews.loc[
            group.index, "similar_review_count"
        ] = similar_count

        has_match = max_similarity > 0

        unique_reviews.loc[
            group.index[has_match],
            "most_similar_source_row_number",
        ] = review_ids[nearest_positions[has_match]]

        normalized_text = (
            group["body"].str.strip().str.casefold()
        )

        unique_reviews.loc[
            group.index, "is_exact_duplicate"
        ] = normalized_text.duplicated(
            keep=False
        ).to_numpy()

    # Restore similarity results to every original source row.
    similarity_columns = [
        "max_text_similarity",
        "similar_review_count",
        "most_similar_source_row_number",
        "is_exact_duplicate",
    ]

    if "source_row_hash" in result.columns:
        lookup = unique_reviews.set_index("source_row_hash")

        for column in similarity_columns:
            result[column] = result["source_row_hash"].map(
                lookup[column]
            )
    else:
        result[similarity_columns] = unique_reviews[
            similarity_columns
        ]

    return result
