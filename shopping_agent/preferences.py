"""Extract and normalize shopping preferences.

The preferred path uses Thinking Machines' Anthropic-compatible Inkling API.
A conservative local parser keeps the workflow usable when the model or key is
unavailable; it never silently turns an uncertain requirement into a pass.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any

BASE_URL = "https://tinker.thinkingmachines.dev/services/tinker-prod/anthropic/api"
MODEL = "thinkingmachines/Inkling"

SYSTEM_PROMPT = """
You extract shopping requirements into JSON.
Separate mandatory requirements from preferences. Preserve exact specifications,
put explicit negatives in excluded_features, and do not invent information.
Return only JSON with exactly these keys:
{"product_type": null, "use_case": null, "hard_requirements": [],
 "excluded_features": [], "priorities": [], "budget_max_usd": null,
 "missing_information": []}
"""


class PreferenceModelError(RuntimeError):
    """The remote preference model could not provide a valid response."""


def _clean_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def normalize_preferences(value: dict[str, Any]) -> dict[str, Any]:
    """Return the stable preference schema expected by the workflow."""
    budget = value.get("budget_max_usd")
    try:
        budget = float(budget) if budget is not None else None
    except (TypeError, ValueError):
        budget = None
    hard_requirements = _clean_list(value.get("hard_requirements"))
    priorities = _clean_list(value.get("priorities"))
    objective_hard = []
    for requirement in hard_requirements:
        subjective = re.search(
            r"\b(?:reliab(?:le|ility)|battery life|durab(?:le|ility)|quality|performance|value)\b",
            requirement,
            re.I,
        )
        measurable = re.search(r"\d|\bat least\b|\bno more than\b", requirement, re.I)
        if subjective and not measurable:
            if requirement not in priorities:
                priorities.append(requirement)
        else:
            objective_hard.append(requirement)

    return {
        "product_type": str(value["product_type"]).strip() if value.get("product_type") else None,
        "use_case": str(value["use_case"]).strip() if value.get("use_case") else None,
        "hard_requirements": objective_hard,
        "excluded_features": _clean_list(value.get("excluded_features")),
        "priorities": priorities,
        "budget_max_usd": budget,
        "missing_information": _clean_list(value.get("missing_information")),
    }


def local_preferences(user_request: str) -> dict[str, Any]:
    """Extract only explicit, high-confidence constraints without a model."""
    text = " ".join(user_request.split())
    lower = text.casefold()
    hard: list[str] = []
    excluded: list[str] = []
    ranked_priorities: list[tuple[int, str]] = []

    for size in ("AAA", "AA"):
        negative = re.search(
            rf"\b(?:do not|don't|no|without|exclude)\b[^.]*\b{size}\b", text, re.I
        )
        if negative:
            excluded.append(f"{size} size")
        elif re.search(rf"\b{size}\b", text, re.I):
            hard.append(f"{size} size")

    for match in re.finditer(
        r"(?:do not want|don't want|without|exclude(?:d)?|must not have)\s+([^.,;]+)",
        text,
        re.I,
    ):
        phrase = match.group(1).strip()
        if phrase and not re.search(r"\b(?:AAA|AA)\b", phrase, re.I):
            excluded.append(phrase)

    for match in re.finditer(
        r"(?:must have|must include|require[sd]?)\s+([^.,;]+)",
        text,
        re.I,
    ):
        phrase = match.group(1).strip()
        if phrase and phrase not in hard:
            hard.append(phrase)

    budget_match = re.search(
        r"(?:under|below|no more than|max(?:imum)?(?: of)?)\s*\$\s*(\d+(?:\.\d{1,2})?)",
        text,
        re.I,
    )
    budget = float(budget_match.group(1)) if budget_match else None
    for priority in (
        "reliability", "battery life", "durability", "comfort", "quality",
        "performance", "ease of use", "design", "price", "value",
    ):
        position = lower.find(priority)
        if position >= 0:
            ranked_priorities.append((position, priority))
    ranked_priorities.sort()

    type_match = re.search(
        r"(?:need|want|looking for|shopping for)\s+(?:an?\s+|some\s+)?([^.,;]+)",
        text,
        re.I,
    )
    return normalize_preferences({
        "product_type": type_match.group(1).strip() if type_match else None,
        "use_case": None,
        "hard_requirements": hard,
        "excluded_features": excluded,
        "priorities": [item[1] for item in ranked_priorities],
        "budget_max_usd": budget,
        "missing_information": [
            "Model-based preference extraction was unavailable; review the inferred constraints."
        ],
    })


def _response_text(response: Any) -> str:
    return "\n".join(
        block.text for block in response.content
        if getattr(block, "type", None) == "text"
    ).strip()


def extract_preferences(
    user_request: str,
    *,
    api_key: str | None = None,
    client: Any | None = None,
) -> dict[str, Any]:
    """Convert natural-language needs to the normalized preference schema."""
    if not user_request.strip():
        raise ValueError("Shopping requirements cannot be empty.")
    api_key = api_key or os.getenv("TINKER_API_KEY")
    if client is None and not api_key:
        raise PreferenceModelError("TINKER_API_KEY is not configured.")
    if client is None:
        try:
            from anthropic import Anthropic
        except ImportError as error:
            raise PreferenceModelError("The anthropic package is not installed.") from error
        client = Anthropic(base_url=BASE_URL, api_key=api_key, timeout=45.0, max_retries=1)
    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=700,
            thinking={"type": "disabled"},
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_request}],
        )
        text = _response_text(response)
        if text.startswith("```"):
            lines = text.splitlines()[1:]
            if lines and lines[-1].strip() == "```":
                lines.pop()
            text = "\n".join(lines).strip()
        parsed = json.loads(text)
        if not isinstance(parsed, dict):
            raise ValueError("response is not a JSON object")
        return normalize_preferences(parsed)
    except (json.JSONDecodeError, ValueError, TypeError, AttributeError) as error:
        raise PreferenceModelError(f"Inkling returned an invalid preference response: {error}") from error
    except Exception as error:
        raise PreferenceModelError(f"Inkling request failed: {error}") from error


def preferences_with_fallback(user_request: str) -> tuple[dict[str, Any], str | None]:
    """Use Inkling when available and report a safe local fallback."""
    try:
        return extract_preferences(user_request), None
    except PreferenceModelError as error:
        return local_preferences(user_request), str(error)
