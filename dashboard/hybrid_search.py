
"""Hybrid product search using BM25 and Sentence-BERT with RRF."""

from __future__ import annotations

from dashboard.data_access import Product
from dashboard.search_ranker import rank_products
from dashboard.semantic_search import SemanticProductSearch


def hybrid_rank_products(
    products: list[Product],
    query: str,
    semantic_index: SemanticProductSearch,
    top_k: int = 50,
    rrf_k: int = 60,
) -> list[Product]:
    """Fuse lexical and semantic rankings by product ASIN."""

    if not query.strip():
        return products

    # Preserve exact ASIN lookup.
    exact = [
        product
        for product in products
        if product.asin.casefold() == query.strip().casefold()
    ]
    if exact:
        return exact

    allowed_asins = {product.asin for product in products}

    lexical_results = rank_products(products, query)[:top_k]

    # The semantic index may cover the full catalog, so apply
    # the allowed-product filter to preserve category selection.
    semantic_results = semantic_index.search(
        query,
        top_k=len(semantic_index.products),
    )
    semantic_results = [
        product
        for product, similarity in semantic_results
        if product.asin in allowed_asins and similarity >= 0.25
    ][:top_k]

    scores: dict[str, float] = {}

    for rank, product in enumerate(lexical_results, start=1):
        scores[product.asin] = (
            scores.get(product.asin, 0.0)
            + 0.3 / (rrf_k + rank)
        )

    for rank, product in enumerate(semantic_results, start=1):
        scores[product.asin] = (
            scores.get(product.asin, 0.0)
            + 0.7 / (rrf_k + rank)
        )

    product_by_asin = {product.asin: product for product in products}

    return [
        product_by_asin[asin]
        for asin in sorted(
            scores,
            key=lambda asin: (-scores[asin], asin),
        )
    ]
