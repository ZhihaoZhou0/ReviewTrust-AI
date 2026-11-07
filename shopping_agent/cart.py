
"""Multi-product shopping cart for ReviewTrust AI.

Build a comparison cart using products from the
existing Amazon Reviews dataset.
"""

from shopping_agent.amazon_links import extract_asin
from shopping_agent.repository import get_product_bundle


def build_cart(
    links: list[str],
    per_group: int = 4,
) -> dict:
    """Build a cart from up to five Amazon product links.

    Features:
    - Extract ASINs from Amazon URLs.
    - Prevent duplicate products.
    - Retrieve product information and review evidence.
    - Report invalid or unavailable products.
    """

    if not 1 <= len(links) <= 5:
        raise ValueError(
            "The shopping cart accepts between 1 and 5 links."
        )

    products = []
    errors = []
    seen_asins = set()

    for link in links:
        # Step 1: Extract and validate the ASIN.
        try:
            asin = extract_asin(link)
        except ValueError as error:
            errors.append({
                "input": link,
                "reason": str(error),
            })
            continue

        # Step 2: Avoid adding the same product twice.
        if asin in seen_asins:
            continue

        seen_asins.add(asin)

        # Step 3: Retrieve product data and real reviews.
        try:
            bundle = get_product_bundle(link, per_group=per_group)
        except Exception as error:
            errors.append({
                "input": link,
                "asin": asin,
                "reason": f"Product data is temporarily unavailable: {error}",
            })
            continue

        # Step 4: Handle products outside our dataset.
        if bundle is None:
            errors.append({
                "input": link,
                "asin": asin,
                "reason": "Product not found in dataset.",
            })
            continue

        products.append(bundle)

    return {
        "products": products,
        "product_count": len(products),
        "errors": errors,
    }
