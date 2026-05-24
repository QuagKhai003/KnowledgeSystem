import pytest

from src.retrieval.coordinator import RetrievalResult
from src.retrieval.rerank import rrf_merge, RankedResult


def _make_results(source: str, ids: list[str]) -> list[RetrievalResult]:
    return [
        RetrievalResult(id=id_, source=source, rank=i + 1, score=1.0 / (i + 1))
        for i, id_ in enumerate(ids)
    ]


class TestRRFMerge:
    def test_single_source(self):
        results = {"dense": _make_results("dense", ["a", "b", "c"])}
        merged = rrf_merge(results, k=60)
        assert len(merged) == 3
        assert merged[0].id == "a"
        assert merged[0].rrf_score > merged[1].rrf_score

    def test_two_sources_boost_overlap(self):
        results = {
            "dense": _make_results("dense", ["a", "b", "c"]),
            "sparse": _make_results("sparse", ["b", "d", "a"]),
        }
        merged = rrf_merge(results, k=60)
        # "a" and "b" appear in both — should score higher
        top_ids = [m.id for m in merged[:2]]
        assert "a" in top_ids or "b" in top_ids

    def test_overlap_has_multiple_sources(self):
        results = {
            "dense": _make_results("dense", ["x", "y"]),
            "sparse": _make_results("sparse", ["y", "z"]),
        }
        merged = rrf_merge(results, k=60)
        y_result = next(m for m in merged if m.id == "y")
        assert "dense" in y_result.sources
        assert "sparse" in y_result.sources

    def test_weights_affect_ranking(self):
        results = {
            "dense": _make_results("dense", ["a"]),
            "sparse": _make_results("sparse", ["b"]),
        }
        # Heavy dense weight
        merged_dense = rrf_merge(results, weights={"dense": 10.0, "sparse": 1.0}, k=60)
        assert merged_dense[0].id == "a"

        # Heavy sparse weight
        merged_sparse = rrf_merge(results, weights={"dense": 1.0, "sparse": 10.0}, k=60)
        assert merged_sparse[0].id == "b"

    def test_k_parameter_affects_smoothing(self):
        results = {"dense": _make_results("dense", ["a", "b"])}
        merged_low_k = rrf_merge(results, k=1)
        merged_high_k = rrf_merge(results, k=100)

        # Lower k means rank 1 vs rank 2 gap is larger
        gap_low = merged_low_k[0].rrf_score - merged_low_k[1].rrf_score
        gap_high = merged_high_k[0].rrf_score - merged_high_k[1].rrf_score
        assert gap_low > gap_high

    def test_empty_sources(self):
        results = {"dense": [], "sparse": []}
        merged = rrf_merge(results, k=60)
        assert merged == []

    def test_three_source_fusion(self):
        results = {
            "dense": _make_results("dense", ["a", "b", "c"]),
            "sparse": _make_results("sparse", ["c", "a", "d"]),
            "graph": _make_results("graph", ["a", "e"]),
        }
        merged = rrf_merge(results, k=60)
        # "a" appears in all 3 sources — should rank highest
        assert merged[0].id == "a"
        assert len(merged[0].sources) == 3
