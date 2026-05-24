import pytest

from src.indexing.manager import IndexManager
from src.indexing.embeddings import EmbeddingModel
from src.compiler.schemas import KnowledgeObject, Abstraction, Relationship


@pytest.fixture
def sample_ko():
    return KnowledgeObject(
        id="concept_union_find",
        type="concept",
        name="Union Find",
        domain="graph_algorithms",
        source_file="/path/to/union_find.md",
        abstractions=Abstraction(
            level_0="class UnionFind:\n    def find(self)...",
            level_1="Class UnionFind with methods find, union",
            level_2="Union Find is a disjoint set data structure with near-constant amortized operations.",
        ),
        ontology_class="DataStructure",
        tags=["algorithm", "data_structure"],
        relationships=[Relationship(target="concept_kruskal", predicate="uses")],
    )


class TestIndexManager:
    def test_build_embed_text_uses_level_2(self, sample_ko):
        manager = IndexManager()
        text = manager._build_embed_text(sample_ko)
        assert "Union Find" in text
        assert "disjoint set" in text

    def test_build_embed_text_falls_back_to_level_1(self):
        ko = KnowledgeObject(
            id="test", type="concept", name="Test",
            abstractions=Abstraction(level_1="L1 summary only"),
        )
        manager = IndexManager()
        text = manager._build_embed_text(ko)
        assert "L1 summary" in text

    def test_build_embed_text_falls_back_to_level_0(self):
        ko = KnowledgeObject(
            id="test", type="concept", name="Test",
            abstractions=Abstraction(level_0="Raw source code here"),
        )
        manager = IndexManager()
        text = manager._build_embed_text(ko)
        assert "Raw source code" in text

    def test_best_abstraction_level(self, sample_ko):
        manager = IndexManager()
        assert manager._best_abstraction_level(sample_ko) == 2

    def test_best_abstraction_level_1(self):
        ko = KnowledgeObject(
            id="test", type="concept", name="Test",
            abstractions=Abstraction(level_1="has L1"),
        )
        manager = IndexManager()
        assert manager._best_abstraction_level(ko) == 1

    def test_index_object_no_stores(self, sample_ko):
        manager = IndexManager()
        status = manager.index_object(sample_ko)
        assert status["qdrant"] is False
        assert status["opensearch"] is False
        assert status["neo4j"] is False

    def test_index_batch(self, sample_ko):
        manager = IndexManager()
        results = manager.index_batch([sample_ko, sample_ko])
        assert len(results) == 2
