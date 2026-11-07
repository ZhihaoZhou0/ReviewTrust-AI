
import pandas as pd


def compute_rule_anomaly_score(
    df: pd.DataFrame,
    similarity_threshold: float = 0.85,
    min_text_length: int = 50,
) -> pd.DataFrame:
    """
    Compute an interpretable rule-based anomaly score.

    Scores range from 0 to 1.
    Higher scores indicate stronger duplicate-text signals,
    not a verified probability of fake reviews.
    """

    required = {
        "text_length",
        "max_text_similarity",
        "is_exact_duplicate",
    }

    missing = required - set(df.columns)

    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    result = df.copy()

    valid_text = result["text_length"] >= min_text_length

    high_similarity = (
        valid_text
        & (
            result["max_text_similarity"]
            >= similarity_threshold
        )
    )

    exact_duplicate = (
        valid_text
        & result["is_exact_duplicate"].fillna(False).astype(bool)
    )

    result["rule_anomaly_score"] = 0.0

    result.loc[
        high_similarity, "rule_anomaly_score"
    ] += 0.6

    result.loc[
        exact_duplicate, "rule_anomaly_score"
    ] += 0.4

    result["rule_anomaly_score"] = (
        result["rule_anomaly_score"].clip(0, 1)
    )

    result["rule_anomaly_flag"] = (
        result["rule_anomaly_score"] >= 0.6
    )

    return result
