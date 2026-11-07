
from pathlib import Path
import pandas as pd


INPUT_PATH = Path("data/raw/reviews_2025.csv")
OUTPUT_DIR = Path("data/processed")

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

df = pd.read_csv(INPUT_PATH, low_memory=False)

print("=== NLP Data Preparation ===")
print(f"Original rows: {len(df):,}")

# Preserve all rows involving repeated review IDs
duplicate_ids = df.duplicated(
    subset=["id"],
    keep=False,
)

quarantine = df[duplicate_ids].copy()

# Keep one deterministic representative per review ID.
# This is a modeling view, not a correction of source data.
clean = df.drop_duplicates(
    subset=["id"],
    keep="first",
).copy()

print(f"Repeated-ID rows for investigation: {len(quarantine):,}")
print(f"Rows in NLP modeling view: {len(clean):,}")
print(f"Rows excluded from modeling view: {len(df) - len(clean):,}")

# Save both datasets
clean.to_csv(
    OUTPUT_DIR / "reviews_2025_nlp.csv",
    index=False,
)

quarantine.to_csv(
    OUTPUT_DIR / "duplicate_review_ids.csv",
    index=False,
)

print("\nFiles saved:")
print("data/processed/reviews_2025_nlp.csv")
print("data/processed/duplicate_review_ids.csv")

# Validate uniqueness
assert clean["id"].is_unique
print("\nValidation passed: review IDs are unique.")
