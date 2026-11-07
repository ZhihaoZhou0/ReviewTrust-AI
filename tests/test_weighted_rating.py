
"""Tests for experimental weighted product ratings."""

import pandas as pd
import pytest

from nlp.weighted_rating import (
    compute_review_weights,
    compute_product_ratings,
)


def make_reviews():
    return pd.DataFrame(
        {
            "asin": ["A", "A", "A", "B"],
            "stars": [5, 5, 1, 3],
            "max_text_similarity": [0.9, 0.2, 0.1, 0.0],
            "text_length": [100, 100, 100, 100],
            "is_exact_duplicate": [False, False, False, False],
            "ml_anomaly_flag": [False, True, False, False],
        }
    )


def test_default_weights():
    df = make_reviews()
    result = compute_review_weights(df)

    assert result["review_weight"].tolist() == [
        0.8, 1.0, 1.0, 1.0
    ]


def test_exact_duplicate_weight():
    df = make_reviews()
    df.loc[0, "is_exact_duplicate"] = True

    result = compute_review_weights(df)

    assert result.loc[0, "review_weight"] == pytest.approx(0.6)
    assert result.loc[0, "weight_reason"] == "exact_text_duplicate"


def test_ml_anomaly_does_not_change_weight():
    df = make_reviews()

    result = compute_review_weights(df)

    # Row 1 is ML-flagged but has no duplication evidence.
    assert result.loc[1, "review_weight"] == 1.0


def test_weighted_product_rating():
    df = make_reviews()
    weighted = compute_review_weights(df)
    products = compute_product_ratings(weighted)

    product_a = products.set_index("asin").loc["A"]

    expected_original = (5 + 5 + 1) / 3
    expected_adjusted = (5 * 0.8 + 5 + 1) / (0.8 + 1 + 1)

    assert product_a["original_rating"] == pytest.approx(
        expected_original
    )

    assert product_a["adjusted_rating"] == pytest.approx(
        expected_adjusted
    )

    assert product_a["adjusted_review_count"] == 1


def test_no_adjustment_keeps_rating():
    df = make_reviews()
    df["max_text_similarity"] = 0.0

    weighted = compute_review_weights(df)
    products = compute_product_ratings(weighted)

    assert (
        products["rating_difference"].abs() < 1e-10
    ).all()


def test_invalid_ratings_are_excluded():
    df = make_reviews()
    df.loc[2, "stars"] = 8

    weighted = compute_review_weights(df)
    products = compute_product_ratings(weighted)

    product_a = products.set_index("asin").loc["A"]

    assert product_a["review_count"] == 2
