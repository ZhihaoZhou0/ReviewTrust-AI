"""Tests for B2 Pros & Cons extraction."""

import json

import pandas as pd
import pytest

from nlp.pros_cons import (
    build_product_cards,
    extract_aspect_mentions,
    prepare_reviews,
    summarize_pros_cons,
)
from nlp.pros_cons.aspects import AspectMatcher
from nlp.pros_cons.schema import attach_review_weights
from nlp.pros_cons.text import split_clauses, split_sentences, tokenize


def make_b1_reviews():
    """Reviews in the B1 NLP-view format after PR #3 (reviews_b1_nlp.csv)."""
    return pd.DataFrame({
        "source_row_number": [1, 2, 3, 4, 5, 6],
        "source_row_hash": ["h1", "h2", "h3", "h4", "h5", "h6"],
        "source_review_id": ["R1", "R2", "R3", "R4", "R5", "R6"],
        "asin": ["A001"] * 5 + ["B001"],
        "body": [
            "Keeps my water cold all day, but the lid leaks.",
            "The lid leaks every time I put it in my bag.",
            "Love it. Keeps drinks cold for hours. Easy to clean.",
            "Leaked all over my desk. Returned it.",
            "",  # empty text: kept for ratings elsewhere, ignored by B2
            "Great price for a pack of twelve.",
        ],
        "stars": [4, 2, 5, 1, 5, 5],
        "found_helpful": [3, 0, 1, 5, 0, 0],
    })


# --- schema -----------------------------------------------------------------

def test_prepare_reviews_maps_b1_columns_and_drops_empty_text():
    reviews = prepare_reviews(make_b1_reviews())
    assert list(reviews.columns) == [
        "review_id", "record_key", "asin", "text", "stars", "review_weight", "found_helpful"
    ]
    assert len(reviews) == 5
    assert (reviews["review_weight"] == 1.0).all()


def test_prepare_reviews_uses_source_row_number_and_hash():
    reviews = prepare_reviews(make_b1_reviews())
    assert reviews["review_id"].iloc[0] == "1"
    assert reviews["record_key"].iloc[0] == "h1"


def test_prepare_reviews_supports_legacy_id_column():
    df = make_b1_reviews().drop(columns=["source_row_number", "source_row_hash"])
    df = df.rename(columns={"source_review_id": "id"})
    reviews = prepare_reviews(df)
    assert reviews["review_id"].iloc[0] == "R1"
    assert (reviews["record_key"] == reviews["review_id"]).all()


def test_prepare_reviews_rejects_non_unique_key():
    df = make_b1_reviews()
    df.loc[1, "source_row_number"] = 1
    with pytest.raises(ValueError, match="not unique"):
        prepare_reviews(df)


def test_exact_source_repeats_are_kept_but_counted_once():
    df = make_b1_reviews()
    repeat = df.iloc[[1]].copy()          # same source_row_hash, new row number
    repeat["source_row_number"] = 99
    df = pd.concat([df, repeat, repeat.assign(source_row_number=100)], ignore_index=True)

    reviews = prepare_reviews(df)
    assert len(reviews) == 7               # every row retained (A1 contract)

    summary = summarize_pros_cons(extract_aspect_mentions(reviews), reviews, min_reviews=1, min_share=0)
    leaks = summary[(summary["asin"] == "A001") & (summary["aspect"] == "leaks")].iloc[0]
    assert leaks["review_count"] == 3      # not 5
    assert leaks["n_text_reviews"] == 4


def test_attach_weights_prefers_b1_text_weight():
    reviews = prepare_reviews(make_b1_reviews())
    weights = pd.DataFrame({
        "source_row_number": [2, 3],
        "text_weight": [0.8, 1.0],
        "review_weight": [0.4, 1.0],      # includes 1 / source repeats
    })
    out = attach_review_weights(reviews, weights).set_index("review_id")
    assert out.loc["2", "review_weight"] == pytest.approx(0.8)
    assert out.loc["1", "review_weight"] == 1.0


def test_attach_weights_falls_back_to_review_weight():
    reviews = prepare_reviews(make_b1_reviews())
    weights = pd.DataFrame({"source_row_number": [2], "review_weight": [0.6]})
    out = attach_review_weights(reviews, weights).set_index("review_id")
    assert out.loc["2", "review_weight"] == pytest.approx(0.6)


# --- text and matching ------------------------------------------------------

def test_contrast_splits_clauses():
    assert split_clauses("Keeps water cold, but the lid leaks") == [
        "Keeps water cold", "the lid leaks"
    ]


def test_sentence_split_handles_html_breaks():
    assert split_sentences("Great bottle.<br>Leaks a bit!") == ["Great bottle.", "Leaks a bit!"]


def test_longest_phrase_wins():
    hits = AspectMatcher().find(tokenize("so easy to clean"))
    assert [h.aspect for h in hits] == ["cleaning"]


def test_term_assigned_to_two_aspects_is_rejected():
    lexicon = {
        "a": {"label": "A", "terms": {"lid": 0}},
        "b": {"label": "B", "terms": {"lid": 0}},
    }
    with pytest.raises(ValueError):
        AspectMatcher(lexicon)


# --- extraction -------------------------------------------------------------

def one_review(text, stars=3):
    return prepare_reviews(pd.DataFrame({
        "source_row_number": [1], "asin": ["A"], "body": [text], "stars": [stars]
    }))


