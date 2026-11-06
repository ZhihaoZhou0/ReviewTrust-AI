# Dashboard Milestone 1 and Team Handoff

The Streamlit preview is implemented on the D feature branch. It reads the completed A1 PostgreSQL database and deliberately leaves B1/B2 analysis unfilled.

## Run locally

From the repository root, after following [database-setup.md](database-setup.md):

    python3.12 -m venv .venv
    .venv/bin/python -m pip install -r requirements-dashboard.txt
    docker compose up -d --wait db
    python3 pipeline/load_snapshot.py
    .venv/bin/streamlit run dashboard/app.py

The dashboard opens at http://localhost:8501. It expects the A1 local database at 127.0.0.1:5433 by default. The data access layer also accepts PGHOST, PGPORT, PGDATABASE, PGUSER, and PGPASSWORD, matching the A1 loader.

## Current user flow

1. Search by product name or ASIN, optionally filter by category, and choose a result.
2. Inspect the product-page rating, the mean of cleaned sampled reviews, sample size, review date range, and a Plotly rating distribution.
3. Read a small set of original review excerpts with their source IDs.
4. Choose two products and compare the same factual metrics side by side.

The "Review trust" and "Pros & Cons" panels are explicit pending states. The app does not invent weighted ratings, fraud labels, or extracted themes.

## Integration boundary for B1, B2, and C

The current read-only adapter is [dashboard/data_access.py](../dashboard/data_access.py). Team C can replace its PostgreSQL queries without changing the Streamlit layout if it preserves the Product, ProductSnapshot, and ReviewExcerpt shapes.

- **B1 trust result:** For each ASIN, provide the weighted rating, the number of sampled reviews used, a versioned weight rule, and a list of anomaly signals. Each signal should have a label, measured value, and plain-language explanation. Treat signals as indicators, not confirmed fake reviews.
- **B2 pros and cons result:** For each ASIN, provide separate positive and negative aspects. Each aspect should include a label, mention count, and at least one real review excerpt with its source review ID.
- **C integration:** Expose one Python function per product to retrieve the B1 and B2 results, returning an explicit unavailable state when analysis has not run. Keep calculation code outside dashboard/app.py.

The product-page rating and sampled-review mean must remain separate. The dataset includes at most 100 source reviews for most products and does not provide a useful verified-versus-unverified purchase split.

## Validation

The adapter queried all 2,727 products from the local database; a product snapshot's star-count sum matched its sample count. Streamlit AppTest rendered both tabs and verified search, empty results, and same-product comparison feedback. The live page was also checked in a browser after fixing the entrypoint import path.
