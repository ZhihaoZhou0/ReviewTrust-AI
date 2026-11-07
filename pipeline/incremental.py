"""
ReviewTrust AI - Incremental Review Loading.

Reads cleaned reviews in fixed-size batches, validates each batch,
and inserts new records into PostgreSQL.

Key features:
- Deterministic batch identifiers
- Batch-level quality validation
- Rerun protection using source_row_number without collapsing repeated content
- Transactional checkpoint tracking
- Safe reruns and failure recovery
"""

import argparse
import csv
import hashlib
import json
import os

from itertools import islice
from pathlib import Path

import polars as pl
import psycopg

from pipeline.clean_dataset import REVIEW_OUTPUT
from pipeline.source import snapshot_manifest
from pipeline.validate import validate_batch


# Resolve paths relative to the repository rather than
# depending on the current terminal working directory.
ROOT = Path(__file__).resolve().parents[1]
REVIEWS_CSV = ROOT / "data/processed/reviews_clean.csv"

# Pinned source revision ensures that the batch identity
# includes the dataset version.
SOURCE_REVISION = snapshot_manifest()["source"]["revision"]

# Increment this value if the batching logic changes in
# a way that should generate new batch identities.
PIPELINE_VERSION = "v2-retain-repeated-reviews"

# Reuse the exact cleaned column order defined by A1.
COLUMNS = ", ".join(REVIEW_OUTPUT)


def get_connection():
    """
    Open a PostgreSQL connection.

    Environment variables allow the same loader to connect to:
    - The local development database
    - The isolated A2 test database
    - PostgreSQL inside Docker

    Explicit transactions are used during batch loading,
    even though the connection enables autocommit.
    """
    return psycopg.connect(
        host=os.getenv("PGHOST", "127.0.0.1"),
        port=os.getenv("PGPORT", "5433"),
        dbname=os.getenv("PGDATABASE", "reviewtrust"),
        user=os.getenv("PGUSER", "reviewtrust"),
        password=os.getenv("PGPASSWORD", "reviewtrust_dev"),
        autocommit=True,
    )


def read_batches(path, batch_size):
    """
    Read cleaned CSV records in fixed-size batches.

    CSV rows are streamed instead of loading the entire dataset
    into memory. This makes the ingestion logic more scalable.
    """
    with path.open(
        "r", encoding="utf-8", newline=""
    ) as file:
        reader = csv.DictReader(file)

        # Reject unexpected columns to enforce A1's data contract.
        if reader.fieldnames != REVIEW_OUTPUT:
            raise ValueError(
                "CSV schema does not match A1 data contract."
            )

        while True:
            rows = list(islice(reader, batch_size))

            # Stop after reading the final batch.
            if not rows:
                break

            yield rows


def make_batch_id(rows, batch_number):
    """
    Generate a deterministic SHA-256 identifier for one batch.

    The ID depends on the source revision, pipeline version,
    batch position, row count, source positions, and row hashes.

    Processing the same batch again produces the same ID,
    allowing previously completed batches to be recognized.
    """
    digest = hashlib.sha256()

    digest.update(
        f"{SOURCE_REVISION}|{PIPELINE_VERSION}|"
        f"{batch_number}|{len(rows)}|".encode()
    )

    # Equal content at different source positions must remain distinct.
    for row in rows:
        digest.update(
            f"{row['source_row_number']}:{row['source_row_hash']}|".encode("ascii")
        )

    return digest.hexdigest()


def is_completed(conn, batch_id):
    """
    Check whether PostgreSQL has a successful checkpoint.

    Only completed batches are skipped.
    Failed batches remain eligible for retry.
    """
    result = conn.execute(
        """
        SELECT 1
        FROM reviewtrust.etl_batches
        WHERE batch_id = %s AND status = 'completed'
        """,
        (batch_id,),
    ).fetchone()

    return result is not None