def _labels(text):
    reviews = one_review(text)
    m = extract_aspect_mentions(reviews)
    return set(zip(m["aspect"], m["polarity"]))


def test_contrast_gives_pro_and_con():
    assert _labels("Keeps my coffee hot for hours, but the lid leaks.") == {
        ("temperature", "pro"), ("leaks", "con")
    }


def test_negation_flips_polarity():
    assert _labels("It does not leak at all.") == {("leaks", "pro")}
    assert _labels("Not comfortable at all.") == {("comfort", "con")}


def test_neutral_clause_is_not_a_mention():
    assert _labels("I checked the size chart before ordering.") == set()


def test_polarity_ignores_star_rating():
    text = "The lid leaks."
    for stars in (1, 5):
        reviews = one_review(text, stars)
        assert extract_aspect_mentions(reviews)["polarity"].tolist() == ["con"]


# --- aggregation ------------------------------------------------------------

def test_summary_counts_distinct_reviews_and_ranks():
    reviews = prepare_reviews(make_b1_reviews())
    mentions = extract_aspect_mentions(reviews)
    summary = summarize_pros_cons(mentions, reviews, min_reviews=1, min_share=0)

    a = summary[summary["asin"] == "A001"].set_index(["polarity", "aspect"])
    assert a.loc[("con", "leaks"), "review_count"] == 3
    assert a.loc[("con", "leaks"), "rank"] == 1
    assert a.loc[("pro", "temperature"), "review_count"] == 2
    assert a.loc[("con", "leaks"), "n_text_reviews"] == 4
    assert a.loc[("con", "leaks"), "mention_share"] == pytest.approx(0.75)


def test_summary_evidence_comes_from_source_reviews():
    reviews = prepare_reviews(make_b1_reviews())
    summary = summarize_pros_cons(extract_aspect_mentions(reviews), reviews, min_reviews=1, min_share=0)
    texts = dict(zip(reviews["review_id"], reviews["text"]))
    for evidence in summary["evidence"]:
        for item in json.loads(evidence):
            assert item["text"] in texts[item["review_id"]]


def test_evidence_snippets_are_distinct():
    df = pd.DataFrame({
        "source_row_number": [1, 2, 3],
        "asin": ["A"] * 3,
        "body": ["The lid leaks.", "The lid leaks!", "Leaked all over my bag."],
        "stars": [1, 2, 2],
    })
    reviews = prepare_reviews(df)
    summary = summarize_pros_cons(extract_aspect_mentions(reviews), reviews, min_reviews=1, min_share=0)
    evidence = json.loads(summary.iloc[0]["evidence"])
    assert summary.iloc[0]["review_count"] == 3
    assert len(evidence) == 2


def test_min_reviews_filters_rare_aspects():
    reviews = prepare_reviews(make_b1_reviews())
    summary = summarize_pros_cons(extract_aspect_mentions(reviews), reviews, min_reviews=3, min_share=0)
    assert set(summary["aspect"]) == {"leaks"}


def test_review_weights_change_ranking_not_counts():
    reviews = prepare_reviews(make_b1_reviews())
    # Down-weight two of the three "leaks" reviews.
    reviews.loc[reviews["review_id"].isin(["2", "4"]), "review_weight"] = 0.1
    mentions = extract_aspect_mentions(reviews)
    summary = summarize_pros_cons(mentions, reviews, min_reviews=1, min_share=0)
    leaks = summary[(summary["asin"] == "A001") & (summary["aspect"] == "leaks")].iloc[0]
    assert leaks["review_count"] == 3
    assert leaks["weighted_review_count"] == pytest.approx(1.2)


def test_product_cards_include_products_without_output():
    reviews = prepare_reviews(make_b1_reviews())
    summary = summarize_pros_cons(extract_aspect_mentions(reviews), reviews, min_reviews=3, min_share=0)
    cards = build_product_cards(summary, reviews).set_index("asin")
    assert json.loads(cards.loc["B001", "pros"]) == []
    assert json.loads(cards.loc["A001", "cons"])[0]["aspect"] == "leaks"


# --- fixes from the first human review (product_review_sheet) --------------

def test_pretty_as_intensifier_is_not_appearance():
    assert _labels("Came in the mail pretty fast and I was pretty happy.") == set()
    assert ("appearance", "pro") in _labels("Have no problems using it, and it's also pretty.")


def test_pretty_bad_is_negative():
    assert _labels("The battery life is pretty bad.") == {("battery", "con")}


def test_solid_as_modifier_is_not_quality():
    assert ("quality", "pro") not in _labels("Just a solid color so you can reorder.")
    assert _labels("It feels very solid.") == {("quality", "pro")}


def test_cost_effective_is_value():
    assert _labels("A really cost effective package.") == {("value", "pro")}


def test_negated_cue_flips_temperature():
    assert _labels("It doesn't keep food cold until lunch.") == {("temperature", "con")}


def test_concessive_sentence_is_split():
    clauses = split_clauses("While it doesn't keep food cold, I just store it in the fridge")
    assert clauses == ["it doesn't keep food cold", "I just store it in the fridge"]


def test_leading_however_is_dropped():
    assert split_clauses("However, once inflated they were easy to shape") == [
        "once inflated they were easy to shape"
    ]
