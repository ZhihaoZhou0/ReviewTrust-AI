# ReviewTrust AI

**A product has 4.8 stars. Can you trust the reviews behind that number?**

ReviewTrust AI is a hackathon project for exploring the reliability of Amazon product reviews. The planned experience helps someone search for a product, inspect review patterns and an explainable weighted rating, read evidence-backed pros and cons, and compare two products side by side. Review signals are clues, not proof that a review is fake.

## The demo we are building

1. **Find a product:** Search and filter products.
2. **Understand its reviews:** Compare the product-page rating with sampled-review and weighted ratings, and inspect unusual patterns.
3. **Read the evidence:** Explore recurring pros and cons with representative review excerpts.
4. **Compare two options:** View ratings, sample size, signals, and tradeoffs together.

The MVP uses PostgreSQL, Python analysis modules, and a Streamlit + Plotly dashboard. A Python data access layer will connect them; a separate FastAPI service is outside the MVP.

## Build status

| Workstream | Scope | Status |
| --- | --- | --- |
| A1 - Data foundation | Source audit, cleaning, schema, PostgreSQL snapshot import | **Integrated** |
| A2 - Data pipeline | Data quality, incremental review loading, Airflow orchestration | **Integrated for the pinned snapshot** |
| B1 - Trust analytics | Similarity, anomaly signals, weighted ratings | In progress on a feature branch |
| B2 - NLP | Pros and cons extraction and evaluation | Planned |
| C - Integration | Python data access, PostgreSQL queries, and module integration | Planned |
| D - Dashboard | Product search, trust views, pros and cons, and two-product comparison | In progress on this branch |

The first D preview is now in progress on this branch. It includes live product search, factual review-sample views, and a two-product comparison; B1/B2 analysis panels remain pending. See [dashboard-handoff.md](docs/dashboard-handoff.md) for local setup and integration details.

## Data foundation and pipeline

We use the pinned [DataHive Amazon Reviews Dataset](https://huggingface.co/datasets/datahiveai/Amazon-Reviews-Dataset), revision `2531d9083bd3aab11261eab7e69d0d0f358a6d6f`. The source has 2,727 products and 255,966 review rows. **Every valid review row is retained**, including 3,832 additional rows with exactly repeated content. Repetition may be a useful review-pattern signal; it is not a fraud verdict. Most reviewed products have at most 100 sampled reviews; product-page ratings and sampled-review means are separate measures.

A1 verifies both raw-file SHA-256 digests, cleans the CSVs without collapsing repeated reviews, creates PostgreSQL tables and indexes, and imports the snapshot transactionally. A2 validates the cleaned data against the A1 contract and audited counts, writes review batches with transactional checkpoints, and orchestrates verification, cleaning, validation, loading, and monitoring with Airflow. Repeated batches are skipped by source position; repeated review content remains available for analysis. The pinned historical snapshot is not a live data stream, and product changes require a new source revision and bootstrap strategy.

See the [source audit](docs/data-audit.md), [data contract](docs/data-contract.md), [database setup](docs/database-setup.md), and [A2 pipeline guide](docs/etl-pipeline.md).

## Run locally

Use Python 3.12, Docker Compose, and a local `psql` client. From the repository root:

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements-pipeline.txt
mkdir -p data/raw
curl -fL -o data/raw/products.csv https://huggingface.co/datasets/datahiveai/Amazon-Reviews-Dataset/resolve/2531d9083bd3aab11261eab7e69d0d0f358a6d6f/products.csv
curl -fL -o data/raw/reviews.csv https://huggingface.co/datasets/datahiveai/Amazon-Reviews-Dataset/resolve/2531d9083bd3aab11261eab7e69d0d0f358a6d6f/reviews.csv
docker compose up -d --wait db
.venv/bin/python pipeline/load_snapshot.py
.venv/bin/python -m pipeline.validate
.venv/bin/python -m pipeline.incremental
```

The snapshot importer creates the A1 tables and A2 checkpoint table in one transaction. Because it already loads every review, the subsequent incremental run records and then skips the same 26 batches without adding duplicate reviews. Actual insertion and failure recovery were also checked in an isolated products-only database.

To run the Airflow DAG locally:

```bash
docker compose -f compose.yaml -f compose.airflow.yaml up -d --build
```

Open `http://localhost:8080` and manually trigger `reviewtrust_etl`. The DAG is intentionally unscheduled for the historical snapshot. Its five tasks verify source files, clean, validate, load, and monitor. The source and cleaned CSV files stay outside Git.

Run regression checks with `.venv/bin/python -m unittest discover -s tests -v`.

To preview the D dashboard on this branch, follow [dashboard-handoff.md](docs/dashboard-handoff.md).
