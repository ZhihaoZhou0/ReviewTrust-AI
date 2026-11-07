from types import SimpleNamespace

from shopping_agent.eligibility import evaluate_cart
from shopping_agent.preferences import local_preferences, normalize_preferences
from shopping_agent.recommendation import rank_products
from shopping_agent.workflow import run_workflow


def bundle(asin: str, title: str, rating: float = 4.0) -> dict:
    return {
        "product": {
            "asin": asin,
            "title": title,
            "description": "Reliable long-lasting power for everyday devices",
            "characteristics": "",
            "category_breadcrumbs": "Electronics -> Batteries",
            "sample_rating": rating,
            "source_rating": rating,
            "product_url": f"https://www.amazon.com/dp/{asin}",
        },
        "reviews": [
            {
                "source_review_id": f"review-{asin}",
                "stars": 5,
                "body": "These lasted for months in my wireless mouse.",
            }
        ],
    }


def preferences(**updates) -> dict:
    value = normalize_preferences({
        "product_type": "batteries",
        "use_case": "wireless mouse",
        "hard_requirements": ["AA size"],
        "excluded_features": ["AAA size"],
        "priorities": ["reliability", "battery life"],
        "budget_max_usd": None,
        "missing_information": [],
    })
    value.update(updates)
    return value


def test_local_fallback_preserves_battery_size_and_exclusion():
    result = local_preferences(
        "I need AA batteries. Reliability matters most. I don't want AAA batteries."
    )
    assert result["hard_requirements"] == ["AA size"]
    assert result["excluded_features"] == ["AAA size"]
    assert result["priorities"][0] == "reliability"


def test_local_fallback_keeps_generic_explicit_constraints():
    result = local_preferences(
        "I need headphones. They must have USB-C. I don't want leather."
    )
    assert result["hard_requirements"] == ["USB-C"]
    assert result["excluded_features"] == ["leather"]


def test_subjective_model_requirements_become_priorities():
    result = normalize_preferences({
        "hard_requirements": ["AA battery size", "high reliability", "long battery life"],
        "priorities": ["price"],
    })
    assert result["hard_requirements"] == ["AA battery size"]
    assert result["priorities"] == ["price", "high reliability", "long battery life"]


def test_hard_requirements_filter_exact_battery_size():
    cart = {
        "products": [
            bundle("B000000001", "High performance AA batteries"),
            bundle("B000000002", "High performance AAA batteries"),
        ]
    }
    result = evaluate_cart(cart, preferences())
    assert [item["status"] for item in result] == ["eligible", "ineligible"]


def test_battery_size_uses_title_not_cross_sell_description():
    item = bundle("B000000001", "48-Pack AA batteries")
    item["product"]["description"] = "Compare our AA and AAA battery families"
    result = evaluate_cart({"products": [item]}, preferences())
    assert result[0]["status"] == "eligible"
    assert result[0]["detected_sizes"] == ["AA"]


def test_unverifiable_requirement_is_unknown_not_eligible():
    cart = {"products": [bundle("B000000001", "AA batteries")]}
    result = evaluate_cart(
        cart,
        preferences(hard_requirements=["AA size", "rechargeable"]),
    )
    assert result[0]["status"] == "unknown"
    assert "Cannot verify" in result[0]["reason"]


def test_ranker_uses_b1_b2_and_cites_reviews():
    cart = {"products": [bundle("B000000001", "AA batteries", 4.1)]}
    eligibility = evaluate_cart(cart, preferences())
    b1 = {
        "B000000001": SimpleNamespace(adjusted_rating=4.7),
    }
    b2 = {
        "B000000001": SimpleNamespace(
            pros=[{
                "aspect": "reliability",
                "label": "Reliability",
                "share": 0.3,
                "evidence": [{
                    "review_id": "r-1",
                    "stars": 5,
                    "text": "Dependable power for daily use.",
                }],
            }],
            cons=[],
        )
    }
    ranked, warnings = rank_products(
        cart, eligibility, preferences(), reliability=b1, pros_cons=b2
    )
    assert not warnings
    assert ranked[0]["rating_source"] == "B1 trust-adjusted"
    assert ranked[0]["citations"][0]["review_id"] == "r-1"
    assert ranked[0]["pros"][0]["label"] == "Reliability"
    assert ranked[0]["cons"] == []


def test_workflow_degrades_when_model_is_unavailable():
    cart = {"products": [bundle("B000000001", "AA batteries")], "errors": []}

    def fallback(_request):
        return preferences(), "TINKER_API_KEY is not configured."

    result = run_workflow(
        ["https://www.amazon.com/dp/B000000001"],
        "I need AA batteries",
        cart_builder=lambda _links: cart,
        preference_extractor=fallback,
        ranker=lambda *_args: ([{
            "rank": 1,
            "asin": "B000000001",
            "title": "AA batteries",
            "score": 80,
            "rating_used": 4.0,
            "rating_source": "available product sample",
            "matched_priorities": [],
            "citations": [],
            "product_url": "https://www.amazon.com/dp/B000000001",
        }], []),
    )
    assert result["status"] == "completed"
    assert result["preference_source"] == "local_fallback"
    assert result["recommendations"][0]["rank"] == 1


def test_workflow_rejects_more_than_five_products():
    result = run_workflow(["B000000001"] * 6, "Need batteries")
    assert result["status"] == "invalid_input"
