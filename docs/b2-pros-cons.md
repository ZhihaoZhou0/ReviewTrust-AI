# B2: Pros & Cons Extraction and NLP Evaluation

B2 turns each product's reviews into a ranked list of **pros** and **cons**, each backed by review evidence, and measures how reliable that output is.

B2 runs on its own. It does not need B1's anomaly models or Team A's database, and it changes no B1 files. Integration points are listed at the end.

## Files

| Path | Purpose |
| --- | --- |
| `nlp/pros_cons/schema.py` | Input contract: maps B1 or A1 columns to one internal schema; optional B1 weight join |
| `nlp/pros_cons/text.py` | Cleaning, sentence splitting, clause splitting at contrast words |
| `nlp/pros_cons/aspects.py` | Cross-category aspect lexicon (20 aspects) and longest-phrase matcher |
| `nlp/pros_cons/sentiment.py` | Clause sentiment: built-in lexicon with negation (default) or VADER (optional) |
| `nlp/pros_cons/extract.py` | Mention extraction, per-product ranking, dashboard cards |
| `analytics/pros_cons_evaluation.py` | Gold-label metrics, automatic checks, annotation templates |
| `run_pros_cons.py` | Command-line extraction |
| `evaluate_pros_cons.py` | Command-line evaluation (`gold`, `auto`, `sample`, `sheet`, `score-sheet`) |
| `tests/test_pros_cons.py`, `tests/test_pros_cons_evaluation.py` | Unit tests |
| `tests/fixtures/pros_cons_seed_gold.csv` | 50 hand-written labeled sentences for regression testing |

## Method (v1: `b2-lexicon-v1`)

For each review:

1. **Clean and split** the text into sentences, then split each sentence into clauses at contrast words (`but`, `however`, `although`, `though`, `except`, `;`). Example: *"Keeps water cold all day, but the lid leaks"* becomes two clauses with opposite opinions.
2. **Find aspects** in each clause with a curated lexicon (durability, size & fit, leaks, taste, value, ...). The longest phrase wins, so *"easy to clean"* counts as cleaning, not ease of use. Some terms carry their own polarity (*"fell apart"*, *"leak proof"*), and some aspects have context cues (*"keeps ... cold"*).
3. **Score clause sentiment** in [-1, 1], with negation handling (*"does not leak"* is positive). Clauses with |score| < 0.2 are neutral and produce no pro or con.

For each product:

4. **Count distinct source records** per (aspect, polarity), so neither one long review nor exact source repeats can dominate. All rows are kept, as the A1 contract requires; rows with the same `source_row_hash` share one `record_key` and count once.
5. **Filter and rank**: keep aspects mentioned by at least 3 reviews and 3% of the product's text reviews; rank by review count (or by B1-weighted count, see below); keep the top 5 per side.
6. **Attach evidence**: up to 3 distinct clauses per item, preferring clear, readable and helpful ones. Duplicated text is shown once.

**Star ratings are never used to decide polarity.** This keeps them available as an independent check in the evaluation, and it lets B2 find cons inside 4 to 5 star reviews, which dominate this dataset.

### Why a lexicon for v1

- Explainable: every pro / con traces back to a matched term and an evidence sentence, which the dashboard can show.
- Fast and dependency-free: about one minute for all 252K reviews on a laptop, no model downloads.
- A baseline to beat: the evaluation tooling is backend-agnostic, so a transformer or LLM extractor can replace step 2 or 3 later and be compared on the same gold set.

## Running it

From the repository root, after A1's cleaner and B1's `prepare_nlp_data.py` have produced `data/processed/reviews_b1_nlp.csv`:

    python run_pros_cons.py --top-products 50     # quick run, same product selection as run_similarity.py
    python run_pros_cons.py                       # all products

    python -m pytest tests/test_pros_cons.py tests/test_pros_cons_evaluation.py

Outputs in `data/processed/` (git-ignored):

| File | Grain | Use |
| --- | --- | --- |
| `pros_cons_mentions.csv` | one row per clause x aspect | Debugging, evaluation, future DB table |
| `product_pros_cons.csv` | one row per product x polarity x rank | Main result, future DB table |
| `product_pros_cons_cards.csv` | one row per product, pros / cons as JSON | Ready for Streamlit |
| `pros_cons_run.json` | run metadata | Reproducibility |

