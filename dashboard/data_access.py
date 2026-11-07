"""Read-only PostgreSQL queries for the Streamlit dashboard.

This module is the handoff point for Team C's Python data access layer.
It returns source and sampled ratings separately and never computes trust scores.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

import psycopg
from psycopg.rows import dict_row


@dataclass(frozen=True)
class Product:
    asin: str
    title: str
    category: str
    source_rating: float
    source_rating_count: int
    image_url: str | None


@dataclass(frozen=True)
class ProductSnapshot:
    product: Product
    sample_review_count: int
    sample_rating: float | None
    first_review_date: date | None
    last_review_date: date | None
    star_counts: tuple[int, int, int, int, int]


@dataclass(frozen=True)
class ReviewExcerpt:
    source_review_id: str
    review_date: date
    stars: int
    title: str | None
    body: str


def _connect() -> psycopg.Connection:
    return psycopg.connect(
        host=os.getenv("PGHOST", "127.0.0.1"),
        port=int(os.getenv("PGPORT", os.getenv("POSTGRES_PORT", "5433"))),
        dbname=os.getenv("PGDATABASE", os.getenv("POSTGRES_DB", "reviewtrust")),
        user=os.getenv("PGUSER", os.getenv("POSTGRES_USER", "reviewtrust")),
        password=os.getenv("PGPASSWORD", os.getenv("POSTGRES_PASSWORD", "reviewtrust_dev")),
        connect_timeout=5,
        options="-c default_transaction_read_only=on",
        row_factory=dict_row,
    )


def _category(breadcrumbs: str | None) -> str:
    if not breadcrumbs:
        return "Uncategorized"
    category = breadcrumbs.split(" -> ", 1)[0].strip()
    return category if category.isascii() else "Other categories"


def _product(row: dict) -> Product:
    return Product(
        asin=row["asin"],
        title=row["title"],
        category=_category(row["category_breadcrumbs"]),
        source_rating=float(row["source_rating"]),
        source_rating_count=int(row["source_rating_count"]),
        image_url=row["main_image_url"] or None,
    )


def load_catalog() -> list[Product]:
    """Return every product for local search and comparison selection."""
    with _connect() as connection, connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT asin, title, category_breadcrumbs, source_rating,
                   source_rating_count, main_image_url
            FROM reviewtrust.products
            ORDER BY source_rating_count DESC, title, asin
            """
        )
        return [_product(row) for row in cursor.fetchall()]


def load_product_snapshot(asin: str) -> ProductSnapshot | None:
    """Return factual product metrics based on the cleaned review sample."""
    with _connect() as connection, connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT p.asin, p.title, p.category_breadcrumbs, p.source_rating,
                   p.source_rating_count, p.main_image_url,
                   count(r.review_pk)::integer AS sample_review_count,
                   round(avg(r.stars)::numeric, 2) AS sample_rating,
                   min(r.review_date) AS first_review_date,
                   max(r.review_date) AS last_review_date,
                   count(*) FILTER (WHERE r.stars = 1)::integer AS star_1,
                   count(*) FILTER (WHERE r.stars = 2)::integer AS star_2,
                   count(*) FILTER (WHERE r.stars = 3)::integer AS star_3,
                   count(*) FILTER (WHERE r.stars = 4)::integer AS star_4,
                   count(*) FILTER (WHERE r.stars = 5)::integer AS star_5
            FROM reviewtrust.products AS p
            LEFT JOIN reviewtrust.reviews AS r ON r.asin = p.asin
            WHERE p.asin = %s
            GROUP BY p.asin
            """,
            (asin,),
        )
        row = cursor.fetchone()
        if row is None:
            return None
        sample_rating: Decimal | None = row["sample_rating"]
        return ProductSnapshot(
            product=_product(row),
            sample_review_count=row["sample_review_count"],
            sample_rating=float(sample_rating) if sample_rating is not None else None,
            first_review_date=row["first_review_date"],
            last_review_date=row["last_review_date"],
            star_counts=tuple(row[f"star_{stars}"] for stars in range(1, 6)),
        )


def load_recent_reviews(asin: str, limit: int = 3) -> list[ReviewExcerpt]:
    """Return original review excerpts as evidence, not inferred pros/cons."""
    with _connect() as connection, connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT source_review_id, review_date, stars, review_title, body
            FROM reviewtrust.reviews
            WHERE asin = %s AND body IS NOT NULL
            ORDER BY review_date DESC, review_pk DESC
            LIMIT %s
            """,
            (asin, limit),
        )
        return [
            ReviewExcerpt(
                source_review_id=row["source_review_id"],
                review_date=row["review_date"],
                stars=row["stars"],
                title=row["review_title"],
                body=row["body"],
            )
            for row in cursor.fetchall()
        ]
