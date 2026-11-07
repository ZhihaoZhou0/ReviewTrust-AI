"""Tests for B2 NLP evaluation."""

from pathlib import Path

import pandas as pd
import pytest

from analytics.pros_cons_evaluation import (
    carry_over_judgements,
    build_annotation_sample,
    build_product_review_sheet,
    evaluate_against_gold,
    evidence_faithfulness,
    parse_gold_labels,
    score_product_review_sheet,
    star_consistency,
    subsample_stability,
)
from nlp.pros_cons import extract_aspect_mentions, prepare_reviews, summarize_pros_cons


SEED_GOLD = Path(__file__).parent / "fixtures" / "pros_cons_seed_gold.csv"


def make_reviews(n_products=3, per_product=12):
    """Small synthetic corpus with a clear pro and a clear con per product."""
    rows = []
    for p in range(n_products):
        for i in range(per_product):
            if i % 3 == 0:
                body, stars = "The lid leaks every single day.", 2
            elif i % 3 == 1:
                body, stars = "Keeps my water cold for hours. Great price.", 5
            else:
                body, stars = "Keeps drinks cold all day, but the lid leaks.", 4
            rows.append({
                "source_row_number": p * 1000 + i + 1,
                "source_row_hash": f"h{p}-{i}",
                "asin": f"A{p:03d}",
                "body": body,
                "stars": stars,
            })
    return prepare_reviews(pd.DataFrame(rows))


def test_parse_gold_labels():
    assert parse_gold_labels("leaks:con; cleaning:pro") == {("leaks", "con"), ("cleaning", "pro")}
    assert parse_gold_labels("") == set()
    with pytest.raises(ValueError):
        parse_gold_labels("leaks:bad")


def test_perfect_predictions_score_one():
    gold = pd.DataFrame({
        "item_id": ["a", "b"],
        "text": ["The lid leaks.", "I bought this yesterday."],
        "gold_labels": ["leaks:con", ""],
    })
    result = evaluate_against_gold(gold)
    assert result["aspect_polarity"]["f1"] == pytest.approx(1.0)
    assert result["errors"].empty


def test_wrong_polarity_counts_as_error_but_detection_hit():
    gold = pd.DataFrame({"item_id": ["a"], "text": ["The lid leaks."], "gold_labels": ["leaks:pro"]})
    result = evaluate_against_gold(gold)
    assert result["aspect_detection"]["f1"] == pytest.approx(1.0)
    assert result["aspect_polarity"]["tp"] == 0
    assert result["polarity_accuracy"] == 0.0


def test_seed_gold_regression():
    """Guards against regressions; the seed set is hand-written, so the
    numbers are optimistic. Real quality is measured on labeled real reviews."""
    gold = pd.read_csv(SEED_GOLD, keep_default_na=False)
    result = evaluate_against_gold(gold)
    assert len(gold) == 50
    assert result["aspect_polarity"]["f1"] >= 0.80
    assert result["polarity_accuracy"] >= 0.90


def test_star_consistency_on_synthetic_data():
    reviews = make_reviews()
    result = star_consistency(extract_aspect_mentions(reviews))
    shares = result["con_share_by_stars"]
    assert shares[2] > shares[5]
    assert result["spearman_net_vs_stars"] > 0
    assert 0 < result["cons_from_4_5_stars"] < 1   # cons hidden in 4-star reviews


def test_evidence_faithfulness_is_one():
    reviews = make_reviews()
    summary = summarize_pros_cons(extract_aspect_mentions(reviews), reviews)
    assert evidence_faithfulness(summary, reviews) == pytest.approx(1.0)


def test_stability_is_high_for_consistent_products():
    reviews = make_reviews()
    result = subsample_stability(extract_aspect_mentions(reviews), reviews, n_rounds=3)
    assert result["mean_jaccard"] >= 0.9


def test_annotation_sample_is_stratified_and_blank():
    reviews = make_reviews()
    sample = build_annotation_sample(reviews, n_per_star=2)
    assert sample.groupby("stars").size().max() <= 2
    assert (sample["gold_labels"] == "").all()
    assert "predicted" not in " ".join(sample.columns)


def test_product_review_sheet_round_trip():
    reviews = make_reviews()
    summary = summarize_pros_cons(extract_aspect_mentions(reviews), reviews)
    sheet = build_product_review_sheet(summary, n_products=2)
    sheet["judgement"] = ["yes", "partial"] + ["no"] * (len(sheet) - 2)
    score = score_product_review_sheet(sheet)
    assert score["judged_items"] == len(sheet)
    assert 0 < score["precision"] < 1


def test_evidence_faithfulness_handles_curly_quotes():
    df = pd.DataFrame({
        "source_row_number": [1, 2, 3],
        "asin": ["A"] * 3,
        "body": [
            "The lid doesn\u2019t seal and it leaks.",
            "It leaks when it\u2019s in my bag.",
            "Leaks everywhere.<br>Very disappointed.",
        ],
        "stars": [1, 2, 1],
    })
    reviews = prepare_reviews(df)
    summary = summarize_pros_cons(extract_aspect_mentions(reviews), reviews, min_reviews=1, min_share=0)
    assert evidence_faithfulness(summary, reviews) == pytest.approx(1.0)


def test_carry_over_keeps_unchanged_judgements_only():
    reviews = make_reviews()
    summary = summarize_pros_cons(extract_aspect_mentions(reviews), reviews)
    old = build_product_review_sheet(summary, n_products=2)
    old["judgement"] = "yes"
    old.loc[0, "evidence_text"] = "an older evidence text"   # this item changed

    new = build_product_review_sheet(summary, asins=list(old["asin"].unique()))
    merged = carry_over_judgements(new, old)
    assert len(merged) == len(new)
    assert (merged["judgement"] == "").sum() == 1
    assert set(merged["judgement"]) == {"yes", ""}
