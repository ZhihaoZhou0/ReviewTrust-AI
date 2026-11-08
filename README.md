# ReviewTrust AI

**Trust the reviews before you trust the stars.**

*Can a 4.8-star product rating tell you what shoppers really experienced?*

ReviewTrust AI is a consumer-focused product discovery and review intelligence platform developed for a hackathon. It helps shoppers search historical Amazon product data, examine review-reliability signals, understand evidence-backed pros and cons, and compare products against their needs.

The application uses a **historical review snapshot**. Its trust signals are experimental, explainable indicators—not proof that any particular review is fraudulent.

## Key Features

1. **Hybrid product search:** Search by product name, ASIN, or natural-language description. A custom BM25 retriever is combined with pretrained Sentence-BERT (`all-MiniLM-L6-v2`) embeddings using Weighted Reciprocal Rank Fusion (RRF).
2. **Review reliability (B1):** Compare product-page ratings, sample-average ratings, and experimental trust-adjusted ratings; see how many review weights were adjusted.
3. **Evidence-backed pros and cons (B2):** Extract recurring positive and negative product aspects using a lexicon-based NLP pipeline with clause segmentation and negation handling, supported by original review excerpts.
4. **Product comparison:** Compare two products by Amazon URL or product selection, with ratings, B1 indicators, B2 themes, and original review evidence side by side.
5. **AI Shopping Agent:** Compare up to five supported Amazon products using natural-language preferences, B1/B2 evidence, and optional Thinking Machines Inkling preference extraction. When model inference is unavailable, the agent transparently falls back to local parsing.
6. **Three-view Streamlit dashboard:** Navigate between **AI Advisor**, **Compare**, and **Explore** to discover products, inspect evidence, and make comparisons.

### Example workflow

1. In **Explore**, search `something to keep my drinks cold` to find related products without using their exact names.
2. In **Compare**, inspect two products' sampled ratings, trust-adjusted ratings, and recurring pros and cons.
3. In **AI Advisor**, enter shopping priorities and up to five supported Amazon product links to request a review-backed recommendation.

## Architecture and Tech Stack

| Component | Implementation |
|---|---|
| Data source | Pinned historical DataHive Amazon Reviews snapshot |
| Data engineering | Python, pandas, CSV validation and cleaning, PostgreSQL, transactional loading, Apache Airflow |
| Review reliability (B1) | TF-IDF review similarity, duplicate detection, heuristic review weights, trust-adjusted sample ratings |
| Review understanding (B2) | Lexicon-based aspect extraction, sentence/clause segmentation, negation-aware sentiment rules, supporting excerpts |
| Keyword search | Custom BM25 over product titles and category information |
| Semantic search | Sentence Transformers `all-MiniLM-L6-v2`, 384-dimensional embeddings, cosine similarity |
| Hybrid ranking | Weighted RRF: 30% BM25, 70% Sentence-BERT |
| AI Shopping Agent | Natural-language preference extraction through Inkling when available, local fallback, B1/B2 evidence-based comparisons |
| Application | Streamlit, Python data access layer, HTML/CSS |
| Validation | Pytest regression tests, NLP evaluations, retrieval benchmark, manual UI walkthroughs |

The MVP uses a **Python data access layer**, not a separate FastAPI service. Product and review records are stored in PostgreSQL; precomputed B1/B2 analysis files are read by the dashboard. The current local demo uses Docker-based PostgreSQL.

### Search behavior

- **Short queries (fewer than four whitespace-separated words):** BM25.
- **Longer natural-language queries:** BM25 + Sentence-BERT rankings fused with weighted RRF.
- **Exact ASINs:** Exact product lookup.

The routing threshold and fusion weights are implementation choices, not proven optimal settings. The Sentence-BERT model is used **pretrained**, without task-specific fine-tuning.

## Build Status

