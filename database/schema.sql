-- DataHive snapshot foundation. Run with: psql -v ON_ERROR_STOP=1 -d reviewtrust -f database/schema.sql
CREATE SCHEMA IF NOT EXISTS reviewtrust;

CREATE TABLE IF NOT EXISTS reviewtrust.products (
    asin                 text PRIMARY KEY CHECK (asin ~ '^[A-Z0-9]{10}$'),
    title                text NOT NULL CHECK (length(btrim(title)) > 0),
    product_url          text,
    main_image_url       text,
    alt_images           jsonb NOT NULL DEFAULT '[]'::jsonb CHECK (jsonb_typeof(alt_images) = 'array'),
    category_breadcrumbs text,
    description          text,
    characteristics      jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(characteristics) = 'object'),
    source_rating        numeric(3, 2) NOT NULL CHECK (source_rating BETWEEN 1 AND 5),
    source_rating_count  bigint NOT NULL CHECK (source_rating_count >= 0),
    source_row_number    bigint NOT NULL CHECK (source_row_number > 0),
    source_row_hash      char(64) NOT NULL UNIQUE,
    loaded_at            timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS reviewtrust.reviews (
    review_pk            bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    asin                 text NOT NULL REFERENCES reviewtrust.products(asin),
    source_review_id     text NOT NULL CHECK (length(btrim(source_review_id)) > 0),
    review_url           text,
    review_title         text,
    body                 text,
    review_date          date NOT NULL,
    stars                smallint NOT NULL CHECK (stars BETWEEN 1 AND 5),
    user_id              text,
    variation            text,
    found_helpful        integer NOT NULL CHECK (found_helpful >= 0),
    verified_purchase    boolean,
    images               jsonb NOT NULL DEFAULT '[]'::jsonb CHECK (jsonb_typeof(images) = 'array'),
    videos               jsonb NOT NULL DEFAULT '[]'::jsonb CHECK (jsonb_typeof(videos) = 'array'),
    source_row_number    bigint NOT NULL CHECK (source_row_number > 0),
    source_row_hash      char(64) NOT NULL,
    loaded_at            timestamptz NOT NULL DEFAULT now()
);

-- Existing A1 databases used a content-hash uniqueness constraint. Remove it
-- so identical source reviews remain separate observations.
ALTER TABLE reviewtrust.reviews DROP CONSTRAINT IF EXISTS reviews_source_row_hash_key;
CREATE UNIQUE INDEX IF NOT EXISTS reviews_source_row_number_uidx
    ON reviewtrust.reviews (source_row_number);
CREATE INDEX IF NOT EXISTS reviews_source_row_hash_idx
    ON reviewtrust.reviews (source_row_hash);

CREATE INDEX IF NOT EXISTS reviews_asin_date_idx ON reviewtrust.reviews (asin, review_date DESC);
CREATE INDEX IF NOT EXISTS reviews_asin_stars_idx ON reviewtrust.reviews (asin, stars);
CREATE INDEX IF NOT EXISTS reviews_source_id_idx ON reviewtrust.reviews (source_review_id);
CREATE INDEX IF NOT EXISTS reviews_user_id_idx ON reviewtrust.reviews (user_id) WHERE user_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS products_title_search_idx ON reviewtrust.products USING gin (to_tsvector('english', title));
