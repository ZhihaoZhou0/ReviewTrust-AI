"""Personalized ranking backed by precomputed B1/B2 review evidence."""

from __future__ import annotations

import re
from typing import Any

from dashboard.analysis_access import load_pros_cons_results, load_reliability_results


def _terms(values: list[str]) -> set[str]:
    return {
        word
        for value in values
        for word in re.findall(r"[a-z0-9]+", value.casefold())
        if len(word) > 2
    }


def _analysis_maps() -> tuple[dict, dict, str | None]:
    try:
        return load_reliability_results(), load_pros_cons_results(), None
    except (OSError, ValueError, TypeError) as error:
        return {}, {}, f"Precomputed analysis could not be loaded: {error}"


def rank_products(
    cart: dict,
    eligibility: list[dict],
    preferences: dict,
    *,
    reliability: dict | None = None,
    pros_cons: dict | None = None,
) -> tuple[list[dict[str, Any]], list[str]]:
    """Rank verified candidates and attach review citations.

    Hard-filtered and unknown products never receive a recommendation rank.
    """
    warnings: list[str] = []
    if reliability is None or pros_cons is None:
        loaded_b1, loaded_b2, warning = _analysis_maps()
        reliability = loaded_b1 if reliability is None else reliability
        pros_cons = loaded_b2 if pros_cons is None else pros_cons
        if warning:
            warnings.append(warning)

    statuses = {item["asin"]: item for item in eligibility}
    desired = _terms(
        list(preferences.get("priorities", []))
        + ([preferences["use_case"]] if preferences.get("use_case") else [])
    )
    ranked = []

    for bundle in cart.get("products", []):
        product = bundle["product"]
        asin = product["asin"]
        eligibility_item = statuses.get(asin, {"status": "unknown"})
        if eligibility_item["status"] != "eligible":
            continue

        b1 = reliability.get(asin)
        base_rating = (
            float(b1.adjusted_rating)
            if b1 is not None
            else float(product.get("sample_rating") or product.get("source_rating") or 0)
        )
        score = base_rating * 20.0
        evidence: list[dict[str, Any]] = []
        matched_priorities: list[str] = []
        b2 = pros_cons.get(asin)

        if b2 is not None:
            for aspect in b2.pros:
                aspect_text = f"{aspect.get('aspect', '')} {aspect.get('label', '')}".casefold()
                aspect_terms = _terms([aspect_text])
                overlap = desired & aspect_terms
                if overlap:
                    matched_priorities.extend(sorted(overlap))
                    score += min(float(aspect.get("share", 0)) * 20.0, 4.0)
                    for citation in aspect.get("evidence", [])[:2]:
                        text = str(citation.get("text", "")).strip()
                        if text:
                            evidence.append({
                                "review_id": str(citation.get("review_id", "unknown")),
                                "stars": citation.get("stars"),
                                "quote": text,
                                "aspect": str(aspect.get("label", "Review theme")),
                            })
                if len(evidence) >= 3:
                    break

        if not evidence:
            for review in bundle.get("reviews", [])[:3]:
                text = str(review.get("body", "")).strip()
                if text:
                    evidence.append({
                        "review_id": str(review.get("source_review_id") or review.get("review_pk")),
                        "stars": review.get("stars"),
                        "quote": text,
                        "aspect": "Original review",
                    })

        ranked.append({
            "asin": asin,
            "title": product["title"],
            "score": round(score, 2),
            "rating_used": round(base_rating, 3),
            "rating_source": "B1 trust-adjusted" if b1 is not None else "available product sample",
            "matched_priorities": sorted(set(matched_priorities)),
            "citations": evidence[:3],
            "pros": list(b2.pros[:3]) if b2 is not None else [],
            "cons": list(b2.cons[:3]) if b2 is not None else [],
            "product_url": product.get("product_url") or f"https://www.amazon.com/dp/{asin}",
        })

    ranked.sort(key=lambda item: (item["score"], item["rating_used"]), reverse=True)
    for position, item in enumerate(ranked, 1):
        item["rank"] = position
    if not ranked:
        warnings.append("No product passed every explicit hard requirement.")
    return ranked, warnings
