
import pandas as pd

from nlp.similarity import compute_review_similarity


def test_long_duplicate_reviews():
    text = (
        "This product works extremely well and "
        "the overall quality is excellent for daily use."
    )

    df = pd.DataFrame({
        "source_row_number": [1, 2, 3],
        "asin": ["A001", "A001", "A001"],
        "body": [
            text,
            text,
            (
                "The product arrived damaged and stopped working "
                "after only a few days of regular use."
            ),
        ],
    })

    result = compute_review_similarity(df)

    assert result.loc[0, "max_text_similarity"] > 0.99
    assert result.loc[0, "similar_review_count"] >= 1
    assert result.loc[0, "most_similar_source_row_number"] == 2
    assert result.loc[0, "is_exact_duplicate"]
    assert result.loc[1, "is_exact_duplicate"]


def test_short_reviews_ignored():
    df = pd.DataFrame({
        "source_row_number": [1, 2],
        "asin": ["A001", "A001"],
        "body": ["Good", "Good"],
    })

    result = compute_review_similarity(df)

    assert result["similar_review_count"].sum() == 0
    assert not result["is_exact_duplicate"].any()


def test_different_products():
    text = (
        "Excellent product quality and works perfectly "
        "for all of my daily household needs."
    )

    df = pd.DataFrame({
        "source_row_number": [1, 2],
        "asin": ["A001", "A002"],
        "body": [text, text],
    })

    result = compute_review_similarity(df)

    assert result["similar_review_count"].sum() == 0
    assert not result["is_exact_duplicate"].any()


from nlp.reliability import compute_rule_anomaly_score


def test_rule_anomaly_score():
    df = pd.DataFrame({
        "text_length": [120, 150, 10, 200],
        "max_text_similarity": [0.95, 0.30, 1.0, 0.99],
        "is_exact_duplicate": [True, False, True, False],
    })

    result = compute_rule_anomaly_score(df)

    assert result.loc[0, "rule_anomaly_score"] == 1.0
    assert result.loc[1, "rule_anomaly_score"] == 0.0
    assert result.loc[2, "rule_anomaly_score"] == 0.0
    assert result.loc[3, "rule_anomaly_score"] == 0.6

    assert result["rule_anomaly_flag"].tolist() == [
        True, False, False, True
    ]

def test_source_duplicates_do_not_trigger_similarity():
    import pandas as pd

    from nlp.similarity import compute_review_similarity

    df = pd.DataFrame(
        {
            "source_row_number": [1, 2, 3],
            "source_row_hash": ["hash_a", "hash_a", "hash_b"],
            "asin": ["P1", "P1", "P1"],
            "body": [
                "This product works extremely well and I recommend it.",
                "This product works extremely well and I recommend it.",
                "The packaging arrived damaged and the item was unusable.",
            ],
        }
    )

    result = compute_review_similarity(df)

    assert len(result) == 3
    assert result["source_row_number"].is_unique
    assert not result["is_exact_duplicate"].any()
    assert result["similar_review_count"].eq(0).all()


def test_independent_source_records_with_same_text_are_detected():
    import pandas as pd

    from nlp.similarity import compute_review_similarity

    repeated_text = (
        "This product works extremely well and I recommend it "
        "to anyone looking for a reliable everyday solution."
    )

    df = pd.DataFrame(
        {
            "source_row_number": [1, 2, 3],
            "source_row_hash": ["hash_a", "hash_b", "hash_c"],
            "asin": ["P1", "P1", "P1"],
            "body": [
                repeated_text,
                repeated_text,
                "The packaging arrived damaged and the item was unusable.",
            ],
        }
    )

    result = compute_review_similarity(df)

    assert len(result) == 3
    assert result.loc[0, "is_exact_duplicate"]
    assert result.loc[1, "is_exact_duplicate"]
    assert not result.loc[2, "is_exact_duplicate"]
    assert result.loc[0, "similar_review_count"] >= 1
    assert result.loc[1, "similar_review_count"] >= 1


def test_source_duplicate_similarity_results_are_mapped_back():
    import pandas as pd

    from nlp.similarity import compute_review_similarity

    repeated_text = (
        "This product works extremely well and I recommend it "
        "to anyone looking for a reliable everyday solution."
    )

    df = pd.DataFrame(
        {
            "source_row_number": [1, 2, 3],
            "source_row_hash": ["hash_a", "hash_a", "hash_b"],
            "asin": ["P1", "P1", "P1"],
            "body": [
                repeated_text,
                repeated_text,
                repeated_text,
            ],
        }
    )

    result = compute_review_similarity(df)

    assert len(result) == 3
    assert result["is_exact_duplicate"].all()
    assert result["similar_review_count"].eq(1).all()
    assert result.loc[0, "max_text_similarity"] == result.loc[
        1, "max_text_similarity"
    ]

def test_source_duplicate_weights_sum_to_one():
    import pandas as pd
    import pytest

    from nlp.weighted_rating import compute_review_weights

    df = pd.DataFrame({
        "asin": ["P1"] * 6,
        "stars": [5, 5, 4, 4, 4, 3],
        "source_row_hash": ["A", "A", "B", "B", "B", "C"],
        "max_text_similarity": [0.0] * 6,
        "text_length": [100] * 6,
        "is_exact_duplicate": [False] * 6,
    })

    result = compute_review_weights(df)

    totals = result.groupby("source_row_hash")[
        "review_weight"
    ].sum()

    assert len(result) == 6
    assert totals["A"] == pytest.approx(1.0)
    assert totals["B"] == pytest.approx(1.0)
    assert totals["C"] == pytest.approx(1.0)


def test_text_and_source_weights_are_combined():
    import pandas as pd
    import pytest

    from nlp.weighted_rating import compute_review_weights

    df = pd.DataFrame({
        "asin": ["P1", "P1", "P1"],
        "stars": [5, 5, 4],
        "source_row_hash": ["A", "A", "B"],
        "max_text_similarity": [1.0, 1.0, 1.0],
        "text_length": [100, 100, 100],
        "is_exact_duplicate": [True, True, True],
    })

    result = compute_review_weights(df)

    # Two copies of source A share the text weight 0.6.
    assert result.loc[0, "review_weight"] == pytest.approx(0.3)
    assert result.loc[1, "review_weight"] == pytest.approx(0.3)

    # Independent source B receives its own text weight.
    assert result.loc[2, "review_weight"] == pytest.approx(0.6)

    assert result["review_weight"].sum() == pytest.approx(1.2)

def test_three_rating_levels():
    import pandas as pd
    import pytest

    from nlp.weighted_rating import (
        compute_product_ratings,
        compute_review_weights,
    )

    df = pd.DataFrame({
        "asin": ["P1", "P1", "P1"],
        "stars": [5, 5, 1],
        "source_row_hash": ["AAA", "AAA", "BBB"],
        "max_text_similarity": [0.0, 0.0, 1.0],
        "text_length": [100, 100, 100],
        "is_exact_duplicate": [False, False, True],
    })

    weighted = compute_review_weights(df)
    products = compute_product_ratings(weighted)

    assert len(products) == 1

    row = products.iloc[0]

    assert row["original_rating"] == pytest.approx(11 / 3)
    assert row["deduplicated_rating"] == pytest.approx(3.0)
    assert row["adjusted_rating"] == pytest.approx(3.5)

    assert row["rating_difference"] == pytest.approx(-1 / 6)

    assert row["rating_difference"] == pytest.approx(
        row["deduplication_difference"]
        + row["text_adjustment_difference"]
    )