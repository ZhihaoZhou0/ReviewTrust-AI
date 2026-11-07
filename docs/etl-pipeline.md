
# ReviewTrust AI — ETL Pipeline Documentation

## 1. Overview

The ReviewTrust AI ETL pipeline processes Amazon product and review
data and stores validated records in PostgreSQL.

The pipeline supports:

- Verification of locally available CSV files against A1's pinned SHA-256 digests
- Data cleaning and schema standardization
- Batch-level data quality validation
- Incremental loading with source-position rerun protection
- PostgreSQL batch checkpoints and failure recovery
- Airflow orchestration, task retries, and monitoring

The current implementation uses a pinned historical dataset snapshot.
Incremental loading is demonstrated through reproducible batches,
rather than a live change-data-capture stream.

## 2. Architecture

    Raw Amazon CSV Files
             |
             v
     Source Verification
             |
             v
      Data Cleaning (A1)
             |
             v
    Batch Validation (A2)
             |
             v
    Incremental Load (A2)
             |
             +----> PostgreSQL Reviews
             |
             +----> PostgreSQL ETL Batches
             |
             v
      Airflow Monitoring

Apache Airflow coordinates the tasks, while PostgreSQL stores
both application data and ETL checkpoint metadata.

## 3. Dataset

Source: DataHive Amazon Reviews Dataset

Dataset revision:
2531d9083bd3aab11261eab7e69d0d0f358a6d6f

| Metric | Count |
|---|---:|
| Raw products | 2,727 |
| Raw reviews | 255,966 |
| Additional rows with exactly repeated content | 3,832 retained |
| Cleaned reviews | 255,966 |
| Default batch size | 10,000 |
| Total review batches | 26 |

Every valid review row is retained during cleaning, including identical rows and reviews sharing a source ID. Repeated content is available for analysis, but is not itself a fraud verdict.

## 4. Key Components

| File | Responsibility |
|---|---|
| pipeline/extract.py | Source data extraction and inspection |
| pipeline/clean_dataset.py | Data cleaning and standardization |
| pipeline/validate.py | Batch-level data quality checks |
| pipeline/incremental.py | Incremental PostgreSQL loading |
| pipeline/load_snapshot.py | Initial full snapshot import |
| database/schema.sql | PostgreSQL application schema |
| database/etl_batches.sql | Batch tracking schema |
| dags/reviewtrust_etl.py | Main Airflow DAG |
| dags/test_airflow_retry.py | Automatic retry verification |
| Dockerfile.airflow | Custom Airflow environment |
| compose.airflow.yaml | Airflow Docker Compose configuration |

## 5. Data Quality Validation

The validation module checks:

- Required columns and identifiers
- ASIN format and product references
- Star ratings between 1 and 5
- Valid review dates
- Nonnegative helpful-vote counts
- Verified-purchase field values
- Unique source row positions within and across batches
- Repeated-content counts matching the A1 audit
- Positive source row numbers
- Exact product and cleaned-review counts for the audited snapshot

Optional review text and unknown verified-purchase status
may be NULL.

A failed validation raises an exception, preventing downstream data loading. An empty or truncated cleaned dataset is a failure, even when every present row is valid.

Validated results are written to:

`data/processed/validation-report.json`

## 6. Incremental Loading

Cleaned reviews are processed in batches of 10,000 rows.

Each batch receives a deterministic SHA-256 identifier derived
from its source revision, pipeline version, batch number,
row count, and ordered source record hashes.

Before loading a batch, the pipeline checks whether its
batch ID has already been completed.

- Completed batches are skipped.
- Unprocessed or failed batches are eligible for loading.
- New reviews are inserted through a temporary staging table.
- Unique source row positions prevent a rerun from inserting the same CSV record twice; `source_row_hash` is non-unique.

The default batch size is configurable through the CLI.

## 7. Checkpointing and Failure Recovery

PostgreSQL stores batch metadata in:

`reviewtrust.etl_batches`

Important metadata includes:

- Batch identifier
- Source revision
- Batch number
- Input and inserted row counts
- Completion status
- Execution timestamps
- Failure details

Review insertion and the successful checkpoint are committed
in the same database transaction.