| Workstream | Scope | Status |
|---|---|---|
| A1 – Data Foundation | Source audit, cleaning, schema, PostgreSQL snapshot import | Integrated |
| A2 – Data Pipeline | Data quality, incremental loading, Airflow orchestration | Integrated |
| B1 – Trust Analytics | Review reliability signals and trust-adjusted ratings | Integrated |
| B2 – NLP | Aspect-based pros/cons extraction and evaluation | Integrated |
| C – Integration | PostgreSQL access and B1/B2 result adapters | Integrated |
| D – Dashboard | AI Advisor, Compare, Explore, and review evidence | Integrated |
| Hybrid Product Search | BM25, Sentence-BERT, RRF, and search evaluation | Integrated |
| AI Shopping Agent | Requirements parsing, evidence-based ranking, optional Inkling and local fallback | Integrated |
| Regression Validation | 90 tests and 10 subtests passed on the tested `main` version | Passed |

## Data Foundation and Pipeline

The project uses the pinned [DataHive Amazon Reviews Dataset](https://huggingface.co/datasets/datahiveai/Amazon-Reviews-Dataset), revision `2531d9083bd3aab11261eab7e69d0d0f358a6d6f`.

The audited source contains:

- **2,727 products**.
- **255,966 review rows**.
- **3,832 additional rows with exactly repeated review content**, retained for analysis and traceability.

Most reviewed products have at most 100 sampled reviews. **Product-page ratings and sample-review means are separate measures** and should not be interpreted as before/after effects of B1.

A1 verifies raw-file SHA-256 digests, cleans CSV data without collapsing repeated reviews, creates PostgreSQL tables and indexes, and imports the snapshot transactionally.

A2 checks cleaned data against the A1 contract and audited counts, uses transactional batch checkpoints, and orchestrates verification, cleaning, validation, loading, and monitoring with Airflow. Replayed batches are skipped by source position; repeated review content remains available for analysis.

Detailed documentation:

- [Source Audit](docs/data-audit.md)
- [Data Contract](docs/data-contract.md)
- [Database Setup](docs/database-setup.md)
- [A2 Pipeline Guide](docs/etl-pipeline.md)
- [Dashboard Guide](docs/dashboard-handoff.md)

## Run Locally

### Prerequisites

- Python **3.12**
- Docker Desktop, or Docker Engine with Compose
- Git
- PostgreSQL client tools for some snapshot import operations (or use the documented Docker-based alternative)

Clone the repository and run the commands from its root directory.

### 1. Set up Python dependencies

**Windows PowerShell**

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-pipeline.txt
python -m pip install -r requirements-analytics.txt
python -m pip install -r requirements-dashboard.txt
```

**Linux / macOS**

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-pipeline.txt
python -m pip install -r requirements-analytics.txt
python -m pip install -r requirements-dashboard.txt
```

### 2. Prepare the historical dataset (first-time setup)

Download `products.csv` and `reviews.csv` from the **pinned DataHive dataset revision** into `data/raw/`. Raw data files are intentionally excluded from Git.

Follow the [Database Setup guide](docs/database-setup.md) for source verification and initial database setup.

### 3. Start PostgreSQL

```bash
docker compose up -d --wait db
```

For a first-time database initialization, follow the A1 snapshot import procedure:

```bash
python pipeline/load_snapshot.py
```

The snapshot importer uses PostgreSQL client tools. On Windows, if `psql` is not installed, use the Docker-based alternative in [Database Setup](docs/database-setup.md). **If the local database is already populated, do not reimport the snapshot just to launch the dashboard.**

### 4. Optional: configure the AI Shopping Agent API key

The dashboard can run **without** a Thinking Machines API key; the shopping agent then uses its local rule-based fallback. To enable model-based preference extraction, provide `TINKER_API_KEY` **as an environment variable in the same shell that starts Streamlit**.

You may store the key in a local project-root `.env` file (ignored by Git) with this format:

```dotenv
TINKER_API_KEY=YOUR_NEW_PRIVATE_KEY
```

**Important:** The current agent reads `TINKER_API_KEY` from the process environment; merely creating `.env` does **not** automatically load it.

**Windows PowerShell — load from local `.env` without printing the key**

```powershell
$env:TINKER_API_KEY = (Get-Content .env | Where-Object { $_ -match '^TINKER_API_KEY=' } | Select-Object -First 1) -replace '^TINKER_API_KEY=', ''
python -c "import os; print('TINKER_API_KEY configured:', bool(os.getenv('TINKER_API_KEY')))"
```

**Linux / macOS — set the environment variable securely for the current shell**

```bash
read -r -s -p 'TINKER_API_KEY: ' TINKER_API_KEY; echo
export TINKER_API_KEY
```

Never commit actual keys to GitHub, add them to a tracked file, or show them in screenshots or logs. If a key is exposed, revoke and rotate it. A configured key does not guarantee that the external API will be available; check the agent's fallback warning during a demo.

### 5. Launch the dashboard

With PostgreSQL running and the virtual environment active:

```bash
python -m streamlit run dashboard/app.py
```

Open the local address printed by Streamlit, typically `http://localhost:8501`.

The application reads product/review data from PostgreSQL and precomputed analysis files:

```text
data/processed/product_rating_comparison.csv
data/processed/product_pros_cons_cards.csv
```

These two precomputed analysis files are included in the repository.

**Windows troubleshooting (OpenBLAS memory/thread initialization):** If Python exits during numerical library import with an `OpenBLAS ... Memory allocation` error, set these variables **before starting Python**:

```powershell
$env:OPENBLAS_NUM_THREADS = '1'
$env:OMP_NUM_THREADS = '1'
$env:MKL_NUM_THREADS = '1'
```

### 6. Run automated tests

```bash
python -m pytest tests/ -q
```

**Latest confirmed local regression result on the tested `main` version (`b557a17`): 90 passed, 10 subtests passed.**

If third-party pytest plugin auto-loading interferes with local test execution, it can be disabled for that shell:

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD = '1'
python -m pytest tests/ -q
```

The regression suite checks code behavior; it does not establish that the external Inkling API is reachable or that all UI interactions are covered automatically.

### 7. Stop local services

Stop Streamlit with `Ctrl+C` in its running terminal. To stop the project containers without deleting the database volume:

```bash
docker compose stop
```

## Airflow Pipeline (optional)

To run the Airflow services in addition to the database:

```bash
docker compose -f compose.yaml -f compose.airflow.yaml up -d --build
```

Open `http://localhost:8080` and manually trigger the `reviewtrust_etl` DAG. It is intentionally unscheduled for the historical snapshot and contains five tasks for source verification, cleaning, validation, loading, and monitoring.

Airflow is **not required** merely to view an already populated dashboard.

## Evaluation Notes

The search evaluation script is available at `scripts/evaluate_search.py`:

```bash
python -m scripts.evaluate_search
```

The preliminary retrieval experiment used **three queries and one labeled expected product per query**:

| Retrieval method | Hit@5 | MRR |
|---|---:|---:|
| BM25 | 0.667 | 0.673 |
| Sentence-BERT | 1.000 | 0.750 |
| Hybrid Search | 1.000 | 0.511 |

These numbers are a small reproducibility/smoke benchmark, **not a general accuracy estimate**. On this sample, Hybrid did not outperform standalone Sentence-BERT on MRR.

The B2 pipeline also has labeled evaluation and human-review tooling; see the source code and project documentation for its specific evaluation protocol and results.

## Limitations

- Review data is historical, not a live Amazon feed; product availability and current ratings may differ.
- Product-page ratings and sample-derived scores use different underlying populations.
- Most products have limited sampled review coverage.
- B1 trust-adjusted ratings are experimental estimates, **not official Amazon ratings**; unusual text patterns do not prove fraud.
- Isolation Forest and review-level SBERT similarity were explored separately; they do not directly determine the current B1 weighted rating.
- B2 pros and cons represent extracted patterns in available text, not guaranteed product properties.
- Search fusion weights and query routing were not optimized on a large benchmark.
- The core dashboard requires a populated PostgreSQL database; AI preference extraction can fall back when Inkling is unavailable.
- Requirements that cannot be verified from available catalog and review evidence should be treated as uncertain rather than confirmed matches.

## Project Documentation

For detailed UI behavior, data interfaces, and local setup notes, see the [Dashboard Guide](docs/dashboard-handoff.md). For pipeline details, see the other guides linked under [Data Foundation and Pipeline](#data-foundation-and-pipeline).
