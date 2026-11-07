"""Amazon link matching at the dashboard boundary."""

from __future__ import annotations

import unittest

from dashboard.view_model import amazon_asin


class AmazonLinkTests(unittest.TestCase):
    def test_common_product_url_shapes(self) -> None:
        examples = (
            "https://www.amazon.com/Owala-Bottle/dp/B085DVHQ57?th=1",
            "https://amazon.com/gp/product/B085DVHQ57/ref=abc",
            "https://smile.amazon.co.uk/product-reviews/B085DVHQ57",
            "https://www.amazon.com/gp/aw/d/B085DVHQ57",
            "https://www.amazon.com/exec/obidos/ASIN?asin=B085DVHQ57",
        )
        for link in examples:
            with self.subTest(link=link):
                self.assertEqual(amazon_asin(link), "B085DVHQ57")

    def test_rejects_non_amazon_and_unresolvable_links(self) -> None:
        for link in (
            "https://amazon.com.evil.example/dp/B085DVHQ57",
            "https://amzn.to/abc123",
            "https://www.amazon.com/s?k=water+bottle",
            "B085DVHQ57",
            "",
        ):
            with self.subTest(link=link):
                self.assertIsNone(amazon_asin(link))


if __name__ == "__main__":
    unittest.main()