If loading fails, the transaction rolls back. A separate
operation records the batch failure for monitoring.

After the underlying issue is fixed, rerunning the loader
skips completed batches and retries unfinished batches.

This provides safe manual recovery. Airflow additionally
supports task-level automatic retries.

## 8. Airflow Orchestration

Main DAG: `reviewtrust_etl`

Execution order:

1. `extract_check`
2. `clean`
3. `validate`
4. `incremental_load`
5. `monitor`

The DAG is manually triggered in the current MVP.

Airflow is configured with:

- Two additional retries per failed task
- A one-minute retry delay
- A maximum of one active DAG run
- Task-level execution logs

The `monitor` task reports PostgreSQL review counts and
ETL batch statuses.

## 9. Local Setup

Prerequisites:

- Docker Desktop and Docker Compose
- Python virtual environment for local testing
- PostgreSQL client (`psql`) for full snapshot import
- Python dependencies including Polars and Psycopg

Start the database:

`docker compose up -d --wait db`

Perform the initial snapshot import:

`python pipeline/load_snapshot.py`

Validate cleaned reviews:

`python -m pipeline.validate`

Execute incremental loading:

`python -m pipeline.incremental`

Start PostgreSQL and Airflow together:

`docker compose -f compose.yaml -f compose.airflow.yaml up -d --build`

Airflow UI:

`http://localhost:8080`

The A1 snapshot importer verifies source checksums and initializes the application schema and batch tracking table in one PostgreSQL transaction. Airflow verifies the raw files again before cleaning. For local Python commands, create a Python 3.12 virtual environment and install `requirements-pipeline.txt` as shown in the README. The DAG writes its runtime cleaning and validation reports to `data/processed/`; it does not overwrite tracked audit files in `docs/`.

## 10. Testing and Verification

### Snapshot Idempotency

The revised snapshot importer migrated a database created by the original A1 pipeline, adding the 3,832 repeated-content source rows that had previously been dropped. A second run inserted zero additional products and reviews.

Final counts:

- Products: 2,727
- Reviews: 255,966

### Batch Validation

All 26 batches passed validation.

- Failed batches: 0
- Cross-batch duplicate source positions: 0
- Additional repeated-content review rows retained: 3,832

### Incremental Loading

All 26 batch checkpoints were completed successfully
in the development database.

A second run skipped previously completed batches.

### Actual Insert Test

A separate test database was used to verify real inserts.

The first batch inserted 10,000 reviews, including 213 rows whose content hash repeats within that batch. Re-running it skipped the completed checkpoint.

### Failure Recovery Test

A temporary database constraint was introduced to force
Batch 3 to fail.

PostgreSQL recorded the failed batch and its error message.

After removing the constraint and rerunning the loader:

- Batches 1 and 2 were skipped.
- Batch 3 inserted 10,000 reviews.
- All three batches were marked completed.
- The test database contained 30,000 reviews.

### Airflow End-to-End Test

The main Airflow DAG completed successfully.

- Successful tasks: 5/5
- Development database reviews: 255,966
- Completed batch checkpoints: 26
- Unresolved failed batches: 0

### Airflow Automatic Retry Test

The separate `reviewtrust_retry_test` DAG intentionally failed
its first task attempt.

- Attempt 1: Failed as expected
- Attempt 2: Succeeded automatically
- Downstream recovery confirmation: Succeeded
- Final DAG run: Success

## 11. Current Limitations

- The source is a historical dataset snapshot, not a live feed.
- The DAG requires local CSV files from the pinned revision. `pipeline/extract.py` can download those exact files when they are missing.
- Incremental checkpoints depend on deterministic batch content
  and ordering.
- Product changes and record updates are not independently
  managed by the incremental review loader.
- Changing the pinned source revision requires a new audit manifest,
  updated expected counts, and a deliberate product-update strategy.
- The current Docker configuration is intended for local
  development and demonstration, not production deployment.

## 12. Future Improvements

Potential improvements include:

- Scheduled source-data refreshes
- Support for new source revisions and update semantics
- Automated integration and regression testing
- More detailed pipeline execution metrics
- Production-oriented credential and deployment management
- Integration with ReviewTrust's NLP and review-scoring modules
