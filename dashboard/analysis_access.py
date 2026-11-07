
"""Read precomputed B1 reliability and B2 pros/cons results."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"

B1_PATH = PROCESSED_DIR / "product_rating_comparison.csv"
B2_PATH = PROCESSED_DIR / "product_pros_cons_cards.csv"


@dataclass(frozen=True)
class ReliabilityResult:
    asin: str
    review_count: int
    original_rating: float
    deduplicated_rating: float
    adjusted_rating: float
    rating_difference: float
    adjusted_review_count: int
    adjusted_review_percentage: float


@dataclass(frozen=True)
class ProsConsResult:
    asin: str
    n_text_reviews: int
    pros: list[dict[str, Any]]
    cons: list[dict[str, Any]]
    method_version: str


def _parse_aspects(value: Any) -> list[dict[str, Any]]:
    """Parse a JSON array safely, including missing values."""
    if not isinstance(value, str) or not value.strip():
        return []

    try:
        parsed = json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return []

    if not isinstance(parsed, list):
        return []

    return [item for item in parsed if isinstance(item, dict)]


def load_reliability_results() -> dict[str, ReliabilityResult]:
    """Load product-level B1 results indexed by ASIN."""
    if not B1_PATH.exists():
        return {}

    df = pd.read_csv(B1_PATH, dtype={"asin": str})

    results = {}

    for row in df.itertuples(index=False):
        results[row.asin] = ReliabilityResult(
            asin=row.asin,
            review_count=int(row.review_count),
            original_rating=float(row.original_rating),
            deduplicated_rating=float(row.deduplicated_rating),
            adjusted_rating=float(row.adjusted_rating),
            rating_difference=float(row.rating_difference),
            adjusted_review_count=int(row.adjusted_review_count),
            adjusted_review_percentage=float(
                row.adjusted_review_percentage
            ),
        )

    return results


def load_pros_cons_results() -> dict[str, ProsConsResult]:
    """Load product-level B2 results indexed by ASIN."""
    if not B2_PATH.exists():
        return {}

    df = pd.read_csv(B2_PATH, dtype={"asin": str})

    results = {}

    for row in df.itertuples(index=False):
        results[row.asin] = ProsConsResult(
            asin=row.asin,
            n_text_reviews=int(row.n_text_reviews),
            pros=_parse_aspects(row.pros),
            cons=_parse_aspects(row.cons),
            method_version=str(row.method_version),
        )

    return results
