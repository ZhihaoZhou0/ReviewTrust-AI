"""Clean the pinned DataHive CSVs into PostgreSQL-ready CSV files.

Every valid source review row is retained, including identical rows. Source files are never edited.
This module uses the Python standard library and reads rows incrementally.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from collections import Counter
from datetime import datetime
from pathlib import Path


PRODUCT_COLUMNS = [
    "url", "asin", "main_image", "alt_images", "title", "breadcrumbs",
    "rating", "number_of_ratings", "description", "characteristics",
]
REVIEW_COLUMNS = [
    "id", "asin", "url", "body", "date", "title", "images", "videos",
    "stars", "user_id", "variation", "found_helpful", "verified_purchase",
]
PRODUCT_OUTPUT = [
    "asin", "title", "product_url", "main_image_url", "alt_images",
    "category_breadcrumbs", "description", "characteristics",
    "source_rating", "source_rating_count", "source_row_number",
    "source_row_hash",
]
REVIEW_OUTPUT = [
    "asin", "source_review_id", "review_url", "review_title", "body",
    "review_date", "stars", "user_id", "variation", "found_helpful",
    "verified_purchase", "images", "videos", "source_row_number",
    "source_row_hash",
]
ASIN_PATTERN = re.compile(r"[A-Z0-9]{10}\Z")


class InvalidRow(ValueError):
    pass


def optional_text(value: str | None) -> str:
    return (value or "").strip()


def required_text(value: str | None, field: str) -> str:
    result = optional_text(value)
    if not result:
        raise InvalidRow(f"missing_{field}")
    return result


def parse_asin(value: str | None) -> str:
    asin = required_text(value, "asin").upper()
    if not ASIN_PATTERN.fullmatch(asin):
        raise InvalidRow("invalid_asin")
    return asin


def parse_integer(value: str | None, field: str, *, minimum: int, maximum: int) -> int:
    raw = required_text(value, field)
    try:
        result = int(raw)
    except ValueError as error:
        raise InvalidRow(f"invalid_{field}") from error
    if not minimum <= result <= maximum:
        raise InvalidRow(f"invalid_{field}")
    return result


def parse_rating(value: str | None) -> str:
    raw = required_text(value, "rating")
    try:
        from decimal import Decimal, InvalidOperation

        rating = Decimal(raw)
        if not rating.is_finite() or not 1 <= rating <= 5 or -rating.as_tuple().exponent > 2:
            raise InvalidRow("invalid_rating")
    except InvalidOperation as error:
        raise InvalidRow("invalid_rating") from error
    return str(rating)


def parse_date(value: str | None) -> str:
    raw = required_text(value, "date")
    try:
        return datetime.strptime(raw, "%a %b %d %Y").date().isoformat()
    except ValueError as error:
        raise InvalidRow("invalid_date") from error


def parse_json(value: str | None, field: str, expected_type: type) -> str:
    raw = required_text(value, field)
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as error:
        raise InvalidRow(f"invalid_{field}") from error
    if not isinstance(parsed, expected_type):
        raise InvalidRow(f"invalid_{field}")
    return json.dumps(parsed, ensure_ascii=False, separators=(",", ":"))


def parse_verified(value: str | None) -> str:
    raw = optional_text(value).lower()
    if not raw:
        return ""  # PostgreSQL COPY reads this as NULL.
    if raw in {"1", "true"}:
        return "true"
    if raw in {"0", "false"}:
        return "false"
    raise InvalidRow("invalid_verified_purchase")


def row_hash(row: dict, columns: list[str]) -> str:
    canonical = json.dumps([row.get(key) for key in columns], ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def clean_product(row: dict, row_number: int, digest: str) -> dict:
    return {
        "asin": parse_asin(row.get("asin")),
        "title": required_text(row.get("title"), "title"),
        "product_url": optional_text(row.get("url")),
        "main_image_url": optional_text(row.get("main_image")),
        "alt_images": parse_json(row.get("alt_images"), "alt_images", list),
        "category_breadcrumbs": optional_text(row.get("breadcrumbs")),
        "description": optional_text(row.get("description")),
        "characteristics": parse_json(row.get("characteristics"), "characteristics", dict),
        "source_rating": parse_rating(row.get("rating")),
        "source_rating_count": parse_integer(row.get("number_of_ratings"), "number_of_ratings", minimum=0, maximum=2**63 - 1),
        "source_row_number": row_number,
        "source_row_hash": digest,
    }


def clean_review(row: dict, row_number: int, digest: str, product_asins: set[str]) -> dict:
    asin = parse_asin(row.get("asin"))
    if asin not in product_asins:
        raise InvalidRow("orphan_asin")
    # Preserve source text exactly for NLP and audit; only whitespace-only text becomes NULL.
    body = row.get("body") or ""
    if not body.strip():
        body = ""
    return {
        "asin": asin,
        "source_review_id": required_text(row.get("id"), "id"),
        "review_url": optional_text(row.get("url")),
        "review_title": optional_text(row.get("title")),
        "body": body,
        "review_date": parse_date(row.get("date")),
        "stars": parse_integer(row.get("stars"), "stars", minimum=1, maximum=5),
        "user_id": optional_text(row.get("user_id")),
        "variation": optional_text(row.get("variation")),
        "found_helpful": parse_integer(row.get("found_helpful"), "found_helpful", minimum=0, maximum=2**31 - 1),
        "verified_purchase": parse_verified(row.get("verified_purchase")),
        "images": parse_json(row.get("images"), "images", list),
        "videos": parse_json(row.get("videos"), "videos", list),
        "source_row_number": row_number,
        "source_row_hash": digest,
    }


def process_file(
    source: Path,
    destination: Path,
    expected_columns: list[str],
    output_columns: list[str],
    kind: str,
    product_asins: set[str] | None = None,
) -> tuple[dict, set[str]]:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    stats = Counter()
    accepted_asins: set[str] = set()
    try:
        with source.open("r", encoding="utf-8-sig", newline="") as input_file, temporary.open("w", encoding="utf-8", newline="") as output_file:
            reader = csv.DictReader(input_file)
            if reader.fieldnames != expected_columns:
                raise ValueError(f"Unexpected {kind} columns: {reader.fieldnames}")
            writer = csv.DictWriter(output_file, fieldnames=output_columns)
            writer.writeheader()
            for row_number, row in enumerate(reader, 1):
                stats["input_rows"] += 1
                if None in row or any(value is None for value in row.values()):
                    stats["rejected_malformed_csv"] += 1
                    continue
                digest = row_hash(row, expected_columns)
                try:
                    if kind == "products":
                        cleaned = clean_product(row, row_number, digest)
                        if cleaned["asin"] in accepted_asins:
                            raise InvalidRow("duplicate_product_asin")
                    else:
                        cleaned = clean_review(row, row_number, digest, product_asins or set())
                except InvalidRow as error:
                    stats[f"rejected_{error}"] += 1
                    continue
                accepted_asins.add(cleaned["asin"])
                writer.writerow(cleaned)
                stats["output_rows"] += 1
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)
    return dict(sorted(stats.items())), accepted_asins


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--products", type=Path, required=True)
    parser.add_argument("--reviews", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()

    product_stats, product_asins = process_file(
        args.products, args.output_dir / "products_clean.csv", PRODUCT_COLUMNS,
        PRODUCT_OUTPUT, "products",
    )
    review_stats, _ = process_file(
        args.reviews, args.output_dir / "reviews_clean.csv", REVIEW_COLUMNS,
        REVIEW_OUTPUT, "reviews", product_asins,
    )
    result = {
        "products": product_stats,
        "reviews": review_stats,
        "rules": {
            "review_retention": "Retain every valid source review row, including rows with identical content or source IDs.",
            "missing_optional_text": "Convert empty or whitespace-only optional fields to SQL NULL via empty CSV values.",
            "review_body": "Preserve nonempty original text exactly; blank text becomes SQL NULL.",
            "verified_purchase": "1/true -> true, 0/false -> false, empty -> SQL NULL.",
            "date": "Parse source date and write ISO YYYY-MM-DD.",
            "invalid_required_data": "Reject rows with invalid ASIN, required ID/title/date/rating/stars/helpful count, malformed JSON, or orphan ASIN.",
        },
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