## NLP evaluation protocol

| Layer | Command | Metrics | Needs labels? |
| --- | --- | --- | --- |
| 1. Sentence gold set | `evaluate_pros_cons.py gold --gold <file>` | Micro P / R / F1 for aspect detection and for aspect + polarity; polarity accuracy; per-aspect table; error list | Yes |
| 2. Automatic checks | `evaluate_pros_cons.py auto` | Con share by star level; Spearman correlation between review net opinion and stars; share of cons from 4 to 5 star reviews; coverage; evidence faithfulness; top-3 stability (Jaccard) under 80% subsampling | No |
| 3. Product-level review | `evaluate_pros_cons.py sheet`, then `score-sheet` | Precision of displayed pros / cons (yes = 1, partial = 0.5, no = 0), by polarity | Yes (quick judgements) |

How to build the real gold set:

1. `python evaluate_pros_cons.py sample --n-per-star 40` exports 200 sentences, stratified by star level so cons are represented. Predictions are hidden from annotators to avoid anchoring.
2. Fill `gold_labels` as `aspect:pro;aspect:con` using the aspect keys in `aspects.py` (empty = no aspect opinion). Two annotators on an overlapping subset lets us report agreement.
3. Save as `data/processed/evaluation/gold_sentences.csv` and run the `gold` command. Compare backends with `--sentiment lexicon vader`.

Annotation files contain review text, so they stay under the git-ignored `data/` folder, following the A1 rule not to commit review text.

**Seed set results** (50 hand-written sentences, so optimistic; not a substitute for real-review labels):

| Backend | Aspect + polarity P / R / F1 | Aspect detection F1 | Polarity accuracy |
| --- | --- | --- | --- |
| lexicon (default) | 0.920 / 0.868 / 0.893 | 0.913 | 0.979 |
| VADER | 0.932 / 0.774 / 0.845 | 0.866 | 0.976 |

**First human review on real data** (10 products from the 50 most-reviewed, 73 extracted pros / cons, judged by the four team members):

| Metric | Value |
| --- | --- |
| Precision (yes = 1, partial = 0.5, no = 0) | 0.938 |
| Strict precision (yes only) | 0.877 |
| Precision for cons / pros | 0.957 / 0.930 |
| Items judged "no" | 0 |

All nine "partial" items traced to four causes, fixed in the next version: "pretty" used as an intensifier ("pretty fast") or "solid" as a modifier ("solid color") matched as aspects; "cost effective" and "package" (meaning a bundle) assigned to the wrong aspect; a negated context cue ("doesn't keep food cold") not flipping polarity; and sentence-initial "While ..., ..." / "However, ..." not split. Re-review with `evaluate_pros_cons.py sheet --previous <old sheet>`, which keeps judgements for unchanged items so only new or changed items need judging.

Known failure types in the seed set: implicit opinions without sentiment words (*"the battery lasts all week"*), comparative or conditional phrasing (*"not what I expected"*), and generic words matched in the wrong sense (*"fit in my bag"* read as size & fit).

## Interfaces with other workstreams

Status after PR #3 (A1 + A2 merged into the B1 branch).

### Input contract (settled by PR #3)

| Item | Contract | B2 behavior |
| --- | --- | --- |
| Input file | `data/processed/reviews_b1_nlp.csv` from `prepare_nlp_data.py` (A1 `reviews_clean.csv` also works) | Default `--input` |
| Row key | `source_row_number`, unique within the pinned source revision | Used as `review_id`; non-unique keys raise an error |
| Repeated content | All 255,966 source rows are kept; `source_row_hash` is **not** unique (3,832 exact repeats) | Used as `record_key`; each source record counts once in pros / cons |
| Text and rating | `body`, `stars` | Rows with blank `body` are skipped, as the contract says for Team B |
| Scope | All reviews, 1999 to 2025 | No date filter |
| Legacy `id` column | Pre-PR #3 B1 view | Still accepted |

