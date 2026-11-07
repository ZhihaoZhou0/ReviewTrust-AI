# Local PostgreSQL and Initial Import

This workflow loads the [pinned DataHive Amazon Reviews snapshot](data-audit.md) for A1, A2, and downstream analysis. The database schema is in [schema.sql](../database/schema.sql), and the transactional import is in [load_snapshot.sql](../database/load_snapshot.sql).

## Prerequisites

- Docker Compose is available.
- Python 3 is available; the cleaner uses only the standard library.
- The psql client is on PATH. The import script checks for it.
- data/raw/products.csv and data/raw/reviews.csv have been downloaded from the pinned revision using the commands in [data-audit.md](data-audit.md). Git does not track source or cleaned CSV files.

## Start and import

Run from the repository root:

    docker compose up -d --wait db
    python3 pipeline/load_snapshot.py

The second command verifies both raw files against A1's committed sizes and SHA-256 digests, cleans them, creates the A1 schema and A2 checkpoint table, loads both cleaned files into temporary tables, and writes to the final tables in one database transaction. An import failure rolls back the transaction. Re-running the command does not create duplicate products or reviews. Existing products are updated if their source content changes; reviews are deduplicated by source_row_hash. The current A2 loader processes new reviews from this pinned snapshot; future source revisions need an explicit product-update and provenance strategy.

Local development defaults:

| Setting | Value |
| --- | --- |
| Host | 127.0.0.1 |
| Port | 5433 |
| Database | reviewtrust |
| User | reviewtrust |
| Password | reviewtrust_dev (local development only) |
| Data volume | reviewtrust-ai_postgres_data |

Override POSTGRES_PORT, POSTGRES_DB, POSTGRES_USER, or POSTGRES_PASSWORD through environment variables for Compose. The import script reads those values and also accepts PGHOST, PGPORT, PGDATABASE, PGUSER, and PGPASSWORD. Ensure Compose and the import script receive matching credentials. The database binds only to the local loopback interface. Other containers should connect to service db on container port 5432.

## Verify and query

    docker compose exec db psql -U reviewtrust -d reviewtrust -c "SELECT count(*) FROM reviewtrust.products;"
    docker compose exec db psql -U reviewtrust -d reviewtrust -c "SELECT count(*) FROM reviewtrust.reviews;"

The pinned snapshot should contain 2,727 products and 252,134 deduplicated reviews. See the [data contract](data-contract.md) for field definitions and a downstream rating query.

Use docker compose stop db to pause the database. Running docker compose up -d --wait db again reuses the named volume. docker compose down removes the containers and network while retaining the volume.

## Validation completed

The import ran twice against local PostgreSQL 16. The first run inserted 2,727 products and 252,134 reviews. The second run inserted zero rows into both final tables, and the counts remained unchanged. Staging-table checks passed on both runs.
