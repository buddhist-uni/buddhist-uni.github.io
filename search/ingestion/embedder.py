"""
Embedder wrapping sentence-transformers for Buddhist University content.
Model: all-MiniLM-L6-v2 (384 dims, fast, high quality for semantic search).
"""

from __future__ import annotations

import numpy as np
from sentence_transformers import SentenceTransformer
from typing import Sequence

MODEL_NAME = "all-MiniLM-L6-v2"
VECTOR_SIZE = 384


class Embedder:
    """
    Singleton-style embedder. Load once, encode many.

    Example:
        embedder = Embedder()
        vectors = embedder.encode(["nibbana", "impermanence and suffering"])
        # vectors.shape == (2, 384)
    """

    _instance: Embedder | None = None

    def __new__(cls) -> Embedder:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._loaded = False
        return cls._instance

    def _load(self) -> None:
        if not self._loaded:
            print(f"🔄 Chargement du modèle {MODEL_NAME}...")
            self._model = SentenceTransformer(MODEL_NAME)
            self._loaded = True
            print(f"✅ Modèle chargé ({VECTOR_SIZE} dims)")

    def encode(
        self,
        texts: str | Sequence[str],
        batch_size: int = 64,
        show_progress: bool = False,
    ) -> np.ndarray:
        """
        Encode one or several texts into normalized vectors.

        Args:
            texts: Single string or list of strings
            batch_size: Batch size for GPU/CPU processing
            show_progress: Show tqdm progress bar

        Returns:
            numpy array of shape (n, 384), L2-normalized (cosine-ready)
        """
        self._load()

        if isinstance(texts, str):
            texts = [texts]

        vectors = self._model.encode(
            list(texts),
            batch_size=batch_size,
            show_progress_bar=show_progress,
            normalize_embeddings=True,  # L2 normalize for cosine similarity
            convert_to_numpy=True,
        )
        return vectors

    def encode_query(self, query: str) -> list[float]:
        """Encode a single search query, returns list[float] for Qdrant."""
        vec = self.encode(query)
        return vec[0].tolist()


# Module-level singleton
_embedder: Embedder | None = None


def get_embedder() -> Embedder:
    """Get or create the module-level embedder singleton."""
    global _embedder
    if _embedder is None:
        _embedder = Embedder()
    return _embedder


if __name__ == "__main__":
    e = get_embedder()
    test_texts = [
        "impermanence and suffering in early Buddhism",
        "Pali grammar introduction for beginners",
        "meditation practice mindfulness breath",
    ]
    vecs = e.encode(test_texts)
    print(f"Shape: {vecs.shape}")  # (3, 384)
    print(f"Norme vecteur[0]: {np.linalg.norm(vecs[0]):.4f}")  # ~1.0
    print("✅ Embedder OK")