### With B1 (optional weighting)

`--weights data/processed/weighted_review_results.csv` joins B1 weights on `source_row_number`.

B1's `review_weight` is `text_weight x source_duplicate_weight`, where the second factor is 1 / number of exact source repeats. B2 already collapses those repeats through `record_key`, so it uses **`text_weight`** when present; using `review_weight` would discount repeats twice. If only `review_weight` exists, B2 falls back to it.

Counts stay raw; only the ranking uses the weighted count. B1's anomaly scores are not used, matching B1's position that they are not evidence of fake reviews. Verified end to end: A1-format input, then `prepare_nlp_data.py`, `run_similarity.py --all-products`, `run_weighted_rating.py`, then `run_pros_cons.py --weights ...`.

### With Team A (still open)

1. **Output tables.** Proposed DDL for A1 to own in `database/schema.sql` (B2 writes, C reads):

        CREATE TABLE IF NOT EXISTS reviewtrust.review_aspect_mentions (
            source_row_number bigint NOT NULL,      -- row key, matches reviewtrust.reviews
            source_row_hash   char(64),             -- record key for counting
            asin              text NOT NULL REFERENCES reviewtrust.products(asin),
            sentence_index    integer NOT NULL,
            clause_index      integer NOT NULL,
            aspect            text NOT NULL,
            polarity          text NOT NULL CHECK (polarity IN ('pro', 'con')),
            sentiment_score   numeric(5, 4) NOT NULL,
            matched_terms     text NOT NULL,
            clause_text       text NOT NULL,
            method_version    text NOT NULL,
            PRIMARY KEY (source_row_number, sentence_index, clause_index, aspect, method_version)
        );

        CREATE TABLE IF NOT EXISTS reviewtrust.product_pros_cons (
            asin                  text NOT NULL REFERENCES reviewtrust.products(asin),
            polarity              text NOT NULL CHECK (polarity IN ('pro', 'con')),
            rank                  smallint NOT NULL CHECK (rank >= 1),
            aspect                text NOT NULL,
            aspect_label          text NOT NULL,
            review_count          integer NOT NULL,
            weighted_review_count numeric NOT NULL,
            n_text_reviews        integer NOT NULL,
            mention_share         numeric(5, 4) NOT NULL,
            avg_stars             numeric(3, 2) NOT NULL,
            opposing_review_count integer NOT NULL,
            consensus             numeric(5, 4) NOT NULL,
            support_level         text NOT NULL CHECK (support_level IN ('low', 'medium', 'high')),
            evidence              jsonb NOT NULL,   -- [{review_id, text, stars}]
            method_version        text NOT NULL,
            computed_at           timestamptz NOT NULL DEFAULT now(),
            PRIMARY KEY (asin, polarity, rank, method_version)
        );

2. **Incremental loading (A2).** Product summaries depend on all of a product's reviews, so after an A2 batch, B2 should recompute only the ASINs touched by that batch and replace their summary rows. Mention rows are keyed by `source_row_number`, so new rows only add mentions. A2's docs note that future source revisions need a composite (revision, position) key; B2's `--id-column` can point at it once it exists.

### With C and D

- D can read `product_pros_cons_cards.csv` (or the table above): `pros` / `cons` are JSON lists with `label`, `review_count`, `share`, `consensus`, `support_level` and `evidence`.
- Show `share` as "mentioned in N% of reviews". Show `consensus` when an aspect appears on both sides; for example, size & fit can be a top con with consensus 0.35, meaning most reviews that mention fit are positive. Grey out `low` support items.
- Label results as based on the sampled reviews (about 100 per product), consistent with how A1 labels `sample_rating`.

## Limitations and next steps

- Lexicon coverage: implicit opinions and category-specific aspects (for example "straw", "zipper") are missed. Next: mine frequent noun phrases per category from the real data to extend the lexicon, then re-run the gold evaluation.
- Generic words can match the wrong sense ("fit in my bag"). Next: per-category aspect lists from `category_breadcrumbs`.
- Sarcasm and comparisons are not handled.
- A transformer aspect-sentiment model or an LLM extractor can be evaluated against this baseline with the same gold set.
