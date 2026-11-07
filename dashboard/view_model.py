
"""Small presentation helpers shared by the Explore and Compare views."""

from __future__ import annotations

import re
from urllib.parse import parse_qs, urlparse

from dashboard.data_access import Product
from dashboard.search_ranker import rank_products


ASIN_PATTERN = re.compile(r"^[A-Z0-9]{10}$")



def amazon_asin(link: str) -> str | None:
    """Extract a product ASIN from an Amazon URL without following redirects."""
    value = link.strip()
    if not value:
        return None
    parsed = urlparse(value)
    host = (parsed.hostname or "").lower()
    if not re.fullmatch(r"(?:[a-z0-9-]+\.)*amazon\.(?:com|co\.uk|ca|de|fr|it|es|in|co\.jp|com\.au|com\.br)", host):
        return None
    segments = [segment.upper() for segment in parsed.path.split("/") if segment]
    for marker in ("DP", "PRODUCT", "PRODUCT-REVIEWS"):
        if marker in segments:
            index = segments.index(marker) + 1
            if index < len(segments) and ASIN_PATTERN.fullmatch(segments[index]):
                return segments[index]
    if "AW" in segments:
        index = segments.index("AW") + 1
        if index + 1 < len(segments) and segments[index] == "D" and ASIN_PATTERN.fullmatch(segments[index + 1]):
            return segments[index + 1]
    for candidate in parse_qs(parsed.query).get("asin", []):
        if ASIN_PATTERN.fullmatch(candidate.upper()):
            return candidate.upper()
    return None


def filter_products(
    products: list[Product], query: str, category: str
) -> list[Product]:
    """Filter products by category and rank using BM25."""

    # Preserve existing category filtering.
    if category == "All categories":
        filtered = products
    else:
        filtered = [
            product
            for product in products
            if product.category == category
        ]

    # Use BM25 for product relevance ranking.
    return rank_products(filtered, query)


def product_label(product: Product) -> str:
    title = product.title
    if len(title) > 82:
        title = title[:79].rstrip() + "..."
    return f"{title}  |  {product.asin}"