def load_batch(conn, rows, batch_id, batch_number):
    """
    Atomically load a batch and save its successful checkpoint.

    Review insertion and checkpoint creation take place in
    the same transaction.

    If either operation fails, PostgreSQL rolls back both.
    """
    with conn.transaction():
        with conn.cursor() as cur:

            # Create an isolated temporary staging table.
            # It automatically disappears when the transaction ends.
            cur.execute(
                f"""
                CREATE TEMP TABLE stage_incremental
                ON COMMIT DROP AS
                SELECT {COLUMNS}
                FROM reviewtrust.reviews
                WITH NO DATA
                """
            )

            # Use PostgreSQL COPY for efficient bulk ingestion.
            # Empty CSV values represent SQL NULL.
            with cur.copy(
                f"COPY stage_incremental ({COLUMNS}) "
                "FROM STDIN"
            ) as copy:
                for row in rows:
                    copy.write_row([
                        row[col] if row[col] != "" else None
                        for col in REVIEW_OUTPUT
                    ])

            # The source position identifies an imported CSV row.
            # Equal content hashes at different positions are retained.
            cur.execute(
                f"""
                INSERT INTO reviewtrust.reviews ({COLUMNS})
                SELECT {COLUMNS}
                FROM stage_incremental
                ON CONFLICT (source_row_number)
                DO NOTHING
                """
            )

            # PostgreSQL reports how many rows were actually inserted.
            inserted = cur.rowcount

            # A reused source position with changed content must fail loudly.
            cur.execute(
                """
                SELECT COUNT(*)
                FROM stage_incremental AS s
                LEFT JOIN reviewtrust.reviews AS r
                  ON r.source_row_number = s.source_row_number
                WHERE r.review_pk IS NULL
                   OR r.source_row_hash <> s.source_row_hash
                """
            )
            if cur.fetchone()[0]:
                raise ValueError("Source row positions do not match stored reviews")

            # Record the successful batch in the same transaction.
            # A previously failed checkpoint becomes completed
            # once the retry succeeds.
            cur.execute(
                """
                INSERT INTO reviewtrust.etl_batches (
                    batch_id, source_revision,
                    batch_number, input_rows,
                    inserted_rows, status, completed_at
                )
                VALUES (%s, %s, %s, %s, %s,
                        'completed', NOW())
                ON CONFLICT (batch_id)
                DO UPDATE SET
                    inserted_rows = EXCLUDED.inserted_rows,
                    status = 'completed',
                    completed_at = NOW(),
                    error_message = NULL
                """,
                (
                    batch_id,
                    SOURCE_REVISION,
                    batch_number,
                    len(rows),
                    inserted,
                ),
            )

    return inserted


def record_failure(conn, batch_id, number, count, error):
    """
    Save failure information after the load transaction rolls back.

    This operation runs separately from the failed transaction
    so that the error record can remain in PostgreSQL.
    """
    conn.execute(
        """
        INSERT INTO reviewtrust.etl_batches (
            batch_id, source_revision,
            batch_number, input_rows,
            status, completed_at, error_message
        )
        VALUES (%s, %s, %s, %s, 'failed', NOW(), %s)
        ON CONFLICT (batch_id)
        DO UPDATE SET
            status = 'failed',
            completed_at = NOW(),
            error_message = EXCLUDED.error_message
        """,
        (
            batch_id,
            SOURCE_REVISION,
            number,
            count,
            str(error)[:2000],
        ),
    )


def run_incremental(batch_size=10000, max_batches=None):
    """
    Execute the incremental ETL workflow.

    For each batch:
    1. Generate a stable batch ID.
    2. Skip completed batches.
    3. Validate record quality.
    4. Insert new records transactionally.
    5. Save success or failure information.
    """
    if batch_size <= 0:
        raise ValueError("batch_size must be positive.")

    if not REVIEWS_CSV.is_file():
        raise FileNotFoundError(REVIEWS_CSV)

    with get_connection() as conn:

        # Load valid product IDs for foreign-key validation.
        product_asins = {
            row[0] for row in conn.execute(
                "SELECT asin FROM reviewtrust.products"
            ).fetchall()
        }

        for number, rows in enumerate(
            read_batches(REVIEWS_CSV, batch_size),
            start=1,
        ):
            # Optional limit for controlled development tests.
            if max_batches is not None and number > max_batches:
                break

            batch_id = make_batch_id(rows, number)

            # Avoid repeating expensive database writes.
            if is_completed(conn, batch_id):
                print(f"Batch {number}: SKIPPED")
                continue

            try:
                # Convert the current batch into a Polars DataFrame
                # to reuse the existing validation function.
                frame = pl.DataFrame(rows)

                result = validate_batch(
                    frame, product_asins, number
                )

                # Quality gate: do not load invalid records.
                if not result["valid"]:
                    raise ValueError(
                        json.dumps(result["issues"])
                    )

                # Load reviews and checkpoint atomically.
                inserted = load_batch(
                    conn, rows, batch_id, number
                )

                print(
                    f"Batch {number}: COMPLETED "
                    f"(input={len(rows)}, "
                    f"inserted={inserted})"
                )

            except Exception as error:
                # Preserve the failure reason for monitoring.
                try:
                    record_failure(
                        conn, batch_id, number,
                        len(rows), error
                    )
                except Exception as log_error:
                    print(
                        f"Could not save failure status: {log_error}"
                    )

                # Re-raise the error so Airflow can detect failure
                # and apply its configured retry policy.
                print(f"Batch {number}: FAILED - {error}")
                raise


if __name__ == "__main__":
    # CLI arguments allow full runs or limited batch tests.
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch-size", type=int, default=10000)
    parser.add_argument("--max-batches", type=int, default=None)

    args = parser.parse_args()

    run_incremental(
        batch_size=args.batch_size,
        max_batches=args.max_batches,
    )
