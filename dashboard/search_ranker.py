
"""BM25-based product relevance ranking."""

from __future__ import annotations

import math
import re
from collections import Counter

from dashboard.data_access import Product


def tokenize(text: str) -> list[str]:
    """Normalize text into searchable words."""
    words = re.findall(r"[a-z0-9]+", text.casefold())

    # Minimal plural normalization, not a synonym dictionary.
    normalized = []
    for word in words:
        if len(word) > 4 and word.endswith("ies"):
            word = word[:-3] + "y"
        elif len(word) > 3 and word.endswith("s") and not word.endswith("ss"):
            word = word[:-1]
        normalized.append(word)

    return normalized


def bm25_scores(
    documents: list[list[str]],
    query_tokens: list[str],
) -> list[float]:
    """Compute BM25 scores for a collection of tokenized documents."""
    if not documents:
        return []

    n_docs = len(documents)
    avg_length = sum(map(len, documents)) / n_docs
    avg_length = max(avg_length, 1)

    document_frequency = Counter()
    for document in documents:
        document_frequency.update(set(document))

    scores = []

    for document in documents:
        frequencies = Counter(document)
        length = len(document)
        score = 0.0

        for term in set(query_tokens):
            tf = frequencies.get(term, 0)
            if tf == 0:
                continue

            df = document_frequency[term]
            idf = math.log(
                1 + (n_docs - df + 0.5) / (df + 0.5)
            )

            k1 = 1.5
            b = 0.75
            denominator = (
                tf + k1 * (1 - b + b * length / avg_length)
            )

            score += idf * (tf * (k1 + 1)) / denominator

        scores.append(score)

    return scores


def rank_products(
    products: list[Product],
    query: str,
) -> list[Product]:
    """Rank products by title and category relevance."""
    query = query.strip()

    if not query:
        return products

    # Preserve exact ASIN lookup.
    asin_matches = [
        product
        for product in products
        if product.asin.casefold() == query.casefold()
    ]
    if asin_matches:
        return asin_matches

    query_tokens = tokenize(query)
    if not query_tokens:
        return []

    titles = [tokenize(product.title) for product in products]

    categories = [
        tokenize(product.category_path or product.category)
        for product in products
    ]

    title_scores = bm25_scores(titles, query_tokens)
    category_scores = bm25_scores(categories, query_tokens)

    ranked = []

    for index, product in enumerate(products):
        # Category is important for identifying product type.
        score = (
            2.0 * title_scores[index]
            + 3.0 * category_scores[index]
        )

        if score > 0:
            ranked.append((score, index, product))

    ranked.sort(key=lambda item: (-item[0], item[1]))

    return [product for _, _, product in ranked]
