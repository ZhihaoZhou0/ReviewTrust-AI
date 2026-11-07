"""Input contract for B2.

B2 accepts review tables from either source used in the project:

* B1 NLP view (prepare_nlp_data.py -> reviews_b1_nlp.csv) and
  A1 cleaned table / PostgreSQL: source_row_number, source_row_hash,
  source_review_id, asin, body, stars, ...
* Legacy B1 view (before PR #3): id, asin, body, stars, ...

Everything is normalized to one internal schema:

    review_id      unique row key (string); source_row_number by default
    record_key     source record key; rows that are exact source repeats
                   (same source_row_hash) share it and are counted once
    asin           product key
    text           review body (non-empty)
    stars          integer 1-5 (used for evaluation only, never for polarity)
    review_weight  float in (0, 1], defaults to 1.0 (B1 trust weight, optional)
    found_helpful  non-negative integer, defaults to 0 (used to pick evidence)
"""

from __future__ import annotations

import pandas as pd


METHOD_VERSION = "b2-lexicon-v1"

# Candidate columns, in priority order.
# source_row_number is the unique row key in the A1 / B1 contract (PR #3).
# source_row_hash is NOT unique: A1 keeps exact source repeats, so it is used
# as record_key (for counting) rather than as the row key.
ID_CANDIDATES = ["review_id", "source_row_number", "review_pk", "id", "source_review_id"]
RECORD_KEY_COLUMN = "source_row_hash"
TEXT_CANDIDATES = ["text", "body"]
STARS_CANDIDATES = ["stars", "rating"]

INTERNAL_COLUMNS = ["review_id", "record_key", "asin", "text", "stars", "review_weight", "found_helpful"]


def _pick(columns, candidates, explicit, role):
    """Return the first candidate column that exists, or the explicit choice."""
    if explicit is not None:
        if explicit not in columns:
            raise ValueError(f"{role} column '{explicit}' not found")
        return explicit
    for name in candidates:
        if name in columns:
            return name
    raise ValueError(f"No {role} column found; expected one of {candidates}")


def prepare_reviews(
    df: pd.DataFrame,
    id_column: str | None = None,
    text_column: str | None = None,
    stars_column: str | None = None,
) -> pd.DataFrame:
    """Normalize a review table to the B2 internal schema.

    Reviews with empty text are dropped (they carry no aspects), following the
    A1 data contract: Team B uses reviews with body IS NOT NULL.
    Raises ValueError if the chosen review key is not unique, because
    evidence and B1 weights are joined on it.

    All rows are kept, including exact source repeats (A1 contract). Repeats
    share a record_key so that summaries count each source record once.
    """
    columns = set(df.columns)
    id_col = _pick(columns, ID_CANDIDATES, id_column, "review id")
    text_col = _pick(columns, TEXT_CANDIDATES, text_column, "text")
    stars_col = _pick(columns, STARS_CANDIDATES, stars_column, "stars")
    if "asin" not in columns:
        raise ValueError("Missing required column: asin")

    out = pd.DataFrame({
        "review_id": df[id_col].astype("string"),
        "asin": df["asin"].astype("string"),
        "text": df[text_col].astype("string"),
        "stars": pd.to_numeric(df[stars_col], errors="coerce"),
    })

    if RECORD_KEY_COLUMN in columns:
        key = df[RECORD_KEY_COLUMN].astype("string")
        blank = key.isna() | (key.str.strip() == "")
        out["record_key"] = key.where(~blank, "row:" + out["review_id"])
    else:
        out["record_key"] = out["review_id"]

    # Optional columns with safe defaults.
    if "review_weight" in columns:
        out["review_weight"] = pd.to_numeric(df["review_weight"], errors="coerce").fillna(1.0)
    else:
        out["review_weight"] = 1.0
    if "found_helpful" in columns:
        out["found_helpful"] = pd.to_numeric(df["found_helpful"], errors="coerce").fillna(0)
    else:
        out["found_helpful"] = 0

    bad_weight = ~out["review_weight"].between(0, 1, inclusive="right")
    if bad_weight.any():
        raise ValueError("review_weight must be in (0, 1]")

    has_text = out["text"].notna() & (out["text"].str.strip().str.len() > 0)
    out = out[has_text & out["review_id"].notna() & out["asin"].notna()].copy()

    if out["review_id"].duplicated().any():
        n_dup = int(out["review_id"].duplicated().sum())
        raise ValueError(
            f"Review key '{id_col}' is not unique ({n_dup} repeats). "
            "Use a unique key such as source_row_number (--id-column)."
        )

    out["found_helpful"] = out["found_helpful"].astype(int)
    return out[INTERNAL_COLUMNS].reset_index(drop=True)


def attach_review_weights(
    reviews: pd.DataFrame,
    weights: pd.DataFrame,
    weight_id_column: str = "source_row_number",
    weight_column: str | None = None,
) -> pd.DataFrame:
    """Join B1 weights onto prepared reviews (optional integration).

    B1's review_weight = text_weight x source_duplicate_weight (1 / number of
    exact source repeats). B2 already counts each source record once through
    record_key, so it uses text_weight when present to avoid discounting
    repeats twice. Reviews without a matching weight keep weight 1.0.
    """
    if weight_column is None:
        weight_column = "text_weight" if "text_weight" in weights.columns else "review_weight"
    if weight_column not in weights.columns:
        raise ValueError(f"weights table has no {weight_column} column")
    if weight_id_column not in weights.columns:
        raise ValueError(f"weights table has no {weight_id_column} column")
    lookup = (
        weights[[weight_id_column, weight_column]]
        .rename(columns={weight_column: "review_weight"})
        .dropna()
        .drop_duplicates(weight_id_column)
        .rename(columns={weight_id_column: "review_id", "review_weight": "b1_weight"})
    )
    lookup["review_id"] = lookup["review_id"].astype("string")
    out = reviews.merge(lookup, on="review_id", how="left")
    out["review_weight"] = out["b1_weight"].fillna(out["review_weight"]).astype(float)
    return out.drop(columns="b1_weight")
