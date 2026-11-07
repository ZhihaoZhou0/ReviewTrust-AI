
"""Isolation Forest-based review anomaly detection."""

import numpy as np
import pandas as pd

from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import RobustScaler


# Default features for the full model
FEATURE_COLUMNS = [
    "text_length",
    "max_text_similarity",
    "similar_review_count",
    "rating_deviation",
    "helpful_votes_log",
]


def compute_ml_anomaly_score(
    df: pd.DataFrame,
    contamination: float = 0.02,
    feature_columns: list[str] | None = None,
) -> pd.DataFrame:
    """
    Train an Isolation Forest and score review anomalies.

    Parameters
    ----------
    df : pd.DataFrame
        Review dataset containing numerical anomaly features.

    contamination : float
        Expected proportion of anomalies.
        This is a modeling assumption, not the true fake-review rate.

    feature_columns : list[str] | None
        Features used to train the model.
        Defaults to FEATURE_COLUMNS.

    Returns
    -------
    pd.DataFrame
        Original dataset with two additional columns:
        - ml_anomaly_score: normalized anomaly score (0 to 1)
        - ml_anomaly_flag: whether the model flags the review

    Notes
    -----
    Higher anomaly scores indicate more unusual observations.
    They are not probabilities of fake reviews.
    """

    # Validate contamination
    if not 0 < contamination <= 0.5:
        raise ValueError(
            "contamination must be in (0, 0.5]"
        )

    # Select features
    if feature_columns is None:
        feature_columns = FEATURE_COLUMNS

    if not feature_columns:
        raise ValueError(
            "At least one feature is required"
        )

    # Validate required columns
    missing = set(feature_columns) - set(df.columns)

    if missing:
        raise ValueError(
            f"Missing features: {missing}"
        )

    result = df.copy()

    if len(result) < 2:
        raise ValueError(
            "At least two reviews are required"
        )

    # Convert selected features to numeric values
    X = result[feature_columns].apply(
        pd.to_numeric,
        errors="coerce",
    )

    # Replace infinite values with NaN
    X = X.replace(
        [np.inf, -np.inf],
        np.nan,
    )

    # Fill missing values using feature medians
    X = X.fillna(X.median()).fillna(0)

    # Scale features
    scaler = RobustScaler()
    X_scaled = scaler.fit_transform(X)

    # Initialize Isolation Forest
    model = IsolationForest(
        n_estimators=200,
        contamination=contamination,
        random_state=42,
        n_jobs=-1,
    )

    # Train model
    model.fit(X_scaled)

    # Calculate anomaly scores
    # Higher values indicate more unusual observations
    raw_scores = -model.score_samples(X_scaled)

    score_min = raw_scores.min()
    score_max = raw_scores.max()

    # Normalize scores to [0, 1]
    if score_max > score_min:
        normalized_scores = (
            (raw_scores - score_min)
            / (score_max - score_min)
        )
    else:
        normalized_scores = np.zeros(
            len(raw_scores)
        )

    result["ml_anomaly_score"] = normalized_scores

    # Isolation Forest:
    # -1 = anomaly
    #  1 = normal
    result["ml_anomaly_flag"] = (
        model.predict(X_scaled) == -1
    )

    return result
