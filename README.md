# ReviewTrust-AI
An end-to-end data engineering and analytics platform for Amazon review reliability and product comparison.

## Data foundation

The A1 data audit for the pinned DataHive dataset is in [docs/data-audit.md](docs/data-audit.md). It includes source download commands, actual CSV schemas, integrity checks, and implications for the PostgreSQL schema.

The cleaning rules and PostgreSQL schema are documented in [docs/data-contract.md](docs/data-contract.md). Run `python3 pipeline/clean_dataset.py --help` for the clean CSV command; the schema is in [database/schema.sql](database/schema.sql).

To start the local PostgreSQL service and load the pinned dataset, follow [docs/database-setup.md](docs/database-setup.md). The short path is `docker compose up -d --wait db` followed by `python3 pipeline/load_snapshot.py` after downloading the source CSVs.

## A2: Data Pipeline and Airflow Orchestration

The A2 pipeline automates review data validation and incremental
loading into PostgreSQL using Apache Airflow.

### Implemented Features

- Batch-level data quality validation
- Incremental loading with deterministic batch IDs
- Idempotent ingestion using source-row hashes
- PostgreSQL checkpoint tracking and transaction rollback
- Failure logging and safe recovery
- Airflow orchestration, automatic retries, and monitoring

### Architecture

```text
Raw CSV Files
      |
      v
Extract Check
      |
      v
Data Cleaning (A1)
      |
      v
Batch Validation (A2)
      |
      v
Incremental Loading (A2)
      |
      v
PostgreSQL + Batch Checkpoints
      |
      v
Airflow Monitoring
```

### Quick Start

Start PostgreSQL:

```bash
docker compose up -d --wait db
```

Import the initial snapshot:

```bash
python pipeline/load_snapshot.py
```

Initialize the incremental ETL tracking table:

```bash
docker compose exec -T db \
  psql -U reviewtrust -d reviewtrust \
  -v ON_ERROR_STOP=1 < database/etl_batches.sql
```

Run validation and incremental loading:

```bash
python -m pipeline.validate
python -m pipeline.incremental
```

Start Airflow:

```bash
docker compose -f compose.yaml \
  -f compose.airflow.yaml up -d --build
```

Open http://localhost:8080 and manually trigger
the `reviewtrust_etl` DAG.

### Verified Results

| Metric | Result |
|---|---|
| Products | 2,727 |
| Cleaned reviews | 252,134 |
| Validation batches | 26/26 passed |
| Incremental checkpoints | 26 completed |
| Airflow DAG tasks | 5/5 successful |
| Automatic retry | Verified |
| Failure recovery | Verified |

The current pipeline operates on a pinned historical dataset
snapshot rather than a live data stream.

For architecture, implementation details, and test results,
see [ETL Pipeline Documentation](docs/etl-pipeline.md).
