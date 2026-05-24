import json
import pytest

from src.retrieval.context_builder import ContextBlock
from src.adapters import get_adapter, ClaudeAdapter, GPTAdapter, CodexAdapter, QwenAdapter, GeminiAdapter


@pytest.fixture
def sample_blocks():
    return [
        ContextBlock(
            id="concept_union_find",
            title="Union Find",
            content="Union Find is a disjoint-set data structure with near-constant amortized operations.",
            abstraction_level=2,
            sources=["dense", "sparse"],
        ),
        ContextBlock(
            id="concept_kruskal",
            title="Kruskal's Algorithm",
            content="class Kruskal:\n    def find_mst(self, edges):\n        ...",
            abstraction_level=0,
            sources=["sparse"],
        ),
    ]


@pytest.fixture
def sample_relationships():
    return [
        {"source": "concept_union_find", "target": "concept_kruskal", "predicate": "used_by"},
        {"source": "concept_kruskal", "target": "concept_spanning_tree", "predicate": "is_a"},
    ]


class TestClaudeAdapter:
    def test_output_is_xml(self, sample_blocks, sample_relationships):
        adapter = ClaudeAdapter()
        output = adapter.format(sample_blocks, "test query", sample_relationships)
        assert "<knowledge_context>" in output
        assert "</knowledge_context>" in output

    def test_contains_concept_tags(self, sample_blocks):
        adapter = ClaudeAdapter()
        output = adapter.format(sample_blocks, "test query")
        assert '<concept id="concept_union_find"' in output
        assert "<name>Union Find</name>" in output

    def test_l2_uses_summary_tag(self, sample_blocks):
        adapter = ClaudeAdapter()
        output = adapter.format(sample_blocks, "test query")
        assert "<summary>" in output
        assert "disjoint-set" in output

    def test_l0_uses_cdata(self, sample_blocks):
        adapter = ClaudeAdapter()
        output = adapter.format(sample_blocks, "test query")
        assert "<![CDATA[" in output

    def test_relationships_in_ontology_block(self, sample_blocks, sample_relationships):
        adapter = ClaudeAdapter()
        output = adapter.format(sample_blocks, "test query", sample_relationships)
        assert "<ontology_hierarchy>" in output
        assert 'type="used_by"' in output


class TestGPTAdapter:
    def test_output_is_markdown(self, sample_blocks, sample_relationships):
        adapter = GPTAdapter()
        output = adapter.format(sample_blocks, "test query", sample_relationships)
        assert "# KNOWLEDGE CONTEXT" in output

    def test_contains_headers(self, sample_blocks):
        adapter = GPTAdapter()
        output = adapter.format(sample_blocks, "test query")
        assert "### Union Find" in output
        assert "### Kruskal" in output

    def test_l0_in_code_block(self, sample_blocks):
        adapter = GPTAdapter()
        output = adapter.format(sample_blocks, "test query")
        assert "```" in output

    def test_relationships_as_bullets(self, sample_blocks, sample_relationships):
        adapter = GPTAdapter()
        output = adapter.format(sample_blocks, "test query", sample_relationships)
        assert "## ONTOLOGY RELATIONSHIPS" in output
        assert "used_by" in output


class TestCodexAdapter:
    def test_minimal_format(self, sample_blocks):
        adapter = CodexAdapter()
        output = adapter.format(sample_blocks, "implement union find")
        assert "# Query: implement union find" in output

    def test_l0_raw_code(self, sample_blocks):
        adapter = CodexAdapter()
        output = adapter.format(sample_blocks, "test")
        assert "class Kruskal:" in output

    def test_l2_as_comment(self, sample_blocks):
        adapter = CodexAdapter()
        output = adapter.format(sample_blocks, "test")
        assert "# Summary:" in output

    def test_dependencies_listed(self, sample_blocks, sample_relationships):
        adapter = CodexAdapter()
        output = adapter.format(sample_blocks, "test", sample_relationships)
        assert "# Dependencies:" in output
        assert "concept_kruskal" in output


class TestQwenAdapter:
    def test_output_is_valid_json(self, sample_blocks, sample_relationships):
        adapter = QwenAdapter()
        output = adapter.format(sample_blocks, "test query", sample_relationships)
        data = json.loads(output)
        assert "context" in data
        assert "query" in data

    def test_context_items(self, sample_blocks):
        adapter = QwenAdapter()
        output = adapter.format(sample_blocks, "test")
        data = json.loads(output)
        assert len(data["context"]) == 2
        assert data["context"][0]["name"] == "Union Find"

    def test_l0_has_code_key(self, sample_blocks):
        adapter = QwenAdapter()
        output = adapter.format(sample_blocks, "test")
        data = json.loads(output)
        kruskal = next(c for c in data["context"] if c["name"] == "Kruskal's Algorithm")
        assert "code" in kruskal

    def test_l2_has_summary_key(self, sample_blocks):
        adapter = QwenAdapter()
        output = adapter.format(sample_blocks, "test")
        data = json.loads(output)
        uf = next(c for c in data["context"] if c["name"] == "Union Find")
        assert "summary" in uf

    def test_relationships_included(self, sample_blocks, sample_relationships):
        adapter = QwenAdapter()
        output = adapter.format(sample_blocks, "test", sample_relationships)
        data = json.loads(output)
        assert "relationships" in data
        assert data["relationships"][0]["rel"] == "used_by"


class TestGeminiAdapter:
    def test_output_has_frontmatter(self, sample_blocks, sample_relationships):
        adapter = GeminiAdapter()
        output = adapter.format(sample_blocks, "test query", sample_relationships)
        assert "---" in output
        assert "# Knowledge Context" in output

    def test_query_in_header(self, sample_blocks):
        adapter = GeminiAdapter()
        output = adapter.format(sample_blocks, "my question")
        assert "**Query:** my question" in output

    def test_relationships_as_table(self, sample_blocks, sample_relationships):
        adapter = GeminiAdapter()
        output = adapter.format(sample_blocks, "test", sample_relationships)
        assert "| Source | Predicate | Target |" in output
        assert "used_by" in output

    def test_l0_in_code_block(self, sample_blocks):
        adapter = GeminiAdapter()
        output = adapter.format(sample_blocks, "test")
        assert "```" in output
        assert "class Kruskal:" in output

    def test_l2_as_plain_text(self, sample_blocks):
        adapter = GeminiAdapter()
        output = adapter.format(sample_blocks, "test")
        assert "disjoint-set" in output

    def test_blockquote_metadata(self, sample_blocks):
        adapter = GeminiAdapter()
        output = adapter.format(sample_blocks, "test")
        assert "> Level 2" in output


class TestGetAdapter:
    def test_returns_claude(self):
        assert isinstance(get_adapter("claude"), ClaudeAdapter)

    def test_returns_gpt(self):
        assert isinstance(get_adapter("gpt"), GPTAdapter)

    def test_returns_codex(self):
        assert isinstance(get_adapter("codex"), CodexAdapter)

    def test_returns_qwen(self):
        assert isinstance(get_adapter("qwen"), QwenAdapter)

    def test_returns_gemini(self):
        assert isinstance(get_adapter("gemini"), GeminiAdapter)

    def test_unknown_defaults_to_gpt(self):
        assert isinstance(get_adapter("unknown_model"), GPTAdapter)

    def test_case_insensitive(self):
        assert isinstance(get_adapter("CLAUDE"), ClaudeAdapter)
