# DataHive Amazon Reviews Data Audit (A1, Step 1)

## Source and reproduction

- Dataset: [datahiveai/Amazon-Reviews-Dataset](https://huggingface.co/datasets/datahiveai/Amazon-Reviews-Dataset)
- Pinned revision: 2531d9083bd3aab11261eab7e69d0d0f358a6d6f
- Source files: products.csv (15,372,071 bytes) and reviews.csv (127,363,815 bytes)
- Complete statistics and SHA-256 checksums: [data-audit.json](data-audit.json)
- Keep source files in data/raw/. Git ignores this directory; do not commit review text.

Download the pinned files and repeat the audit from the repository root:

    mkdir -p data/raw
    curl -fL -o data/raw/products.csv https://huggingface.co/datasets/datahiveai/Amazon-Reviews-Dataset/resolve/2531d9083bd3aab11261eab7e69d0d0f358a6d6f/products.csv
    curl -fL -o data/raw/reviews.csv https://huggingface.co/datasets/datahiveai/Amazon-Reviews-Dataset/resolve/2531d9083bd3aab11261eab7e69d0d0f358a6d6f/reviews.csv
    python3 pipeline/audit_dataset.py --products data/raw/products.csv --reviews data/raw/reviews.csv --output docs/data-audit.json

## Actual CSV structure

| File | Rows | Source columns |
| --- | ---: | --- |
| products.csv | 2,727 | url, asin, main_image, alt_images, title, breadcrumbs, rating, number_of_ratings, description, characteristics |
| reviews.csv | 255,966 | id, asin, url, body, date, title, images, videos, stars, user_id, variation, found_helpful, verified_purchase |

The default Hugging Face dataset viewer attempts to combine these two CSV files into one split and fails because their columns differ. Read the files separately and join them on asin. Some field names in the dataset card also differ from the actual CSV headers; use the headers as the implementation contract.

## Full-dataset findings

| Check | Result |
| --- | ---: |
| Distinct product ASINs / duplicate product ASINs | 2,727 / 0 |
| Reviews linked to a product | 255,966 / 255,966 (100%) |
| Products without reviews | 38 |
| Distinct review IDs / additional rows with repeated IDs | 247,696 / 8,270 |
| Additional exactly duplicated review rows | 3,832 |
| Additional rows with a repeated (asin, id) pair | 3,842, including 10 rows with different content |
| Reviews with empty body text | 211 |
| Malformed CSV rows / invalid numeric values / invalid dates | 0 / 0 / 0 |
| Review date range | 1999-07-12 to 2025-07-17 |
| Reviews dated 2025 | 196,119 |
| verified_purchase values | 1: 253,543; empty: 2,423; 0: none |
| Reviews per product with reviews | Minimum 1, median 100, maximum 100 |
| Products with exactly 100 reviews | 2,478 / 2,689 |

Missing product fields: breadcrumbs in 75 rows and description in 3 rows. Missing review fields: variation in 43,277 rows, title in 1,333 rows, user_id in 1,333 rows, verified_purchase in 2,423 rows, and body in 211 rows. Review stars and source product ratings are both within the 1-5 range.

Three products have non-ASCII top-level category labels. The audit JSON groups those labels under an English summary key; the raw CSV values remain unchanged.

## Implications for A1 and downstream teams

1. **Keys:** products.asin can be the product primary key. Neither review id nor (asin, id) is unique. Use an internal review key, retain source_review_id and asin, remove only exact whole-row duplicates, and retain the 10 differing rows that share an (asin, id) pair.
2. **Rating definitions:** For 2,680 of the 2,689 comparable products, the source number_of_ratings differs from the number of sampled CSV reviews. Keep the source rating and the sampled-review mean as separate metrics.
3. **Sample coverage:** Exactly 2,478 products have 100 reviews each, indicating a per-product sample cap. The sampled dates and ratings do not represent each product's complete review history. Label any weighted rating as based on this sample.
4. **Suspicious signals:** verified_purchase contains only 1 or an empty value; empty does not prove an unverified purchase. The 20,549 additional rows with identical body text are text matches, not confirmed fake reviews.
5. **Source and date:** This DataHive dataset contains reviews from 2025. Do not describe it as the McAuley Lab Amazon Reviews 2023 dataset from the proposal. Show the actual source and sampled date range in the demo.

## Cleaning and schema

See [data-contract.md](data-contract.md) for cleaning rules, field mappings, and the database contract. The raw CSV files remain unchanged; the cleaning report records input, output, and removed-row counts.
