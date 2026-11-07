
import pandas as pd

df = pd.read_csv("data/processed/similarity_results.csv")

flagged = df[df["similar_review_count"] > 0].copy()

flagged["text_length"] = (
    flagged["body"].fillna("").astype(str).str.len()
)

print("=== Flagged Review Length ===")
print(flagged["text_length"].describe())

print("\n=== Short Flagged Reviews ===")
print("Under 20 chars:", (flagged["text_length"] < 20).sum())
print("Under 50 chars:", (flagged["text_length"] < 50).sum())

print("\n=== Exact Duplicate Texts ===")

# Only count duplicate text within the same product.
exact_duplicates = flagged.duplicated(
    subset=["asin", "body"],
    keep=False,
)

print("Exact duplicate reviews:", exact_duplicates.sum())

print("\n=== Similarity Distribution ===")
print(
    flagged["max_text_similarity"].describe()
)

print("\n=== Examples of Short Flagged Reviews ===")
print(
    flagged.loc[
        flagged["text_length"] < 50,
        ["asin", "body", "max_text_similarity"]
    ]
    .head(15)
    .to_string(index=False)
)
