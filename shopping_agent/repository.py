
"""PostgreSQL data access for the ReviewTrust shopping agent.

Resolve Amazon product links to existing dataset products.
This module does not modify the database.
"""

import os

import psycopg
from psycopg.rows import dict_row

from shopping_agent.amazon_links import extract_asin


def get_connection():
    """Create a read-only connection to PostgreSQL."""
    return psycopg.connect(
        host=os.getenv("PGHOST", "127.0.0.1"),
        port=int(os.getenv("PGPORT", "5433")),
        dbname=os.getenv("PGDATABASE", "reviewtrust"),
        user=os.getenv("PGUSER", "reviewtrust"),
        password=os.getenv("PGPASSWORD", "reviewtrust_dev"),
        connect_timeout=5,
        options="-c default_transaction_read_only=on",
        row_factory=dict_row,
    )


def get_product_by_asin(asin: str) -> dict | None:
    """Retrieve a product and its factual review statistics."""

    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT
                p.asin,
                p.title,
                p.product_url,
                p.main_image_url,
                p.category_breadcrumbs,
                p.description,
                p.characteristics,
                p.source_rating::float8 AS source_rating,
                p.source_rating_count,
                COUNT(r.review_pk)::integer AS sample_review_count,
                ROUND(AVG(r.stars)::numeric, 2)
                    AS sample_rating

            FROM reviewtrust.products AS p

            LEFT JOIN reviewtrust.reviews AS r
                ON p.asin = r.asin

            WHERE p.asin = %s

            GROUP BY p.asin
            """,
            (asin,),
        ).fetchone()

    if row is None:
        return None

    product = dict(row)

    if product["sample_rating"] is not None:
        product["sample_rating"] = float(
            product["sample_rating"]
        )

    return product


def get_product_by_url(url: str) -> dict | None:
    """Resolve an Amazon product link to database data."""
    asin = extract_asin(url)
    return get_product_by_asin(asin)

def get_reviews_by_asin(
    asin: str,
    per_group: int = 4,
) -> list[dict]:
    """Retrieve balanced review evidence for a product.

    Positive and negative groups are based on star ratings.
    These are candidate evidence excerpts, not NLP-extracted
    pros and cons.
    """
    if not 1 <= per_group <= 10:
        raise ValueError("per_group must be between 1 and 10.")

    reviews = []

    with get_connection() as conn:
        for rating_group, min_stars, max_stars in [
            ("positive", 4, 5),
            ("negative", 1, 2),
        ]:
            rows = conn.execute(
                """
                SELECT
                    review_pk,
                    source_row_number,
                    source_review_id,
                    review_date,
                    stars,
                    review_title,
                    LEFT(body, 800) AS body,
                    found_helpful,
                    verified_purchase
                FROM reviewtrust.reviews
                WHERE asin = %s
                  AND stars BETWEEN %s AND %s
                  AND body IS NOT NULL
                  AND LENGTH(TRIM(body)) >= 20
                ORDER BY
                    found_helpful DESC,
                    review_date DESC,
                    review_pk DESC
                LIMIT %s
                """,
                (asin, min_stars, max_stars, per_group),
            ).fetchall()

            for row in rows:
                reviews.append({
                    **dict(row),
                    "rating_group": rating_group,
                })

    return reviews


def get_product_bundle(
    url: str,
    per_group: int = 4,
) -> dict | None:
    """Return a product and its review evidence together."""

    product = get_product_by_url(url)

    if product is None:
        return None

    reviews = get_reviews_by_asin(
        product["asin"],
        per_group=per_group,
    )

    return {
        "product": product,
        "reviews": reviews,
        "retrieved_review_count": len(reviews),
    }
