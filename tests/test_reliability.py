
import pandas as pd

from nlp.similarity import compute_review_similarity


def test_long_duplicate_reviews():
    text = (
        "This product works extremely well and "
        "the overall quality is excellent for daily use."
    )

    df = pd.DataFrame({
        "id": ["r1", "r2", "r3"],
        "asin": ["A001", "A001", "A001"],
        "body": [
            text,
            text,
            "The product arrived damaged and stopped working "
            "after only a few days of regular use.",
        ],
    })

    result = compute_review_similarity(df)

    assert result.loc[0, "max_text_similarity"] > 0.99
    assert result.loc[0, "similar_review_count"] >= 1
    assert result.loc[0, "most_similar_review_id"] == "r2"
    assert result.loc[0, "is_exact_duplicate"]
    assert result.loc[1, "is_exact_duplicate"]


def test_short_reviews_ignored():
    df = pd.DataFrame({
        "id": ["r1", "r2"],
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
        "id": ["r1", "r2"],
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
