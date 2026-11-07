# A1 Cleaning Rules and PostgreSQL Data Contract

This contract uses pinned DataHive revision 2531d9083bd3aab11261eab7e69d0d0f358a6d6f. See [data-audit.md](data-audit.md) for source profiling and [cleaning-report.json](cleaning-report.json) for cleaning counts.

## Run the cleaner

Run from the repository root:

    python3 pipeline/clean_dataset.py --products data/raw/products.csv --reviews data/raw/reviews.csv --output-dir data/processed --report docs/cleaning-report.json

The outputs are data/processed/products_clean.csv and data/processed/reviews_clean.csv. The source files are unchanged, and Git ignores data/processed/. source_row_number is the one-based CSV record number, not the physical line number, because review text may contain line breaks. source_row_hash is a SHA-256 digest of the source CSV field values in source-column order. It identifies identical source records; it is not a fraud label.

This snapshot retained all 2,727 products. Of 255,966 source reviews, the cleaner removed 3,832 rows whose CSV field values were identical to an earlier row, leaving 252,134 reviews. No other rows were rejected. If future input has missing required fields, out-of-range values, invalid dates or JSON, or orphan ASINs, the report records counts by rejection reason.

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

Other URLs, titles, descriptions, and user IDs remain nullable text. The reviews table uses an internal review_pk primary key. source_row_hash is unique, but (asin, source_review_id) is not: the source contains 10 rows whose content differs despite sharing that pair. loaded_at records database load time, not review publication time. See [schema.sql](../database/schema.sql) for the table definitions.

## Query definitions for downstream teams

The following query computes the mean from deduplicated sampled reviews and keeps it separate from the source product-page rating:

    SELECT p.asin, p.title, p.source_rating, p.source_rating_count,
           count(r.review_pk) AS sample_review_count,
           round(avg(r.stars), 2) AS sample_rating
    FROM reviewtrust.products AS p
    LEFT JOIN reviewtrust.reviews AS r ON r.asin = p.asin
    GROUP BY p.asin;

- **Team B:** Use reviews with body IS NOT NULL for text similarity and Pros & Cons. Rating aggregates may include reviews with valid stars and empty body text. Do not treat verified_purchase IS NULL as an unverified purchase.
- **Teams C and D:** Label source_rating as the product-page rating and sample_rating as the mean of this CSV subset. Review dates range from 1999-07-12 to 2025-07-17, and most products have at most 100 sampled reviews.
- **A2:** Use source_row_hash to recognize duplicate source records. Record future load batches and revisions separately; source_row_number is not stable across revisions.

## Validation completed

The schema and both cleaned CSV files loaded successfully into PostgreSQL 16: 2,727 products and 252,134 reviews passed the foreign key, jsonb, date, boolean, and check constraints. The loaded data contains 206 reviews with NULL body and 2,395 with unknown verified-purchase status. All 10 differing rows that share an (asin, source_review_id) pair remain. The temporary validation container was removed. A persistent local database and repeatable import are documented in [database-setup.md](database-setup.md).
