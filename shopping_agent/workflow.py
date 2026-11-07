"""End-to-end personalized shopping workflow for one to five products."""

from __future__ import annotations

import argparse
import json
from collections.abc import Callable
from typing import Any

from shopping_agent.cart import build_cart
from shopping_agent.eligibility import evaluate_cart
from shopping_agent.preferences import preferences_with_fallback
from shopping_agent.recommendation import rank_products


def run_workflow(
    links: list[str],
    user_request: str,
    *,
    cart_builder: Callable[..., dict] = build_cart,
    preference_extractor: Callable[[str], Any] = preferences_with_fallback,
    ranker: Callable[..., tuple[list[dict], list[str]]] = rank_products,
) -> dict:
    """Resolve products, enforce constraints, and rank review evidence."""
    cleaned_links = [link.strip() for link in links if link.strip()]
    if not 1 <= len(cleaned_links) <= 5:
        return {
            "status": "invalid_input",
            "message": "Provide between one and five Amazon product links.",
            "cart_errors": [],
        }
    if not user_request.strip():
        return {
            "status": "invalid_input",
            "message": "Describe what you need before comparing products.",
            "cart_errors": [],
        }

    try:
        cart = cart_builder(cleaned_links)
    except Exception as error:
        return {
            "status": "data_unavailable",
            "message": "Product data is temporarily unavailable.",
            "cart_errors": [{"reason": str(error)}],
        }
    if not cart.get("products"):
        return {
            "status": "no_products",
            "cart_errors": cart.get("errors", []),
            "message": "None of these products are available in the historical review dataset.",
        }

    model_warning = None
    try:
        extracted = preference_extractor(user_request)
        if isinstance(extracted, tuple):
            preferences, model_warning = extracted
        else:
            preferences = extracted
    except Exception as error:
        return {
            "status": "preference_error",
            "message": "The shopping requirements could not be interpreted safely.",
            "cart_errors": cart.get("errors", []),
            "model_warning": str(error),
        }

    eligibility = evaluate_cart(cart, preferences)
    ranked, warnings = ranker(cart, eligibility, preferences)
    eligible_asins = {item["asin"] for item in eligibility if item["status"] == "eligible"}
    unknown_asins = {item["asin"] for item in eligibility if item["status"] == "unknown"}

    if ranked:
        winner = ranked[0]
        message = f"Recommended: {winner['title']}"
    elif unknown_asins:
        message = "No recommendation was made because one or more hard requirements could not be verified."
    else:
        message = "No product satisfies every explicit hard requirement."

    return {
        "status": "completed",
        "preferences": preferences,
        "preference_source": "local_fallback" if model_warning else "inkling",
        "model_warning": model_warning,
        "eligibility": eligibility,
        "eligible_products": sorted(eligible_asins),
        "unknown_products": sorted(unknown_asins),
        "recommendations": ranked,
        "analysis_warnings": warnings,
        "cart_errors": cart.get("errors", []),
        "message": message,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="ReviewTrust Shopping Agent")
    parser.add_argument("--need", required=True, help="Shopping requirements")
    parser.add_argument("links", nargs="+", help="One to five Amazon product links")
    args = parser.parse_args()
    result = run_workflow(args.links, args.need)
    print(json.dumps(result, indent=2, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
