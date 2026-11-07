"""Final PostgreSQL checks for the pinned ReviewTrust snapshot."""

from __future__ import annotations

import os

import psycopg

from pipeline.source import expected_counts


def run_monitor() -> dict:
    """Fail if the database is incomplete or any ETL batch remains failed."""
    expected_products, expected_reviews = expected_counts()
    with psycopg.connect(
        host=os.getenv("PGHOST", "127.0.0.1"),
        port=os.getenv("PGPORT", "5433"),
        dbname=os.getenv("PGDATABASE", "reviewtrust"),
        user=os.getenv("PGUSER", "reviewtrust"),
        password=os.getenv("PGPASSWORD", "reviewtrust_dev"),
        options="-c default_transaction_read_only=on",
    ) as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM reviewtrust.products")
            product_count = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM reviewtrust.reviews")
            review_count = cursor.fetchone()[0]
            cursor.execute(
                "SELECT status, COUNT(*) FROM reviewtrust.etl_batches GROUP BY status"
            )
            batch_status = dict(cursor.fetchall())

    summary = {
        "products": product_count,
        "reviews": review_count,
        "batch_status": batch_status,
    }
    print(f"Products: {product_count}/{expected_products}")
    print(f"Reviews: {review_count}/{expected_reviews}")
    print(f"Batch status: {batch_status}")
    if product_count != expected_products or review_count != expected_reviews:
        raise ValueError("PostgreSQL row counts differ from the audited snapshot")
    if batch_status.get("completed", 0) == 0:
        raise ValueError("No completed ETL batches were recorded")
    if batch_status.get("failed", 0) > 0:
        raise ValueError("Failed ETL batches detected")
    return summary


if __name__ == "__main__":
    run_monitor()
