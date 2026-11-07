"""Regression checks for the pinned source and A2 quality gate."""

from __future__ import annotations

import csv
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

import polars as pl

from pipeline import validate
from pipeline.clean_dataset import PRODUCT_OUTPUT, REVIEW_OUTPUT
from pipeline.source import expected_counts, verify_file


class SourceContractTests(unittest.TestCase):
    def test_source_file_requires_expected_size_and_digest(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "products.csv"
            path.write_bytes(b"pinned source")
            digest = hashlib.sha256(b"pinned source").hexdigest()
            verify_file(path, 13, digest)
            with self.assertRaisesRegex(ValueError, "Unexpected size"):
                verify_file(path, 14, digest)
            with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
                verify_file(path, 13, "0" * 64)

    def test_expected_counts_match_a1_audit(self) -> None:
        self.assertEqual(expected_counts(), (2727, 252134))


class QualityGateTests(unittest.TestCase):
    def test_empty_cleaned_snapshot_fails_and_writes_report(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            for filename, columns in (
                ("products_clean.csv", PRODUCT_OUTPUT),
                ("reviews_clean.csv", REVIEW_OUTPUT),
            ):
                with (output / filename).open("w", newline="") as handle:
                    csv.writer(handle).writerow(columns)

            original = validate.PROCESSED_DIR
            validate.PROCESSED_DIR = output
            try:
                with self.assertRaisesRegex(ValueError, "Data quality validation failed"):
                    validate.run_validation()
            finally:
                validate.PROCESSED_DIR = original

            report = json.loads((output / "validation-report.json").read_text())
            self.assertFalse(report["valid"])
            self.assertEqual(report["snapshot_issues"]["review_count"]["actual"], 0)
            self.assertEqual(report["snapshot_issues"]["product_count"]["actual"], 0)

    def test_extra_cleaned_column_breaks_contract(self) -> None:
        frame = pl.DataFrame({name: [] for name in PRODUCT_OUTPUT + ["extra"]})
        with self.assertRaisesRegex(ValueError, "A1 contract"):
            validate.check_schema(frame, PRODUCT_OUTPUT)


if __name__ == "__main__":
    unittest.main()
