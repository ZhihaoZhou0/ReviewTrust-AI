
"""Regression tests for product search relevance."""
from dashboard.hybrid_search import hybrid_rank_products
from dashboard.data_access import Product
from dashboard.search_ranker import rank_products
from dashboard.view_model import filter_products


def make_product(
    asin: str,
    title: str,
    category: str,
    category_path: str,
) -> Product:
    return Product(
        asin=asin,
        title=title,
        category=category,
        category_path=category_path,
        source_rating=4.5,
        source_rating_count=100,
        image_url=None,
    )


def sample_products() -> list[Product]:
    return [
        make_product(
            "B000000001",
            "Nail Gel Polish for UV Lamp",
            "Beauty & Personal Care",
            "Beauty & Personal Care -> Nail Art -> Gel Polish",
        ),
        make_product(
            "B000000002",
            "Stained Glass Table Lamp",
            "Tools & Home Improvement",
            "Tools & Home Improvement -> Lighting -> Table Lamps",
        ),
        make_product(
            "B000000003",
            "Wireless Gaming Headset",
            "Electronics",
            "Electronics -> Audio -> Headphones",
        ),
        make_product(
            "B000000004",
            "Lightweight Travel Pillow",
            "Home & Kitchen",
            "Home & Kitchen -> Bedding -> Pillows",
        ),
    ]


def test_lamp_prefers_lighting_product():
    results = rank_products(sample_products(), "lamp")

    assert results
    assert results[0].asin == "B000000002"


def test_light_does_not_match_lightweight():
    results = rank_products(sample_products(), "light")

    assert "B000000004" not in [p.asin for p in results]


def test_headphones_matches_category():
    results = rank_products(sample_products(), "headphones")

    assert results
    assert results[0].asin == "B000000003"


def test_exact_asin():
    results = rank_products(sample_products(), "B000000002")

    assert len(results) == 1
    assert results[0].asin == "B000000002"


def test_category_filter():
    results = filter_products(
        sample_products(),
        "lamp",
        "Beauty & Personal Care",
    )

    assert all(p.category == "Beauty & Personal Care" for p in results)


def test_empty_search_preserves_order():
    products = sample_products()

    assert rank_products(products, "") == products


class FakeSemanticIndex:
    """A lightweight semantic index for testing without SBERT."""

    def __init__(self, products):
        self.products = products
        self.calls = 0

    def search(self, query, top_k=20):
        self.calls += 1
        return [
            (product, 0.8)
            for product in self.products[:top_k]
        ]


def test_hybrid_exact_asin():
    products = sample_products()
    index = FakeSemanticIndex(products)

    results = hybrid_rank_products(
        products, "B000000002", index
    )

    assert [p.asin for p in results] == ["B000000002"]
    assert index.calls == 0


def test_hybrid_category_filter():
    products = sample_products()
    index = FakeSemanticIndex(products)

    selected = [
        p for p in products
        if p.category == "Beauty & Personal Care"
    ]

    results = hybrid_rank_products(
        selected, "nail polish for home use", index
    )

    assert results
    assert all(
        p.category == "Beauty & Personal Care"
        for p in results
    )


def test_hybrid_no_duplicates():
    products = sample_products()
    index = FakeSemanticIndex(products)

    results = hybrid_rank_products(
        products, "table lamp for my room", index
    )

    asins = [p.asin for p in results]

    assert len(asins) == len(set(asins))


def test_hybrid_empty_query():
    products = sample_products()
    index = FakeSemanticIndex(products)

    results = hybrid_rank_products(products, "", index)

    assert results == products
    assert index.calls == 0
