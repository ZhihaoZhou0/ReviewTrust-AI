
"""Compare BM25, SBERT and Hybrid product search rankings."""

from dashboard.data_access import load_catalog
from dashboard.search_ranker import rank_products
from dashboard.semantic_search import SemanticProductSearch
from dashboard.hybrid_search import hybrid_rank_products


TEST_CASES = [
    {
        "query": "lamp",
        "expected_asin": "B00N31CQ5A",
    },
    {
        "query": "headphones",
        "expected_asin": "B01KB9K9Z0",
    },
    {
        "query": "something to keep my drinks cold",
        "expected_asin": "B0BNYR7MQV",
    },
]


def evaluate(results, expected_asin):
    """Return hit@5 and reciprocal rank for one labeled product."""
    ranked_asins = [product.asin for product in results]

    if expected_asin not in ranked_asins:
        return 0, 0.0, None

    rank = ranked_asins.index(expected_asin) + 1

    return int(rank <= 5), 1.0 / rank, rank


def main():
    products = load_catalog()
    semantic_index = SemanticProductSearch(products)

    totals = {
        "BM25": [0, 0.0],
        "SBERT": [0, 0.0],
        "Hybrid": [0, 0.0],
    }

    for case in TEST_CASES:
        query = case["query"]
        expected = case["expected_asin"]

        results = {
            "BM25": rank_products(products, query),
            "SBERT": [
                product
                for product, _ in semantic_index.search(
                    query, top_k=len(products)
                )
            ],
            "Hybrid": hybrid_rank_products(
                products, query, semantic_index
            ),
        }

        print(f"\nQuery: {query}")
        print(f"Expected ASIN: {expected}")

        for method, ranked in results.items():
            hit, rr, rank = evaluate(ranked, expected)

            totals[method][0] += hit
            totals[method][1] += rr

            print(
                f"  {method:8s} "
                f"rank={str(rank):>5s} "
                f"hit@5={hit} "
                f"RR={rr:.3f}"
            )

    n = len(TEST_CASES)

    print("\n=== Evaluation Summary ===")

    for method, (hits, rr_sum) in totals.items():
        print(
            f"{method:8s} "
            f"Hit@5={hits / n:.3f} "
            f"MRR={rr_sum / n:.3f}"
        )


if __name__ == "__main__":
    main()
