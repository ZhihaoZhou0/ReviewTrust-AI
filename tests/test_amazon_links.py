
"""Unit tests for Amazon URL parsing."""

import unittest

from shopping_agent.amazon_links import extract_asin


class TestAmazonLinks(unittest.TestCase):

    def test_raw_asin(self):
        result = extract_asin("b0xxxxxxxx")
        self.assertEqual(result, "B0XXXXXXXX")

    def test_standard_url(self):
        result = extract_asin(
            "https://www.amazon.com/dp/B0XXXXXXXX"
        )
        self.assertEqual(result, "B0XXXXXXXX")

    def test_url_with_product_name(self):
        result = extract_asin(
            "https://www.amazon.com/Product/dp/B0XXXXXXXX?th=1"
        )
        self.assertEqual(result, "B0XXXXXXXX")

    def test_gp_product_url(self):
        result = extract_asin(
            "https://www.amazon.com/gp/product/B0XXXXXXXX"
        )
        self.assertEqual(result, "B0XXXXXXXX")

    def test_mobile_url(self):
        result = extract_asin(
            "https://www.amazon.com/gp/aw/d/B0XXXXXXXX"
        )
        self.assertEqual(result, "B0XXXXXXXX")

    def test_invalid_domain(self):
        with self.assertRaises(ValueError):
            extract_asin(
                "https://amazon.com.evil.example/dp/B0XXXXXXXX"
            )

    def test_missing_asin(self):
        with self.assertRaises(ValueError):
            extract_asin("https://www.amazon.com/")

    def test_empty_input(self):
        with self.assertRaises(ValueError):
            extract_asin("")


if __name__ == "__main__":
    unittest.main()
