# Dashboard Integration and Team Handoff

## Overview

The ReviewTrust AI Streamlit dashboard integrates product discovery, PostgreSQL-backed review exploration, experimental B1 reliability analytics, and B2 evidence-backed pros and cons.

The integrated dashboard was merged into `main` through Pull Request #6.

The interface supports a consumer-facing workflow for discovering products, inspecting review evidence, and comparing two products.

## Run Locally

From the repository root, after initializing PostgreSQL as described in [Database Setup](database-setup.md):

```bash
python -m pip install -r requirements-dashboard.txt
docker compose up -d --wait db
python -m streamlit run dashboard/app.py
```

Streamlit typically opens at:

`http://localhost:8501`

If the default port is occupied, Streamlit may use another port.

The database connection defaults to the A1 local PostgreSQL instance at `127.0.0.1:5433`.

Supported environment variables:

- `PGHOST`
- `PGPORT`
- `PGDATABASE`
- `PGUSER`
- `PGPASSWORD`

The dashboard requires a populated PostgreSQL database for product discovery and review exploration.

## User Experience

### Product Discovery

Users can browse image-led categories, featured products, and review-based shortlists.

The search interface supports product names, ASINs, and category filtering.

### Amazon URL Comparison

Users can paste two full Amazon product URLs.

The application extracts ASINs locally and matches them against the historical dataset. It does not fetch live Amazon pages or resolve shortened links.

Only products represented in the local catalog can be compared.

### Product Inspection

Product details include:

- Product-page rating.
- Sampled-review mean.
- Sample review count.
- Historical review evidence.
- B1 reliability metrics when available.
- B2 recurring pros and cons when available.

### B1 Review Reliability

The B1 panel displays experimental trust-adjusted ratings alongside sampled-review averages.

Metrics include:

- Original sampled rating.
- Trust-adjusted rating.
- Rating difference.
- Number of adjusted reviews.
- Percentage of adjusted reviews.

These signals are analytical indicators and should not be interpreted as confirmed fake-review detection.

### B2 Pros and Cons

The B2 panel presents recurring positive and negative review aspects.

Users can expand an aspect to inspect supporting review excerpts.

The panel uses precomputed results rather than generating new NLP outputs on each dashboard interaction.

### Review Pulse

The dashboard provides aggregate review indicators, including star distributions, sampled-review counts, and comparisons with listed product ratings.

Detailed review evidence remains available through expandable interface elements.

### Side-by-Side Comparison

Users can compare two catalog products, including their listed ratings, sampled-review averages, review counts, and available B1 reliability metrics.

## Data Access and Integration

### PostgreSQL Data Access

`dashboard/data_access.py`

Provides product discovery, product snapshots, and review evidence from PostgreSQL.

The dashboard uses a Python data access layer rather than a separate API service.

### B1/B2 Analysis Access

`dashboard/analysis_access.py`

Loads precomputed analytics from:

```text
data/processed/product_rating_comparison.csv
data/processed/product_pros_cons_cards.csv
```

The B1 output provides product-level rating adjustments.

The B2 output provides product-level positive and negative aspects with supporting evidence.

Both files are included in the repository.

The application handles unavailable analysis results separately from the core PostgreSQL product data.

## Interface Design

The dashboard uses custom HTML and CSS within Streamlit.

Visual features include:

- Image-led product discovery.
- Responsive product cards.
- Product comparison layouts.
- CSS entrance and hover transitions.
- Accessible focus behavior.
- Reduced-motion support using `prefers-reduced-motion`.

Typography uses Bricolage Grotesque, Onest, and DM Mono, with system font fallbacks.

The dashboard uses CSS-based rating visualizations rather than requiring Plotly for those elements.

## Validation

The integrated dashboard has been manually inspected using the populated PostgreSQL database.

Verified interactions include:

- Product browsing and search.
- Amazon URL matching.
- Product inspection.
- B1 reliability metric display.
- B2 expandable review evidence.
- Two-product comparison.

Automated regression tests after merging PR #6:

**63 passed, 10 subtests passed.**

Run:

```bash
python -m pytest tests/ -q
```

## Limitations

- The underlying review snapshot is historical.
- Product-page ratings and sampled-review averages are different measures.
- Most products have at most 100 sampled reviews.
- Trust adjustments are experimental and are not fraud verdicts.
- Pros and cons are extracted from available review text and may not represent every customer experience.
- Product data and reviews require PostgreSQL; precomputed B1/B2 CSV files do not replace the database.
- The application does not provide live Amazon pricing, purchasing, or real-time review updates.