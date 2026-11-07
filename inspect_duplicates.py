
import pandas as pd

df = pd.read_csv("data/processed/similarity_results.csv")

flagged = df[df["similar_review_count"] > 0].copy()

print("=== Duplicate Diagnostics ===")
print("Total flagged:", len(flagged))

print(
    "Duplicate review IDs:",
    df.duplicated(subset=["id"], keep=False).sum()
)

print(
    "Exact text duplicates among flagged:",
    flagged["is_exact_duplicate"].sum()
)

print(
    "Near duplicates (not exact):",
    (
        flagged["similar_review_count"].gt(0)
        & ~flagged["is_exact_duplicate"].astype(bool)
    ).sum()
)

print("\n=== Matched Review Examples ===")

lookup = df.set_index("id")["body"].to_dict()

examples = flagged.head(5)

for _, row in examples.iterrows():
    print("\nReview ID:", row["id"])
    print("Matched ID:", row["most_similar_review_id"])
    print("Similarity:", row["max_text_similarity"])
    print("Original:", str(row["body"])[:200])
    print(
        "Matched:",
        str(lookup.get(row["most_similar_review_id"], ""))[:200]
    )
