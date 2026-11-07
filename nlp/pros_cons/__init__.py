"""B2: aspect-based Pros & Cons extraction for product reviews.

Typical use:

    from nlp.pros_cons import prepare_reviews, extract_aspect_mentions, summarize_pros_cons

    reviews = prepare_reviews(raw_df)              # normalize B1 / A1 column names
    mentions = extract_aspect_mentions(reviews)    # one row per clause x aspect
    summary = summarize_pros_cons(mentions, reviews)  # ranked pros / cons per product

The extractor never looks at the star rating when deciding polarity, so star
ratings remain an independent signal for evaluation.
"""

from nlp.pros_cons.schema import METHOD_VERSION, prepare_reviews
from nlp.pros_cons.extract import (
    extract_aspect_mentions,
    summarize_pros_cons,
    build_product_cards,
)

__all__ = [
    "METHOD_VERSION",
    "prepare_reviews",
    "extract_aspect_mentions",
    "summarize_pros_cons",
    "build_product_cards",
]
