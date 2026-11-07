from pathlib import Path
import pandas as pd

URL = (
    "https://huggingface.co/datasets/"
    "datahiveai/Amazon-Reviews-Dataset/resolve/main/reviews.csv"
)

output_dir = Path("data/raw")
output_dir.mkdir(parents=True, exist_ok=True)

print("Downloading Amazon reviews from Hugging Face...")

df = pd.read_csv(URL, low_memory=False)

df["parsed_date"] = pd.to_datetime(
    df["date"],
    errors="coerce",
    utc=True,
)

df_2025 = df[df["parsed_date"].dt.year == 2025].copy()

output_path = output_dir / "reviews_2025.csv"
df_2025.to_csv(output_path, index=False)

print(f"Total source reviews: {len(df):,}")
print(f"2025 reviews: {len(df_2025):,}")
print(f"Unique products: {df_2025['asin'].nunique():,}")
print(f"Saved to: {output_path}")