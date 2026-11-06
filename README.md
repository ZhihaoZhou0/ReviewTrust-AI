# ReviewTrust AI

**A product has 4.8 stars. Can you trust the reviews behind that number?**

ReviewTrust AI is a hackathon project for exploring the reliability of Amazon product reviews. Our goal is a simple decision flow: search for a product, inspect unusual review patterns, compare the original rating with an explainable weighted rating, read evidence-backed pros and cons, and compare two products side by side.

Review signals are clues, not proof that a review is fake. The dashboard will show how each score is calculated and make the limits of the sampled data visible.

## The demo we are building

1. **Find a product:** Search and filter products.
2. **Understand its reviews:** See similarity and timing signals alongside the original and weighted ratings.
3. **Read the evidence:** Explore recurring pros and cons with representative review excerpts.
4. **Compare two options:** View ratings, review volume, signals, and tradeoffs together.

The planned MVP uses PostgreSQL, Python analysis modules, and a Streamlit + Plotly dashboard. The Python data access layer will integrate the modules; a separate FastAPI service is not part of the MVP.

## Build status

| Workstream | Scope | Status |
| --- | --- | --- |
| A1 - Data foundation | Read and audit the dataset, clean records, define the schema, and load PostgreSQL | **Finished on the [A1 feature branch](https://github.com/ZhihaoZhou0/ReviewTrust-AI/tree/feature/a1-data-foundation)** |
| A2 - Data pipeline | Incremental loading, Airflow orchestration, and data quality checks | Planned |
| B1 - Trust analytics | Review similarity, anomaly signals, and explainable weighted ratings | Planned |
| B2 - NLP | Pros and cons extraction and evaluation | Planned |
| C - Integration | Python data access, PostgreSQL queries, and module integration | Planned |
| D - Dashboard | Product search, trust views, pros and cons, and two-product comparison | Planned |

## A1: completed data foundation

The A1 implementation uses the pinned [DataHive Amazon Reviews Dataset](https://huggingface.co/datasets/datahiveai/Amazon-Reviews-Dataset), with separate product and review CSV files joined by ASIN. The dataset is a sample, not a complete or live view of Amazon reviews.

- **Audited:** 2,727 products and 255,966 raw review rows. Every raw review ASIN matched a product. Review dates span July 1999 to July 2025.
- **Cleaned:** Removed 3,832 exact duplicate review rows, leaving 252,134 reviews. Empty review text and unknown verified-purchase status remain nullable. Conflicting records that share a source review ID are preserved.
- **Modeled:** PostgreSQL tables have product keys, an internal review key, a product-review foreign key, source-row hashes, validation constraints, and query indexes. The product-page rating is stored separately from the mean of sampled reviews.
- **Loaded:** A Docker Compose PostgreSQL 16 service and a transactional import command reproduce the local database. The import was run twice: the first run inserted 2,727 products and 252,134 reviews; the second inserted no new rows.

Most reviewed products in this dataset have exactly 100 sampled reviews, and the purchase-verification field is either true or unknown. These limits matter when interpreting future trust scores.

The finished code, audit report, data contract, and setup instructions are on the [A1 feature branch](https://github.com/ZhihaoZhou0/ReviewTrust-AI/tree/feature/a1-data-foundation). Start with its [database setup guide](https://github.com/ZhihaoZhou0/ReviewTrust-AI/blob/feature/a1-data-foundation/docs/database-setup.md). The raw and cleaned CSV files are excluded from that branch; the guide links to the pinned download commands.

## Next milestone

Connect A2's scheduled data pipeline and B1/B2's analysis outputs to the shared PostgreSQL foundation, then build the Streamlit comparison flow for the hackathon demo.
