
import pandas as pd

df = pd.read_csv("data/raw/reviews_2025.csv", low_memory=False)

# Review IDs appearing more than once
duplicate_rows = df[
    df.duplicated(subset=["id"], keep=False)
].copy()

print("=== Duplicate Review ID Analysis ===")
print(f"Total rows: {len(df):,}")
print(f"Rows with repeated IDs: {len(duplicate_rows):,}")
print(f"Unique repeated IDs: {duplicate_rows['id'].nunique():,}")

# Count fully identical records
print(
    "Fully identical rows:",
    df.duplicated(keep=False).sum()
)

# Check whether a repeated ID maps to different products
asin_conflicts = (
    duplicate_rows.groupby("id")["asin"]
    .nunique(dropna=False)
)

print(
    "IDs associated with multiple ASINs:",
    (asin_conflicts > 1).sum()
)

# Check whether repeated IDs contain different review texts
text_conflicts = (
    duplicate_rows.groupby("id")["body"]
    .nunique(dropna=False)
)

print(
    "IDs associated with different texts:",
    (text_conflicts > 1).sum()
)

# Check rating conflicts if the field is available
if "stars" in df.columns:
    rating_conflicts = (
        duplicate_rows.groupby("id")["stars"]
        .nunique(dropna=False)
    )

    print(
        "IDs associated with different ratings:",
        (rating_conflicts > 1).sum()
    )

print("\n=== Example Duplicate IDs ===")

print(
    duplicate_rows[
        ["id", "asin", "body"]
    ]
    .head(10)
    .to_string(index=False, max_colwidth=70)
)
