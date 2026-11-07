
import pandas as pd

from nlp.isolation_forest import compute_ml_anomaly_score


DATA_PATH = "data/processed/similarity_results.csv"

df = pd.read_csv(DATA_PATH)

experiments = {
    "full": [
        "text_length",
        "max_text_similarity",
        "similar_review_count",
        "rating_deviation",
        "helpful_votes_log",
    ],
    "no_length": [
        "max_text_similarity",
        "similar_review_count",
        "rating_deviation",
        "helpful_votes_log",
    ],
    "text_only": [
        "max_text_similarity",
        "similar_review_count",
    ],
}

results = {}

for name, features in experiments.items():
    output = compute_ml_anomaly_score(
        df,
        contamination=0.02,
        feature_columns=features,
    )

    results[name] = output["ml_anomaly_flag"].to_numpy()

    print(f"\n=== {name.upper()} ===")
    print("Features:", features)
    print("Flagged:", results[name].sum())

    print(
        "Average flagged review length:",
        round(
            df.loc[
                results[name], "text_length"
            ].mean(),
            2,
        ),
    )

    print(
        "Average flagged rating deviation:",
        round(
            df.loc[
                results[name], "rating_deviation"
            ].mean(),
            3,
        ),
    )

print("\n=== Model Agreement ===")

for a, b in [
    ("full", "no_length"),
    ("full", "text_only"),
    ("no_length", "text_only"),
]:
    overlap = (results[a] & results[b]).sum()
    union = (results[a] | results[b]).sum()

    jaccard = overlap / union if union else 1.0

    print(
        f"{a} vs {b}: "
        f"overlap={overlap}, "
        f"Jaccard={jaccard:.3f}"
    )
