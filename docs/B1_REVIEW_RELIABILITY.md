# B1 — Review Reliability Analysis

## 1. Overview

The B1 module analyzes review reliability using text similarity, anomaly detection, source-level deduplication, and reliability-weighted product ratings.

It consumes the cleaned review dataset produced by A1 and generates review-level and product-level outputs for downstream integration with the data pipeline, PostgreSQL, and dashboard.

The module identifies potentially suspicious review patterns. It does not establish whether individual reviews are fake or AI-generated.

## 2. Methods

### 2.1 Text Similarity Detection

- Uses TF-IDF vectorization and cosine similarity.
- Compares review texts within the same product (`asin`).
- Uses a similarity threshold of 0.85.
- Requires at least 50 characters for similarity-based detection.
- Excludes repeated source records from independent similarity comparisons using `source_row_hash`.

### 2.2 Rule-Based Reliability Analysis

The rule-based anomaly score uses two indicators:

- High text similarity: +0.6.
- Independent exact-text duplication: +0.4.

Reviews with anomaly scores of at least 0.6 are flagged for further inspection.

These flags indicate suspicious patterns rather than confirmed fraudulent reviews.

### 2.3 Isolation Forest

An unsupervised Isolation Forest model identifies statistically unusual reviews using engineered review features.

The configured contamination rate is 0.02.

Isolation Forest results are reported separately and do not directly determine the final rating weights.

### 2.4 Source Deduplication and Review Weighting

Repeated source records are identified using `source_row_hash`.

Each record receives a source weight:

`source_duplicate_weight = 1 / source_duplicate_count`

Text reliability weights are assigned as follows:

| Review category | Text weight |
|---|---:|
| Normal review | 1.0 |
| Highly similar review | 0.8 |
| Exact duplicate text | 0.6 |

The final review weight is:

`review_weight = text_weight * source_duplicate_weight`

### 2.5 Product Rating Comparison

The module calculates three product-level ratings:

1. **Original Rating:** Mean rating across the input review records.
2. **Deduplicated Rating:** Rating adjusted for repeated source records.
3. **Adjusted Rating:** Rating calculated using both source deduplication and text reliability weights.

The adjusted rating is calculated as:

`adjusted_rating = sum(rating * review_weight) / sum(review_weight)`

These metrics are intended for comparison and sensitivity analysis, not as verified estimates of product quality.

## 3. Input Data

**Input file:** `data/processed/reviews_clean.csv`

The module uses A1's cleaned dataset and relies on these identifiers:

| Field | Purpose |
|---|---|
| `asin` | Product identifier |
| `source_row_number` | Unique source-row identifier within the dataset snapshot |
| `source_row_hash` | Identifies repeated source records |

The preprocessing step preserves all source review records for traceability.

## 4. How to Run

Run the following commands from the repository root after installing the project dependencies.

**Step 1 — Prepare NLP data**

```bash
python prepare_nlp_data.py
```

**Step 2 — Run similarity analysis**

```bash
python run_similarity.py --all-products
```

**Step 3 — Generate weighted ratings**

```bash
python run_weighted_rating.py
```

**Step 4 — Run tests**

```bash
python -m pytest tests/ -q
```

## 5. Output Files

| Output file | Description |
|---|---|
| `data/processed/reviews_b1_nlp.csv` | Prepared NLP input with review-level features |
| `data/processed/similarity_results.csv` | Text similarity and anomaly analysis |
| `data/processed/weighted_review_results.csv` | Review-level reliability weights and indicators |
| `data/processed/product_rating_comparison.csv` | Product-level rating comparison |

Generated datasets are excluded from Git tracking and must be produced by running the pipeline.

## 6. Full Dataset Validation

The B1 workflow was executed against A1's cleaned dataset.

| Metric | Result |
|---|---:|
| Total review records | 255,966 |
| Distinct products | 2,689 |
| Additional duplicate source records | 3,832 |
| Rule-based flagged reviews | 108 |
| Isolation Forest flagged reviews | 5,120 |
| Products with rating comparisons | 2,671 |
| Automated tests passed | 22 |

All source records were preserved during preprocessing and analysis.

## 7. Integration Notes

The B1 outputs can be consumed by downstream database and dashboard components.

- Use `asin` to associate product-level rating results with products.
- Use `source_row_number` to associate review-level results with the corresponding source records from the same dataset snapshot.
- Use `product_rating_comparison.csv` to display original, deduplicated, and adjusted ratings.
- Use `weighted_review_results.csv` to display review weights and reliability indicators.

The exact database loading process and downstream integration should be coordinated with the A1/A2 and dashboard modules.

## 8. Limitations

- High text similarity does not prove that a review is fake.
- Isolation Forest detects statistical anomalies rather than confirmed fraud.
- The module does not include a dedicated AI-generated text classifier.
- The reliability weights are heuristic rather than calibrated probabilities.
- Product ratings are based on the available dataset sample, not necessarily all Amazon reviews.
- Adjusted ratings should be presented as experimental indicators.