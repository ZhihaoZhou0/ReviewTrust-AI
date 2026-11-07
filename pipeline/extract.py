from pathlib import Path

import polars as pl
from huggingface_hub import hf_hub_download


# =====================================
# Configuration
# =====================================

REPO_ID = "datahiveai/Amazon-Reviews-Dataset"

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = PROJECT_ROOT / "data" / "raw"

RAW_DIR.mkdir(parents=True, exist_ok=True)


# =====================================
# Extract
# =====================================

def get_local_file(filename: str) -> Path:
    """
    Use local CSV if available.
    Download from Hugging Face only if missing.
    """

    file_path = RAW_DIR / filename

    if file_path.is_file() and file_path.stat().st_size > 0:
        print(f"[LOCAL] Found {filename}")
        return file_path

    print(f"[DOWNLOAD] Downloading {filename}...")

    downloaded_path = hf_hub_download(
        repo_id=REPO_ID,
        filename=filename,
        repo_type="dataset",
        local_dir=str(RAW_DIR),
    )

    return Path(downloaded_path)


def extract_data():
    """
    Extract products and reviews from local CSV files.
    Preserve all raw columns as strings.
    """

    products_path = get_local_file("products.csv")
    reviews_path = get_local_file("reviews.csv")

    print("\nReading local CSV files...")

    products = pl.read_csv(
        products_path,
        infer_schema=False,
    )

    reviews = pl.read_csv(
        reviews_path,
        infer_schema=False,
    )

    print("\n=== Extract Results ===")
    print(f"Products: {products.shape}")
    print(f"Reviews: {reviews.shape}")

    print("\nProduct columns:")
    print(products.columns)

    print("\nReview columns:")
    print(reviews.columns)

    return products, reviews


# =====================================
# Main
# =====================================

if __name__ == "__main__":

    products, reviews = extract_data()

    print("\nSample reviews:")
    print(
        reviews.select(
            ["id", "asin", "stars", "date"]
        ).head(5)
    )
