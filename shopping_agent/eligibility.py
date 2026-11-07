"""Conservative hard-requirement enforcement for shopping candidates."""

from __future__ import annotations

import re
from typing import Any

STOPWORDS = {
    "a", "an", "and", "be", "for", "has", "have", "include", "includes",
    "is", "must", "of", "or", "should", "size", "the", "to", "with",
}


def battery_sizes(text: str) -> set[str]:
    return set(re.findall(r"\b(?:AAA|AA)\b", text.upper()))


def _document(product: dict[str, Any]) -> str:
    return " ".join(
        str(product.get(field) or "")
        for field in (
            "title", "description", "characteristics", "category_breadcrumbs",
        )
    )


def _keywords(requirement: str) -> list[str]:
    words = re.findall(r"[a-z0-9]+", requirement.casefold())
    return [word for word in words if len(word) > 1 and word not in STOPWORDS]


def _matches_phrase(requirement: str, document: str) -> bool:
    sizes = battery_sizes(requirement)
    if sizes:
        return bool(sizes & battery_sizes(document))
    words = _keywords(requirement)
    return bool(words) and all(word in document.casefold() for word in words)


def evaluate_cart(cart: dict, preferences: dict) -> list[dict]:
    """Classify every product as eligible, ineligible, or unknown.

    A product passes only when every explicit hard requirement is verifiable from
    catalog text and no explicit exclusion is present. Unverifiable requirements
    remain unknown instead of being treated as satisfied.
    """
    requirements = [str(item) for item in preferences.get("hard_requirements", [])]
    exclusions = [str(item) for item in preferences.get("excluded_features", [])]
    budget = preferences.get("budget_max_usd")
    results = []

    for bundle in cart.get("products", []):
        product = bundle["product"]
        document = _document(product)
        title = str(product.get("title") or "")
        checks = []
        failed = []
        unknown = []

        for exclusion in exclusions:
            match_document = title if battery_sizes(exclusion) else document
            matched = _matches_phrase(exclusion, match_document)
            checks.append({
                "requirement": f"Exclude: {exclusion}",
                "status": "failed" if matched else "passed",
            })
            if matched:
                failed.append(f"Contains excluded feature: {exclusion}")

        for requirement in requirements:
            match_document = title if battery_sizes(requirement) else document
            matched = _matches_phrase(requirement, match_document)
            checks.append({
                "requirement": requirement,
                "status": "passed" if matched else "unknown",
            })
            if not matched:
                unknown.append(f"Cannot verify requirement from catalog data: {requirement}")

        if budget is not None:
            price = product.get("price")
            if price is None:
                checks.append({"requirement": f"Price <= ${budget:g}", "status": "unknown"})
                unknown.append("Current price is unavailable in the historical dataset.")
            elif float(price) > float(budget):
                checks.append({"requirement": f"Price <= ${budget:g}", "status": "failed"})
                failed.append(f"Price ${float(price):.2f} exceeds budget ${float(budget):.2f}.")

        if failed:
            status = "ineligible"
            reason = failed[0]
        elif unknown:
            status = "unknown"
            reason = unknown[0]
        else:
            status = "eligible"
            reason = "All explicit hard requirements were verified."

        results.append({
            "asin": product["asin"],
            "title": product["title"],
            "status": status,
            "reason": reason,
            "checks": checks,
            "detected_sizes": sorted(battery_sizes(title)),
        })
    return results


def evaluate_battery_cart(cart: dict, preferences: dict) -> list[dict]:
    """Backward-compatible alias for the original battery-only evaluator."""
    return evaluate_cart(cart, preferences)
