"""Profile the two CSV files in the pinned DataHive Amazon reviews snapshot.

Run from the repository root:
    python3 pipeline/audit_dataset.py --products data/raw/products.csv \
        --reviews data/raw/reviews.csv --output docs/data-audit.json

Uses only the Python standard library and does not modify source CSV files.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import statistics
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path


SOURCE = {
    "repository": "datahiveai/Amazon-Reviews-Dataset",
    "revision": "2531d9083bd3aab11261eab7e69d0d0f358a6d6f",
    "url": "https://huggingface.co/datasets/datahiveai/Amazon-Reviews-Dataset",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def normalized(value: str | None) -> str:
    return (value or "").strip()


def scan(path: Path, kind: str) -> tuple[dict, dict]:
    missing = Counter()
    malformed = 0
    row_count = 0
    ids = set()
    duplicate_ids = 0
    first_id_row = {}
    first_pair_row = {}
    seen_rows = set()
    exact_duplicate_rows = 0
    duplicate_id_different_rows = 0
    duplicate_id_other_asin = 0
    duplicate_asin_id_pairs = 0
    duplicate_asin_id_different_rows = 0
    asin_counts = Counter()
    star_counts = Counter()
    numeric_invalid = Counter()
    numeric_ranges: dict[str, list[float]] = {}
    dates = Counter()
    invalid_dates = 0
    date_min = None
    date_max = None
    body_hashes = Counter()
    body_empty = 0
    verified = Counter()
    categories = Counter()
    sample_stars = defaultdict(float)
    product_rating = {}
    product_rating_count = {}
    id_column = "asin" if kind == "products" else "id"
    numeric_columns = (
        ("rating", "number_of_ratings")
        if kind == "products"
        else ("stars", "found_helpful")
    )

    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        headers = reader.fieldnames or []
        for row in reader:
            row_count += 1
            if None in row or any(value is None for value in row.values()):
                malformed += 1
            for key in headers:
                if not normalized(row.get(key)):
                    missing[key] += 1
            identifier = normalized(row.get(id_column))
            row_digest = hashlib.sha256(repr(tuple(row.items())).encode("utf-8")).digest()
            if row_digest in seen_rows:
                exact_duplicate_rows += 1
            seen_rows.add(row_digest)
            if identifier:
                if identifier in ids:
                    duplicate_ids += 1
                ids.add(identifier)
            asin = normalized(row.get("asin"))
            if asin:
                asin_counts[asin] += 1
            if kind == "reviews" and identifier:
                if identifier in first_id_row:
                    first_digest, first_asin = first_id_row[identifier]
                    duplicate_id_different_rows += first_digest != row_digest
                    duplicate_id_other_asin += first_asin != asin
                else:
                    first_id_row[identifier] = (row_digest, asin)
                pair = (asin, identifier)
                if pair in first_pair_row:
                    duplicate_asin_id_pairs += 1
                    duplicate_asin_id_different_rows += first_pair_row[pair] != row_digest
                else:
                    first_pair_row[pair] = row_digest
            for key in numeric_columns:
                value = normalized(row.get(key))
                if not value:
                    continue
                try:
                    number = float(value)
                    if not (number == number and abs(number) != float("inf")):
                        raise ValueError(value)
                    if key not in numeric_ranges:
                        numeric_ranges[key] = [number, number]
                    else:
                        numeric_ranges[key][0] = min(numeric_ranges[key][0], number)
                        numeric_ranges[key][1] = max(numeric_ranges[key][1], number)
                    if kind == "reviews" and key == "stars" and asin:
                        sample_stars[asin] += number
                    if kind == "products" and asin:
                        if key == "rating":
                            product_rating[asin] = number
                        elif key == "number_of_ratings":
                            product_rating_count[asin] = int(number)
                except ValueError:
                    numeric_invalid[key] += 1
            if kind == "products":
                breadcrumb = normalized(row.get("breadcrumbs"))
                if breadcrumb:
                    categories[breadcrumb.split(" -> ")[0]] += 1
            else:
                star_counts[normalized(row.get("stars")) or "<empty>"] += 1
                value = normalized(row.get("date"))
                if value:
                    try:
                        parsed = datetime.strptime(value, "%a %b %d %Y").date()
                        date_min = min(date_min, parsed) if date_min else parsed
                        date_max = max(date_max, parsed) if date_max else parsed
                        dates[str(parsed.year)] += 1
                    except ValueError:
                        invalid_dates += 1
                body = normalized(row.get("body"))
                if body:
                    body_hashes[hashlib.sha256(body.encode("utf-8")).digest()] += 1
                else:
                    body_empty += 1
                verified[normalized(row.get("verified_purchase")) or "<empty>"] += 1

    report = {
        "file": str(path),
        "bytes": path.stat().st_size,
        "sha256": sha256(path),
        "columns": headers,
        "rows": row_count,
        "malformed_rows": malformed,
        "missing_by_column": dict(missing),
        "distinct_identifiers": len(ids),
        "duplicate_identifiers": duplicate_ids,
        "exact_duplicate_rows": exact_duplicate_rows,
        "distinct_asins": len(asin_counts),
        "numeric_min_max": numeric_ranges,
        "invalid_numeric_by_column": dict(numeric_invalid),
    }
    if kind == "products":
        report["top_level_categories"] = categories.most_common()
    else:
        counts = list(asin_counts.values())
        report.update(
            {
                "date_min": str(date_min) if date_min else None,
                "date_max": str(date_max) if date_max else None,
                "date_by_year": dict(sorted(dates.items())),
                "invalid_dates": invalid_dates,
                "empty_bodies": body_empty,
                "exact_duplicate_body_rows": sum(n - 1 for n in body_hashes.values() if n > 1),
                "verified_purchase_values": dict(verified),
                "star_counts": dict(sorted(star_counts.items())),
                "duplicate_id_different_rows": duplicate_id_different_rows,
                "duplicate_id_other_asin": duplicate_id_other_asin,
                "duplicate_asin_id_pairs": duplicate_asin_id_pairs,
                "duplicate_asin_id_different_rows": duplicate_asin_id_different_rows,
                "reviews_per_asin": {
                    "min": min(counts) if counts else 0,
                    "median": statistics.median(counts) if counts else 0,
                    "max": max(counts) if counts else 0,
                    "at_least_100": sum(n >= 100 for n in counts),
                    "at_least_500": sum(n >= 500 for n in counts),
                },
            }
        )
    aux = {
        "asin_counts": asin_counts,
        "sample_stars": sample_stars,
        "product_rating": product_rating,
        "product_rating_count": product_rating_count,
    }
    return report, aux


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--products", type=Path, required=True)
    parser.add_argument("--reviews", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    products, product_aux = scan(args.products, "products")
    reviews, review_aux = scan(args.reviews, "reviews")
    product_asins = set(product_aux["asin_counts"])
    review_asins = set(review_aux["asin_counts"])
    orphan_asins = review_asins - product_asins
    orphan_rows = sum(review_aux["asin_counts"][asin] for asin in orphan_asins)
    comparable = [
        (
            asin,
            product_aux["product_rating"][asin],
            review_aux["sample_stars"][asin] / count,
            count,
            product_aux["product_rating_count"].get(asin),
        )
        for asin, count in review_aux["asin_counts"].items()
        if count and asin in product_aux["product_rating"]
    ]
    comparable.sort(key=lambda item: abs(item[1] - item[2]), reverse=True)
    result = {
        "source": SOURCE,
        "products": products,
        "reviews": reviews,
        "join": {
            "matched_review_rows": reviews["rows"] - orphan_rows - reviews["missing_by_column"].get("asin", 0),
            "orphan_review_rows": orphan_rows,
            "orphan_distinct_asins": len(orphan_asins),
            "products_without_reviews": len(product_asins - review_asins),
        },
        "rating_comparison": {
            "comparable_products": len(comparable),
            "products_with_source_count_different_from_sample_count": sum(
                source_count != sample_count
                for _, _, _, sample_count, source_count in comparable
            ),
            "largest_absolute_differences": [
                {
                    "asin": asin,
                    "source_rating": source_rating,
                    "sample_review_mean": round(sample_mean, 3),
                    "sample_review_count": sample_count,
                    "source_rating_count": source_count,
                }
                for asin, source_rating, sample_mean, sample_count, source_count in comparable[:10]
            ],
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "products": products["rows"], "reviews": reviews["rows"], "join": result["join"]}, indent=2))


if __name__ == "__main__":
    main()
