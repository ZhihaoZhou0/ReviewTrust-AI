-- Run through pipeline/load_snapshot.py from the repository root.
-- psql -1 wraps the schema and both COPY operations in one transaction.

CREATE TEMP TABLE stage_products AS
SELECT asin, title, product_url, main_image_url, alt_images,
       category_breadcrumbs, description, characteristics,
       source_rating, source_rating_count, source_row_number, source_row_hash
FROM reviewtrust.products WITH NO DATA;

CREATE TEMP TABLE stage_reviews AS
SELECT asin, source_review_id, review_url, review_title, body,
       review_date, stars, user_id, variation, found_helpful,
       verified_purchase, images, videos, source_row_number, source_row_hash
FROM reviewtrust.reviews WITH NO DATA;

\copy stage_products FROM 'data/processed/products_clean.csv' WITH (FORMAT csv, HEADER true, NULL '')
\copy stage_reviews FROM 'data/processed/reviews_clean.csv' WITH (FORMAT csv, HEADER true, NULL '')

INSERT INTO reviewtrust.products (
    asin, title, product_url, main_image_url, alt_images,
    category_breadcrumbs, description, characteristics,
    source_rating, source_rating_count, source_row_number, source_row_hash
)
SELECT asin, title, product_url, main_image_url, alt_images,
       category_breadcrumbs, description, characteristics,
       source_rating, source_rating_count, source_row_number, source_row_hash
FROM stage_products
ON CONFLICT (asin) DO UPDATE SET
    title = EXCLUDED.title,
    product_url = EXCLUDED.product_url,
    main_image_url = EXCLUDED.main_image_url,
    alt_images = EXCLUDED.alt_images,
    category_breadcrumbs = EXCLUDED.category_breadcrumbs,
    description = EXCLUDED.description,
    characteristics = EXCLUDED.characteristics,
    source_rating = EXCLUDED.source_rating,
    source_rating_count = EXCLUDED.source_rating_count,
    source_row_number = EXCLUDED.source_row_number,
    source_row_hash = EXCLUDED.source_row_hash
WHERE (
    reviewtrust.products.title, reviewtrust.products.product_url,
    reviewtrust.products.main_image_url, reviewtrust.products.alt_images,
    reviewtrust.products.category_breadcrumbs, reviewtrust.products.description,
    reviewtrust.products.characteristics, reviewtrust.products.source_rating,
    reviewtrust.products.source_rating_count, reviewtrust.products.source_row_number,
    reviewtrust.products.source_row_hash
) IS DISTINCT FROM (
    EXCLUDED.title, EXCLUDED.product_url, EXCLUDED.main_image_url,
    EXCLUDED.alt_images, EXCLUDED.category_breadcrumbs, EXCLUDED.description,
    EXCLUDED.characteristics, EXCLUDED.source_rating,
    EXCLUDED.source_rating_count, EXCLUDED.source_row_number,
    EXCLUDED.source_row_hash
);

INSERT INTO reviewtrust.reviews (
    asin, source_review_id, review_url, review_title, body,
    review_date, stars, user_id, variation, found_helpful,
    verified_purchase, images, videos, source_row_number, source_row_hash
)
SELECT asin, source_review_id, review_url, review_title, body,
       review_date, stars, user_id, variation, found_helpful,
       verified_purchase, images, videos, source_row_number, source_row_hash
FROM stage_reviews
ON CONFLICT (source_row_number) DO NOTHING;

DO $$
BEGIN
    IF (SELECT count(*) FROM stage_products) !=
       (SELECT count(*) FROM stage_products AS s
        JOIN reviewtrust.products AS p ON p.asin = s.asin AND p.source_row_hash = s.source_row_hash)
    THEN
        RAISE EXCEPTION 'Product staging rows do not match loaded products';
    END IF;
    IF (SELECT count(*) FROM stage_reviews) !=
       (SELECT count(*) FROM stage_reviews AS s
        JOIN reviewtrust.reviews AS r
          ON r.source_row_number = s.source_row_number
         AND r.source_row_hash = s.source_row_hash)
    THEN
        RAISE EXCEPTION 'Review staging rows do not match loaded reviews';
    END IF;
END $$;

SELECT (SELECT count(*) FROM stage_products) AS staged_products,
       (SELECT count(*) FROM stage_reviews) AS staged_reviews,
       (SELECT count(*) FROM reviewtrust.products) AS total_products,
       (SELECT count(*) FROM reviewtrust.reviews) AS total_reviews;
