import pytest

from src.compiler.ollama_abstract import AbstractionCache, OllamaAbstractor


class TestAbstractionCache:
    def test_put_and_get(self, tmp_path):
        cache = AbstractionCache(tmp_path / "cache.db")
        cache.put("hash123", "level_1", "Test summary")
        assert cache.get("hash123", "level_1") == "Test summary"
        cache.close()

    def test_miss_returns_none(self, tmp_path):
        cache = AbstractionCache(tmp_path / "cache.db")
        assert cache.get("nonexistent", "level_1") is None
        cache.close()

    def test_overwrite_updates_value(self, tmp_path):
        cache = AbstractionCache(tmp_path / "cache.db")
        cache.put("hash1", "level_2", "Old summary")
        cache.put("hash1", "level_2", "New summary")
        assert cache.get("hash1", "level_2") == "New summary"
        cache.close()

    def test_different_levels_independent(self, tmp_path):
        cache = AbstractionCache(tmp_path / "cache.db")
        cache.put("hash1", "level_1", "L1 summary")
        cache.put("hash1", "level_2", "L2 summary")
        assert cache.get("hash1", "level_1") == "L1 summary"
        assert cache.get("hash1", "level_2") == "L2 summary"
        cache.close()


class TestOllamaAbstractor:
    def test_empty_content_returns_empty(self, tmp_path):
        abstractor = OllamaAbstractor(cache_path=tmp_path / "cache.db")
        assert abstractor.generate("", "level_1") == ""
        assert abstractor.generate("   ", "level_1") == ""
        abstractor.close()

    def test_invalid_level_returns_empty(self, tmp_path):
        abstractor = OllamaAbstractor(cache_path=tmp_path / "cache.db")
        assert abstractor.generate("some content", "level_99") == ""
        abstractor.close()

    def test_uses_cache_when_available(self, tmp_path):
        cache_path = tmp_path / "cache.db"
        cache = AbstractionCache(cache_path)
        content = "Union Find is a data structure"
        import hashlib
        h = hashlib.sha256(content.encode()).hexdigest()
        cache.put(h, "level_1", "Cached L1 result")
        cache.close()

        abstractor = OllamaAbstractor(cache_path=cache_path)
        result = abstractor.generate(content, "level_1")
        assert result == "Cached L1 result"
        abstractor.close()

    def test_graceful_ollama_unavailable(self, tmp_path):
        abstractor = OllamaAbstractor(
            ollama_url="http://localhost:99999",
            cache_path=tmp_path / "cache.db"
        )
        result = abstractor.generate("Some content here", "level_2")
        assert result == ""
        abstractor.close()

    def test_generate_all_levels_structure(self, tmp_path):
        cache_path = tmp_path / "cache.db"
        cache = AbstractionCache(cache_path)
        content = "Test content for all levels"
        import hashlib
        h = hashlib.sha256(content.encode()).hexdigest()
        cache.put(h, "level_1", "L1 result")
        cache.put(h, "level_2", "L2 result")
        cache.close()

        abstractor = OllamaAbstractor(cache_path=cache_path)
        result = abstractor.generate_all_levels(content)
        assert result["level_0"] == content
        assert result["level_1"] == "L1 result"
        assert result["level_2"] == "L2 result"
        assert result["level_3"] == ""
        abstractor.close()
