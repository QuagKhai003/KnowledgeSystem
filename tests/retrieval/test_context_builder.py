import pytest

from src.retrieval.context_builder import ContextBuilder, ContextBlock, _estimate_tokens
from src.retrieval.rerank import RankedResult


def _make_ranked(id_: str, sources: list[str] = None) -> RankedResult:
    return RankedResult(
        id=id_,
        rrf_score=0.5,
        sources=sources or ["dense"],
        payload={"name": id_, "content": f"Content about {id_}"},
    )


class TestTokenEstimation:
    def test_rough_estimate(self):
        assert _estimate_tokens("hello world") > 0
        assert _estimate_tokens("a" * 400) == 100

    def test_empty_string(self):
        assert _estimate_tokens("") == 1


class TestContextBuilder:
    def test_builds_blocks_from_results(self):
        results = [_make_ranked("concept_a"), _make_ranked("concept_b")]
        builder = ContextBuilder()
        blocks = builder.build(results, token_budget=50000)
        assert len(blocks) == 2

    def test_uses_knowledge_store(self):
        store = {
            "concept_x": {
                "name": "Union Find",
                "abstractions": {
                    "level_0": "raw code...",
                    "level_1": "Class with find/union",
                    "level_2": "Disjoint set structure for partitioning",
                },
            }
        }
        results = [_make_ranked("concept_x")]
        builder = ContextBuilder(knowledge_store=store)
        blocks = builder.build(results, target_levels=["level_2"])
        assert "Disjoint set" in blocks[0].content

    def test_budget_truncation(self):
        long_content = "word " * 10000
        store = {
            "big": {
                "name": "Big",
                "abstractions": {"level_0": long_content},
            }
        }
        results = [_make_ranked("big")]
        builder = ContextBuilder(knowledge_store=store)
        blocks = builder.build(results, token_budget=500, target_levels=["level_0"])
        total_tokens = sum(b.tokens for b in blocks)
        assert total_tokens <= 500

    def test_downgrade_l0_to_l2(self):
        store = {
            "obj": {
                "name": "Obj",
                "abstractions": {
                    "level_0": "x " * 5000,
                    "level_2": "Short L2 summary",
                },
            }
        }
        results = [_make_ranked("obj")]
        builder = ContextBuilder(knowledge_store=store)
        blocks = builder.build(results, token_budget=100, target_levels=["level_0"])
        assert blocks[0].abstraction_level == 2
        assert "Short L2" in blocks[0].content

    def test_format_markdown(self):
        blocks = [ContextBlock(
            id="test", title="Test Title", content="Some content",
            abstraction_level=1, sources=["dense", "sparse"],
        )]
        builder = ContextBuilder()
        output = builder.format_context(blocks, style="markdown")
        assert "### Test Title" in output
        assert "dense" in output

    def test_format_xml(self):
        blocks = [ContextBlock(
            id="test", title="Test Title", content="Some content",
            abstraction_level=2, sources=["graph"],
        )]
        builder = ContextBuilder()
        output = builder.format_context(blocks, style="xml")
        assert "<context>" in output
        assert '<document id="test"' in output
        assert "<title>Test Title</title>" in output

    def test_empty_results(self):
        builder = ContextBuilder()
        blocks = builder.build([], token_budget=8000)
        assert blocks == []
