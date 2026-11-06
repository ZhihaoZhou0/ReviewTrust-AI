"""Small presentation helpers shared by the Explore and Compare views."""

from __future__ import annotations

from dashboard.data_access import Product


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
