import pandas as pd

from prepare_nlp_data import prepare_nlp_data


def test_prepare_preserves_duplicates_and_literal_na(tmp_path):
    source = tmp_path / "reviews_clean.csv"
    output = tmp_path / "reviews_b1_nlp.csv"

    df = pd.DataFrame(
        {
            "source_row_number": [1, 2, 3, 4, 5],
            "source_review_id": ["r1", "r1", "r2", "r3", "r4"],
            "asin": ["A", "A", "A", "B", "B"],
            "body": [
                "Excellent product",
                "Excellent product",
                "NA",
                "",
                "Excellent product",
            ],
            "stars": [5, 5, 3, 4, 5],
            "user_id": ["u1", "u1", "u2", "u3", "u4"],
            "review_date": ["2025-01-01"] * 5,
            "verified_purchase": ["true"] * 5,
            "found_helpful": [0] * 5,
        }
    )

    df.to_csv(source, index=False)

    result = prepare_nlp_data(source, output)

    assert len(result) == 5
    assert result["source_row_number"].is_unique
    assert result["source_review_id"].duplicated().any()

    # Literal "NA" must remain review text.
    assert result.loc[2, "body"] == "NA"
    assert bool(result.loc[2, "has_text"])

    # Truly empty body remains excluded from text analysis.
    assert not bool(result.loc[3, "has_text"])
    assert result.loc[3, "text_length"] == 0

    # Same product and same text are flagged, not removed.
    assert bool(result.loc[0, "same_product_exact_text"])
    assert bool(result.loc[1, "same_product_exact_text"])

    # Identical text on another product is not a same-product match.
    assert not bool(result.loc[4, "same_product_exact_text"])

    assert output.exists()
