import pytest
from src.indexing.embeddings import EmbeddingModel, EmbeddingCache, EMBEDDING_DIM


class TestEmbeddingCache:
    def test_put_and_get(self, tmp_path):
        cache = EmbeddingCache(tmp_path / "embed_cache.db")
        vector = [0.1] * EMBEDDING_DIM
        cache.put("hash1", vector)
        result = cache.get("hash1")
        assert result is not None
        assert len(result) == EMBEDDING_DIM
        assert abs(result[0] - 0.1) < 1e-6
        cache.close()

    def test_miss_returns_none(self, tmp_path):
        cache = EmbeddingCache(tmp_path / "embed_cache.db")
        assert cache.get("missing") is None
        cache.close()


class TestEmbeddingModel:
    def test_empty_text_returns_zeros(self):
        model = EmbeddingModel()
        vec = model.embed("")
        assert len(vec) == EMBEDDING_DIM
        assert all(v == 0.0 for v in vec)

    def test_fallback_produces_correct_dim(self):
        model = EmbeddingModel()
        vec = model.embed("Union Find data structure")
        assert len(vec) == EMBEDDING_DIM

    def test_deterministic_fallback(self):
        model = EmbeddingModel()
        v1 = model.embed("test content")
        v2 = model.embed("test content")
        assert v1 == v2

    def test_different_text_different_vectors(self):
        model = EmbeddingModel()
        v1 = model.embed("Kruskal algorithm")
        v2 = model.embed("Binary search tree")
        assert v1 != v2

    def test_uses_cache(self, tmp_path):
        model = EmbeddingModel(cache_path=tmp_path / "cache.db")
        v1 = model.embed("cached content")
        v2 = model.embed("cached content")
        assert v1 == v2
        model.close()

    def test_batch_embed(self):
        model = EmbeddingModel()
        texts = ["hello", "world", "test"]
        vectors = model.embed_batch(texts)
        assert len(vectors) == 3
        assert all(len(v) == EMBEDDING_DIM for v in vectors)
