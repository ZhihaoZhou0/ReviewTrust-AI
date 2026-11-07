# ReviewTrust AI

**A product has 4.8 stars. Can you trust the reviews behind that number?**

ReviewTrust AI is a consumer-focused review intelligence platform developed for a hackathon. It helps users explore Amazon product reviews beyond the headline star rating through review reliability signals, evidence-backed pros and cons, and side-by-side product comparisons.

ReviewTrust AI does not claim to identify fake reviews with certainty. Its trust signals are explainable indicators based on historical review samples.

## Key Features

1. **Product discovery:** Browse categories, search by product name or ASIN, and explore featured products and review-based shortlists.
2. **Review reliability (B1):** Compare listed ratings, sampled-review means, and experimental trust-adjusted ratings. Inspect rating changes and adjusted review counts.
3. **Evidence-backed pros and cons (B2):** Explore recurring positive and negative product aspects, supported by actual review excerpts.
4. **Product comparison:** Paste two supported Amazon product URLs or select products to compare their review evidence side by side.
5. **Review exploration:** Inspect star distributions, review counts, historical review windows, and supporting review excerpts.
6. **AI Shopping Agent:** Compare one to five supported Amazon products against explicit needs. Hard requirements are enforced before B1/B2 evidence-based ranking.

## Architecture and Tech Stack

- **Data source:** DataHive Amazon Reviews Dataset, pinned historical snapshot.
- **Data engineering:** Python, CSV validation, cleaning, PostgreSQL, transactional loading, and Airflow orchestration.
- **Analytics:** Python-based review reliability and aspect extraction modules.
- **Integration:** PostgreSQL data access and precomputed B1/B2 CSV result adapters.
- **Frontend:** Streamlit, HTML, and CSS.
- **Testing:** Python automated tests and manual dashboard validation.

The MVP uses a Python data access layer rather than a separate FastAPI service.

## Build Status

| Workstream | Scope | Status |
| --- | --- | --- |
| A1 — Data Foundation | Source audit, cleaning, schema, PostgreSQL snapshot import | Integrated |
| A2 — Data Pipeline | Data quality, incremental loading, Airflow orchestration | Integrated for pinned snapshot |
| B1 — Trust Analytics | Review reliability signals and adjusted ratings | Integrated |
| B2 — NLP | Evidence-backed pros and cons extraction | Integrated |
| C — Integration | PostgreSQL access and B1/B2 result adapters | Integrated for dashboard MVP |
| D — Dashboard | Discovery, review evidence, B1/B2 views, product comparison | Integrated |

## Data Foundation and Pipeline

We use the pinned [DataHive Amazon Reviews Dataset](https://huggingface.co/datasets/datahiveai/Amazon-Reviews-Dataset), revision `2531d9083bd3aab11261eab7e69d0d0f358a6d6f`.

The source contains:

- 2,727 products.
- 255,966 review rows.
- 3,832 additional rows with exactly repeated review content, retained for analysis.

Most reviewed products have at most 100 sampled reviews. Product-page ratings and sampled-review means are separate measures.

A1 verifies raw-file SHA-256 digests, cleans the CSVs without collapsing repeated reviews, creates PostgreSQL tables and indexes, and imports the snapshot transactionally.

A2 validates cleaned data against the A1 contract and audited counts, writes review batches with transactional checkpoints, and orchestrates verification, cleaning, validation, loading, and monitoring with Airflow.

Repeated batches are skipped by source position; repeated review content remains available for analysis. The pinned historical snapshot is not a live data stream.

Documentation:

- [Source Audit](docs/data-audit.md)
- [Data Contract](docs/data-contract.md)
- [Database Setup](docs/database-setup.md)
- [A2 Pipeline Guide](docs/etl-pipeline.md)
- [Dashboard Guide](docs/dashboard-handoff.md)

## Run Locally

### Prerequisites

- Python 3.12
- Docker Desktop or Docker Engine with Compose
- Git
- A local PostgreSQL client, or PostgreSQL tools inside the Docker container

### 1. Set Up Python

**Windows PowerShell:**

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-pipeline.txt
python -m pip install -r requirements-analytics.txt
python -m pip install -r requirements-dashboard.txt
```

To enable Thinking Machines Inkling preference extraction, set
`TINKER_API_KEY` in the local environment before starting Streamlit. The
application does not display or persist this key. Without it, the agent uses a
conservative local parser and clearly labels the fallback.

Set the shared team key only in the local terminal that launches Streamlit;
do not put it in Git, `launch.json`, or Streamlit configuration files.

**Windows PowerShell:**

```powershell
$env:TINKER_API_KEY = "paste-the-team-key-here"
python -m streamlit run dashboard/app.py
```

**Linux/macOS:**

```bash
export TINKER_API_KEY="paste-the-team-key-here"
python -m streamlit run dashboard/app.py
```

**Linux/macOS:**

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-pipeline.txt
python -m pip install -r requirements-analytics.txt
python -m pip install -r requirements-dashboard.txt
```

### 2. Prepare the Dataset

Download `products.csv` and `reviews.csv` from the pinned DataHive dataset revision into `data/raw/`.

The raw data files are excluded from Git.

See [Database Setup](docs/database-setup.md) for detailed source verification and initialization instructions.

### 3. Start PostgreSQL

```bash
docker compose up -d --wait db
```

Initialize the database using the documented A1 snapshot-loading process:

```bash
python pipeline/load_snapshot.py
```

The snapshot importer requires PostgreSQL client tools. On Windows, where `psql` may not be installed locally, follow the Docker-based alternative in the database setup documentation.

### 4. Launch the Dashboard

```bash
python -m streamlit run dashboard/app.py
```

Open the local URL displayed by Streamlit, typically:

`http://localhost:8501`

The dashboard uses PostgreSQL for product and review data and reads precomputed B1/B2 results from:

```text
data/processed/product_rating_comparison.csv
data/processed/product_pros_cons_cards.csv
```

These two analysis result files are included in the repository.

### 5. Run Tests

```bash
python -m pytest tests/ -q
```

Latest local regression result on the AI Shopping Agent branch:

**80 passed, 10 subtests passed.**

## Airflow Pipeline

Start the Airflow services:

```bash
docker compose -f compose.yaml -f compose.airflow.yaml up -d --build
```

Open `http://localhost:8080` and manually trigger the `reviewtrust_etl` DAG.

The DAG is intentionally unscheduled for the historical snapshot. Its five tasks verify source files, clean, validate, load, and monitor.

## Limitations

- The dataset is historical, not a live Amazon feed.
- Product-page ratings may differ from sampled-review averages.
- Most products have limited sampled review coverage.
- Trust-adjusted ratings are experimental analytical estimates, not official Amazon ratings.
- Unusual review patterns are not proof of fraud.
- B2 pros and cons reflect patterns in available review text, not guaranteed product properties.
- The dashboard requires a populated PostgreSQL database for its core product and review views.
- Requirements that cannot be verified from historical catalog data remain
  unknown and are excluded from the recommendation ranking.

## Project Documentation

For detailed dashboard behavior, integration interfaces, and setup notes, see [Dashboard Guide](docs/dashboard-handoff.md).
