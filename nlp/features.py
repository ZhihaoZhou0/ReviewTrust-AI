
import numpy as np
import pandas as pd


def build_anomaly_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Build numerical features for unsupervised anomaly detection.
    """

    required = {
        "asin",
        "stars",
        "text_length",
        "max_text_similarity",
        "similar_review_count",
        "verified_purchase",
        "found_helpful",
    }

    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Missing columns: {missing}")

    result = df.copy()

    result["stars"] = pd.to_numeric(
        result["stars"], errors="coerce"
    )

    # Product-level average rating
    result["product_avg_rating"] = (
        result.groupby("asin")["stars"].transform("mean")
    )

    result["rating_deviation"] = (
        result["stars"] - result["product_avg_rating"]
    ).abs()


    # Normalize verified purchase values
    verified = (
        result["verified_purchase"]
        .astype("string")
        .str.strip()
        .str.lower()
    )

    result["verified_purchase_numeric"] = verified.map({
        "true": 1,
        "false": 0,
        "1": 1,
        "1.0": 1,
        "0": 0,
        "0.0": 0,
    }).astype(float)

    # Keep missing values distinguishable
    result["verified_purchase_missing"] = (
        result["verified_purchase_numeric"].isna().astype(int)
)


    # Helpful votes
    result["helpful_votes"] = pd.to_numeric(
        result["found_helpful"], errors="coerce"
    ).fillna(0).clip(lower=0)

    # Reduce extreme helpful-vote values
    result["helpful_votes_log"] = np.log1p(
        result["helpful_votes"]
    )

    return result
