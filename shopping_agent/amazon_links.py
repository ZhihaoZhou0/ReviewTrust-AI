
"""Parse Amazon product URLs into ASINs.

This module does not scrape Amazon or make HTTP requests.
It only extracts product identifiers from user-provided URLs.
"""

import re
from urllib.parse import parse_qs, urlsplit


ASIN_PATTERN = re.compile(
    r"^[A-Z0-9]{10}$",
    re.IGNORECASE,
)

PRODUCT_PATH_PATTERN = re.compile(
    r"/(?:dp|gp/product|gp/aw/d)/([A-Z0-9]{10})(?=/|$)",
    re.IGNORECASE,
)

AMAZON_DOMAINS = (
    "amazon.com",
    "amazon.ca",
    "amazon.co.uk",
    "amazon.de",
    "amazon.fr",
    "amazon.it",
    "amazon.es",
    "amazon.in",
    "amazon.co.jp",
    "amazon.com.au",
)


def extract_asin(value: str) -> str:
    """Extract an ASIN from an Amazon URL or a raw ASIN."""

    value = value.strip()

    if not value:
        raise ValueError("Amazon URL cannot be empty.")

    # Accept a raw ASIN.
    if ASIN_PATTERN.fullmatch(value):
        return value.upper()

    # Handle URLs without an explicit scheme.
    if "://" not in value:
        value = "https://" + value

    parsed = urlsplit(value)
    hostname = (parsed.hostname or "").lower()

    # Validate the domain before accepting any identifier.
    valid_domain = any(
        hostname == domain
        or hostname.endswith("." + domain)
        for domain in AMAZON_DOMAINS
    )

    if parsed.scheme not in ("http", "https") or not valid_domain:
        raise ValueError("Unsupported Amazon URL.")

    # Standard Amazon product URL formats.
    match = PRODUCT_PATH_PATTERN.search(parsed.path)

    if match:
        return match.group(1).upper()

    # Some URLs include the ASIN as a query parameter.
    for key, values in parse_qs(parsed.query).items():
        if key.lower() == "asin" and values:
            asin = values[0].upper()

            if ASIN_PATTERN.fullmatch(asin):
                return asin

    raise ValueError("No valid ASIN found in the URL.")
