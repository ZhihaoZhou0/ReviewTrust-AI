# A1 Cleaning Rules and PostgreSQL Data Contract

This contract uses pinned DataHive revision 2531d9083bd3aab11261eab7e69d0d0f358a6d6f. See [data-audit.md](data-audit.md) for source profiling and [cleaning-report.json](cleaning-report.json) for cleaning counts.

## Run the cleaner

Run from the repository root:

    python3 pipeline/clean_dataset.py --products data/raw/products.csv --reviews data/raw/reviews.csv --output-dir data/processed --report docs/cleaning-report.json

The outputs are data/processed/products_clean.csv and data/processed/reviews_clean.csv. The source files are unchanged, and Git ignores data/processed/. source_row_number is the one-based CSV record number, not the physical line number, because review text may contain line breaks. It is an ingestion key within this pinned source revision. source_row_hash is a SHA-256 digest of the source CSV field values in source-column order. Equal hashes are retained as repeated observations; they are not fraud labels.

This snapshot retains all 2,727 products and all 255,966 source reviews. It includes 3,832 additional review rows with exactly repeated CSV field values. No source rows were rejected. If future input has missing required fields, out-of-range values, invalid dates or JSON, or orphan ASINs, the report records counts by rejection reason.

## Field mapping and rules

| Source field | Database field | Rule |
| --- | --- | --- |
| products.asin | reviewtrust.products.asin | Uppercase, ten alphanumeric characters; product primary key |
| products.title | title | Required; trim surrounding whitespace |
| products.rating | source_rating | Source product-page rating, 1-5; separate from the sample mean |
| products.number_of_ratings | source_rating_count | Source product-page rating count; separate from sampled review count |
| products.breadcrumbs | category_breadcrumbs | Nullable; retain the source category path |
| products.alt_images, characteristics | Same names, jsonb | Require a JSON array and JSON object, respectively |
| reviews.id | source_review_id | Required but not unique; cannot serve as the primary key |
| reviews.asin | asin | Must reference products.asin |
| reviews.body | body | Preserve nonempty source text; store blank text as NULL without dropping the rating |
| reviews.date | review_date | Parse the source format into a PostgreSQL date |
| reviews.stars | stars | Integer from 1 to 5 |
| reviews.verified_purchase | verified_purchase | 1/true becomes TRUE, 0/false becomes FALSE, and empty becomes NULL; NULL is not FALSE |
| reviews.found_helpful | found_helpful | Nonnegative integer |
| reviews.images, videos | Same names, jsonb | Require JSON arrays |
| reviews.variation | variation | Plain text; source values are not JSON |

Other URLs, titles, descriptions, and user IDs remain nullable text. The reviews table uses an internal review_pk primary key. Neither source_row_hash nor (asin, source_review_id) is unique. source_row_number is unique only to prevent re-importing the same CSV position; 10 rows have differing content despite sharing an (asin, source_review_id) pair. loaded_at records database load time, not review publication time. See [schema.sql](../database/schema.sql) for the table definitions.

## Query definitions for downstream teams

The following query computes the mean from every sampled source review row, including repeated content, and keeps it separate from the source product-page rating:

    SELECT p.asin, p.title, p.source_rating, p.source_rating_count,
           count(r.review_pk) AS sample_review_count,
           round(avg(r.stars), 2) AS sample_rating
    FROM reviewtrust.products AS p
    LEFT JOIN reviewtrust.reviews AS r ON r.asin = p.asin
    GROUP BY p.asin;

- **Team B:** Use reviews with body IS NOT NULL for text similarity and Pros & Cons. Keep repeated-content reviews in similarity, anomaly, and review-volume analysis; do not deduplicate by content hash or source review ID. Rating aggregates may include reviews with valid stars and empty body text. Do not treat verified_purchase IS NULL as an unverified purchase.
- **Teams C and D:** Label source_rating as the product-page rating and sample_rating as the mean of this CSV subset. Review dates range from 1999-07-12 to 2025-07-17, and most products have at most 100 sampled reviews.
- **A2:** Use source_row_number for idempotent loading of this pinned revision. Keep source_row_hash non-unique so repeated content remains available for anomaly analysis. Future revisions require a composite source revision and position key because row numbers may change.

## Validation completed

The original A1 schema validation used a deduplicated subset. The revised schema and loader retain all 255,966 source review rows while preserving foreign key, jsonb, date, boolean, and check constraints. The 3,832 additional exact repeats and all 10 differing rows that share an (asin, source_review_id) pair remain. A persistent local database and repeatable import are documented in [database-setup.md](database-setup.md).
