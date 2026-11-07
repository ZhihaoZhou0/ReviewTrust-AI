# Dashboard Milestone 1 and Team Handoff

The Streamlit evidence desk is implemented on the D feature branch. It reads the completed A1 PostgreSQL database and keeps unfinished trust and theme analysis in a clearly labeled future state. The interface presents a consumer-facing research flow: a product-led hero with a working A vs B picker, image-led categories, a staggered four-product feature, a filterable catalog grid, a review-based Best Buy shortlist, product search, aggregate evidence, and comparison. All UI copy is in English.

## Run locally

From the repository root, after following [database-setup.md](database-setup.md):

    python3.12 -m venv .venv
    .venv/bin/python -m pip install -r requirements-dashboard.txt
    docker compose up -d --wait db
    python3 pipeline/load_snapshot.py
    .venv/bin/python -m streamlit run dashboard/app.py

The dashboard opens at http://localhost:8501. It expects the A1 local database at 127.0.0.1:5433 by default. The data access layer also accepts PGHOST, PGPORT, PGDATABASE, PGUSER, and PGPASSWORD, matching the A1 loader.

## Current user flow

1. Select two popular products in the hero to preview their sampled means and open the full comparison.
2. Open an image-led category, a featured product, a Best Buy candidate, or search by product name or ASIN.
3. Inspect the product-page rating, sampled mean, review count, and aggregate review pulse. Hover or focus a pulse card for its calculation context.
4. Expand the evidence panel when needed to see the Plotly rating distribution and original review excerpts with source IDs.
5. Use the Compare view to inspect two products side by side.

A small future-analysis note replaces large empty panels. The app does not invent weighted ratings, fraud labels, extracted themes, prices, or purchasing functionality. Product-page ratings and sample means are labeled separately throughout. Featured products use their actual catalog images and listed ratings. The Best Buy area is explicitly a **review-based candidate shortlist**, not a final price/value verdict: it requires at least 50 sampled reviews, a sampled mean of at least 4.5, and a listed rating of at least 4.4, then shows one candidate per category. Prices and B1 trust signals are not available yet.

The motion system uses CSS entrance and hover transitions, subtle hero movement, mixed-height product imagery, and aggregate review cards that reveal explanatory details on hover or keyboard focus. `prefers-reduced-motion` disables animation and keeps aggregate details visible. Original reviews are collapsed by default to keep the main decision flow concise.

## Integration boundary for B1, B2, and C

The current read-only adapter is [dashboard/data_access.py](../dashboard/data_access.py). Team C can replace its PostgreSQL queries without changing the Streamlit layout if it preserves the Product, ProductSnapshot, and ReviewExcerpt shapes.

- **B1 trust result:** For each ASIN, provide the weighted rating, the number of sampled reviews used, a versioned weight rule, and a list of anomaly signals. Each signal should have a label, measured value, and plain-language explanation. Treat signals as indicators, not confirmed fake reviews.
- **B2 pros and cons result:** For each ASIN, provide separate positive and negative aspects. Each aspect should include a label, mention count, and at least one real review excerpt with its source review ID.
- **C integration:** Expose one Python function per product to retrieve the B1 and B2 results, returning an explicit unavailable state when analysis has not run. Keep calculation code outside dashboard/app.py.

The product-page rating and sampled-review mean must remain separate. The dataset includes at most 100 source reviews for most products and does not provide a useful verified-versus-unverified purchase split.

## Validation

The adapter queried all 2,727 products from the local database; a product snapshot's star-count sum matched its sample count. Streamlit AppTest rendered both views and verified search, empty results, side-by-side comparison, same-product feedback, and the product-to-compare action. The redesigned page was also inspected with real PostgreSQL data in Chrome.
