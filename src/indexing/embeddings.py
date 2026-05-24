"""Local embedding model wrapper for dense vector generation."""

import hashlib
import sqlite3
import time
import json
from pathlib import Path

EMBEDDING_DIM = 1024

try:
    from fastembed import TextEmbedding
    HAS_FASTEMBED = True
except ImportError:
    HAS_FASTEMBED = False


class EmbeddingCache:
    """SQLite cache for computed embeddings keyed by content hash."""

    def __init__(self, cache_path: str | Path):
        self._conn = sqlite3.connect(str(cache_path))
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS embedding_cache (
                content_hash TEXT PRIMARY KEY,
                vector TEXT NOT NULL,
                created_at INTEGER NOT NULL
            )
        """)
        self._conn.commit()

    def get(self, content_hash: str) -> list[float] | None:
        row = self._conn.execute(
            "SELECT vector FROM embedding_cache WHERE content_hash = ?",
            (content_hash,)
        ).fetchone()
        if row:
            return json.loads(row[0])
        return None

    def put(self, content_hash: str, vector: list[float]):
        self._conn.execute(
            "INSERT OR REPLACE INTO embedding_cache VALUES (?, ?, ?)",
            (content_hash, json.dumps(vector), int(time.time()))
        )
        self._conn.commit()

    def close(self):
        self._conn.close()


class EmbeddingModel:
    """Generates dense embeddings using local BGE-M3 or falls back to zero vectors."""

    def __init__(self, model_name: str = "BAAI/bge-m3", cache_path: str | Path | None = None):
        self.model_name = model_name
        self.cache = EmbeddingCache(cache_path) if cache_path else None
        self._model = None

        if HAS_FASTEMBED:
            try:
                self._model = TextEmbedding(model_name)
            except Exception:
                self._model = None

    def embed(self, text: str) -> list[float]:
        if not text.strip():
            return [0.0] * EMBEDDING_DIM

        content_hash = hashlib.sha256(text.encode()).hexdigest()

        if self.cache:
            cached = self.cache.get(content_hash)
            if cached is not None:
                return cached

        if self._model is not None:
            vectors = list(self._model.embed([text]))
            vector = vectors[0].tolist()
        else:
            vector = self._deterministic_fallback(text)

        if self.cache:
            self.cache.put(content_hash, vector)

        return vector

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return [self.embed(t) for t in texts]

    def _deterministic_fallback(self, text: str) -> list[float]:
        """Hash-based pseudo-embedding when no model is available.
        Not semantically meaningful but allows pipeline testing."""
        h = hashlib.sha256(text.encode()).digest()
        import struct
        values = []
        for i in range(0, EMBEDDING_DIM):
            byte_idx = i % len(h)
            values.append((h[byte_idx] - 128) / 128.0)
        return values

    def close(self):
        if self.cache:
            self.cache.close()
