"""Small presentation helpers shared by the Explore and Compare views."""

from __future__ import annotations

import re
from urllib.parse import parse_qs, urlparse

from dashboard.data_access import Product


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
    """Match all search terms against title or ASIN while preserving catalog order."""
    terms = query.casefold().split()
    return [
        product
        for product in products
        if (category == "All categories" or product.category == category)
        and all(
            term in f"{product.title} {product.asin}".casefold()
            for term in terms
        )
    ]


def product_label(product: Product) -> str:
    title = product.title
    if len(title) > 82:
        title = title[:79].rstrip() + "..."
    return f"{title}  |  {product.asin}"
