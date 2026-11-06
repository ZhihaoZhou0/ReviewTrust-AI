# ReviewTrust-AI
An end-to-end data engineering and analytics platform for Amazon review reliability and product comparison.

## Data foundation

The A1 data audit for the pinned DataHive dataset is in [docs/data-audit.md](docs/data-audit.md). It includes source download commands, actual CSV schemas, integrity checks, and implications for the PostgreSQL schema.

The cleaning rules and PostgreSQL schema are documented in [docs/data-contract.md](docs/data-contract.md). Run `python3 pipeline/clean_dataset.py --help` for the clean CSV command; the schema is in [database/schema.sql](database/schema.sql).
