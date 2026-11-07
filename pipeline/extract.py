from pathlib import Path
import sys
from urllib.request import urlopen

import polars as pl
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pipeline.source import snapshot_manifest, verify_file


# =====================================
# Configuration
# =====================================

REPO_ID = "datahiveai/Amazon-Reviews-Dataset"

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = PROJECT_ROOT / "data" / "raw"

# =====================================
# Extract
# =====================================

def get_local_file(filename: str) -> Path:
    """
    Use a verified local CSV or download the exact audited revision.
    """
    if filename not in {"products.csv", "reviews.csv"}:
        raise ValueError(f"Unknown source file: {filename}")
    manifest = snapshot_manifest()
    expected = manifest[filename.removesuffix(".csv")]
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    file_path = RAW_DIR / filename
    if file_path.exists():
        verify_file(file_path, expected["bytes"], expected["sha256"])
        print(f"[LOCAL] Verified {filename}")
        return file_path
    revision = manifest["source"]["revision"]
    url = (
        f"https://huggingface.co/datasets/{REPO_ID}/resolve/"
        f"{revision}/{filename}"
    )
    temporary = file_path.with_suffix(".csv.part")
    print(f"[DOWNLOAD] Fetching pinned {filename}...")
    try:
        with urlopen(url, timeout=60) as response, temporary.open("wb") as output:
            for chunk in iter(lambda: response.read(1024 * 1024), b""):
                output.write(chunk)
        verify_file(temporary, expected["bytes"], expected["sha256"])
        temporary.replace(file_path)
    finally:
        temporary.unlink(missing_ok=True)
    return file_path


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
