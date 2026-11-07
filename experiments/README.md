# SBERT Semantic Similarity Experiments

## Overview

This directory contains exploratory experiments evaluating Sentence-BERT (SBERT) for semantic similarity analysis of Amazon product reviews.

The goal is to investigate whether transformer-based sentence embeddings can identify semantically similar reviews that traditional TF-IDF similarity may overlook.

These experiments are independent of the production B1 Review Reliability Analysis pipeline. **SBERT similarity scores are not currently used to modify review reliability weights or product ratings.**

## Dataset and Methods

- **Dataset:** Amazon product reviews from the B1 preprocessing pipeline
- **Input:** `data/processed/reviews_b1_nlp.csv`
- **Products sampled:** 50
- **Reviews sampled:** 3,737
- **Within-product review pairs:** 143,831
- **SBERT model:** `sentence-transformers/all-MiniLM-L6-v2`
- **Embedding similarity:** Cosine similarity using normalized embeddings
- **Exploratory SBERT threshold:** 0.80
- **Random seed:** 42
- **Execution:** PyTorch with CUDA GPU acceleration when available

Reviews are compared only against other reviews of the same product. Duplicate source records are removed before similarity computation.

## Experiment 1: TF-IDF vs. SBERT

**Script:** `sbert_similarity.py`

This experiment compares lexical similarity using TF-IDF against semantic similarity using SBERT.

TF-IDF uses unigram and bigram features, English stop-word removal, and cosine similarity.

SBERT uses pretrained sentence embeddings to capture semantic relationships beyond exact word overlap.

### Results

| Metric | Result |
|---|---:|
| Products | 50 |
| Reviews | 3,737 |
| Review pairs | 143,831 |
| Mean TF-IDF similarity | 0.0225 |
| Mean SBERT similarity | 0.3870 |
| TF-IDF pairs above 0.85 | 0 |
| SBERT pairs above 0.80 | 371 |

Manual inspection identified semantically related reviews with low lexical overlap, including reviews discussing similar product qualities and experiences.

**Important:** The thresholds are exploratory and different between methods. Candidate counts are not a calibrated measure of model accuracy or superiority.

## Experiment 2: Text Cleaning Ablation

**Script:** `sbert_cleaning_ablation.py`

Initial analysis revealed that Amazon reviews sometimes contain the repeated placeholder:

`The media could not be loaded.`

This non-review text can artificially influence semantic similarity scores.

A controlled ablation experiment compares SBERT similarity before and after removing this placeholder while keeping the same reviews, review pairs, model, and threshold.

### Results

| Metric | Before cleaning | After cleaning |
|---|---:|---:|
| Review pairs | 143,831 | 143,831 |
| Mean SBERT similarity | 0.3821 | 0.3870 |
| High-similarity pairs (≥ 0.80) | 398 | 371 |

Candidate-level changes:

- 357 pairs remained above the threshold.
- 41 pairs dropped below the threshold.
- 14 pairs newly exceeded the threshold.
- Net reduction: 27 high-similarity pairs (approximately 6.8%).

In one manually examined example, similarity decreased from 0.923 to 0.431 after removing the placeholder.

The results demonstrate that preprocessing can materially affect transformer-based similarity detection. They do not establish that all removed candidates were false positives.

## Running the Experiments

From the project root, activate the project's Python environment and install the required dependencies.

The experiments require pandas, NumPy, scikit-learn, PyTorch, and sentence-transformers.

Run the TF-IDF vs. SBERT experiment:

```bash
python experiments/sbert_similarity.py
```

Run the fixed-sample cleaning ablation:

```bash
python experiments/sbert_cleaning_ablation.py
```

Results are saved to:

- `data/processed/sbert_experiment/`
- `data/processed/sbert_cleaning_ablation/`

Generated CSV files are excluded from Git through the project's `.gitignore`.

## Limitations and Future Work

1. **Semantic similarity is not evidence of fraud.** Genuine customers can independently describe similar product experiences.
2. **No labeled fraud benchmark:** Current results do not establish precision, recall, or F1 for fraudulent review detection.
3. **Uncalibrated thresholds:** The similarity cutoffs require validation before production use.
4. **Sample scope:** Results are based on 50 sampled products rather than the full dataset.
5. **Semantic contradictions:** High embedding similarity does not guarantee that two reviews express the same sentiment or factual claims.

Potential future improvements include human-labeled evaluation, contradiction-aware semantic comparison, and combining semantic similarity with independent behavioral signals.

## Integration Status

The existing B1 reliability scoring pipeline remains unchanged.

SBERT is currently an optional research component for discovering semantically similar review candidates. Any future integration into reliability scoring should be supported by additional evaluation and calibration.