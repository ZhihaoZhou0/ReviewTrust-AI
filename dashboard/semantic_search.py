
"""Sentence-BERT semantic search for the product catalog."""

from __future__ import annotations

from functools import lru_cache

import numpy as np
from sentence_transformers import SentenceTransformer

from dashboard.data_access import Product


MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"


@lru_cache(maxsize=1)
def get_model() -> SentenceTransformer:
    """Load the embedding model once per process."""
    return SentenceTransformer(MODEL_NAME)


class SemanticProductSearch:
    """Build and query semantic embeddings for catalog products."""

    def __init__(self, products: list[Product]) -> None:
        self.products = products

        # Include the full category to capture the product's purpose.
        self.documents = [
            f"{product.title}. Category: "
            f"{product.category_path or product.category}"
            for product in products
        ]

        self.model = get_model()

        # Normalize embeddings for cosine similarity.
        self.embeddings = self.model.encode(
            self.documents,
            batch_size=64,
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False,
        )

    def search(
        self,
        query: str,
        top_k: int = 20,
    ) -> list[tuple[Product, float]]:
        """Return semantic matches ranked by cosine similarity."""

        if not query.strip() or top_k <= 0:
            return []

        query_embedding = self.model.encode(
            [query],
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False,
        )[0]

        scores = np.dot(self.embeddings, query_embedding)

        indices = np.argsort(-scores)[:top_k]

        return [
            (self.products[int(index)], float(scores[index]))
            for index in indices
        ]
