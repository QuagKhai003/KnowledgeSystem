import pytest

from src.compiler.ontology import Ontology
from src.compiler.ontology_val import OntologyValidator
from src.compiler.schemas import KnowledgeObject, Relationship


@pytest.fixture
def ontology():
    return Ontology()


@pytest.fixture
def validator(ontology):
    return OntologyValidator(ontology)


class TestOntologyTaxonomy:
    def test_valid_classes(self, ontology):
        assert ontology.is_valid_class("Concept")
        assert ontology.is_valid_class("Algorithm")
        assert ontology.is_valid_class("Implementation")
        assert not ontology.is_valid_class("FakeClass")

    def test_parent_chain(self, ontology):
        assert ontology.get_parent_class("Algorithm") == "Concept"
        assert ontology.get_parent_class("Concept") == "KnowledgeObject"
        assert ontology.get_parent_class("KnowledgeObject") is None

    def test_base_type_resolution(self, ontology):
        assert ontology.get_base_type("Algorithm") == "Concept"
        assert ontology.get_base_type("DataStructure") == "Concept"
        assert ontology.get_base_type("Implementation") == "Implementation"
        assert ontology.get_base_type("Reference") == "Reference"

    def test_valid_predicates(self, ontology):
        assert ontology.is_valid_predicate("depends_on")
        assert ontology.is_valid_predicate("uses")
        assert not ontology.is_valid_predicate("created_by")

    def test_predicate_type_checking(self, ontology):
        # Concept -> Concept with depends_on: valid
        assert ontology.is_predicate_valid_for_types("depends_on", "Algorithm", "DataStructure")
        # Implementation -> Concept with example_of: valid
        assert ontology.is_predicate_valid_for_types("example_of", "Implementation", "Concept")
        # Concept -> Concept with example_of: invalid (source must be Implementation)
        assert not ontology.is_predicate_valid_for_types("example_of", "Algorithm", "Concept")


class TestOntologyValidator:
    def test_accepts_valid_objects(self, validator):
        objects = [
            KnowledgeObject(
                id="concept_union_find", type="concept", name="Union Find",
                ontology_class="DataStructure",
                relationships=[Relationship(target="concept_kruskal", predicate="uses")]
            ),
            KnowledgeObject(
                id="concept_kruskal", type="concept", name="Kruskal",
                ontology_class="Algorithm",
            ),
        ]
        errors = validator.validate(objects)
        assert len(errors) == 0

    def test_rejects_invalid_class(self, validator):
        objects = [
            KnowledgeObject(
                id="obj1", type="concept", name="Test",
                ontology_class="MadeUpClass",
            ),
        ]
        errors = validator.validate(objects)
        assert any(e.rule == "invalid_class" for e in errors)

    def test_rejects_invalid_predicate(self, validator):
        objects = [
            KnowledgeObject(
                id="obj1", type="concept", name="Test",
                ontology_class="Concept",
                relationships=[Relationship(target="obj2", predicate="invented_by")]
            ),
            KnowledgeObject(id="obj2", type="concept", name="Test2", ontology_class="Concept"),
        ]
        errors = validator.validate(objects)
        assert any(e.rule == "invalid_predicate" for e in errors)

    def test_detects_is_a_cycle(self, validator):
        objects = [
            KnowledgeObject(
                id="a", type="concept", name="A", ontology_class="Concept",
                relationships=[Relationship(target="b", predicate="is_a")]
            ),
            KnowledgeObject(
                id="b", type="concept", name="B", ontology_class="Concept",
                relationships=[Relationship(target="a", predicate="is_a")]
            ),
        ]
        errors = validator.validate(objects)
        assert any(e.rule == "cycle_detected" for e in errors)

    def test_detects_part_of_cycle(self, validator):
        objects = [
            KnowledgeObject(
                id="x", type="concept", name="X", ontology_class="Concept",
                relationships=[Relationship(target="y", predicate="part_of")]
            ),
            KnowledgeObject(
                id="y", type="concept", name="Y", ontology_class="Concept",
                relationships=[Relationship(target="z", predicate="part_of")]
            ),
            KnowledgeObject(
                id="z", type="concept", name="Z", ontology_class="Concept",
                relationships=[Relationship(target="x", predicate="part_of")]
            ),
        ]
        errors = validator.validate(objects)
        assert any(e.rule == "cycle_detected" for e in errors)

    def test_no_false_cycle_on_dag(self, validator):
        objects = [
            KnowledgeObject(
                id="a", type="concept", name="A", ontology_class="Concept",
                relationships=[Relationship(target="c", predicate="is_a")]
            ),
            KnowledgeObject(
                id="b", type="concept", name="B", ontology_class="Concept",
                relationships=[Relationship(target="c", predicate="is_a")]
            ),
            KnowledgeObject(id="c", type="concept", name="C", ontology_class="Concept"),
        ]
        errors = validator.validate(objects)
        assert not any(e.rule == "cycle_detected" for e in errors)

    def test_detects_orphan_implementation(self, validator):
        objects = [
            KnowledgeObject(
                id="file1.py", type="implementation", name="file1.py",
                ontology_class="Implementation",
                relationships=[],  # no link to any concept
            ),
        ]
        errors = validator.validate(objects)
        assert any(e.rule == "orphan_implementation" for e in errors)

    def test_linked_implementation_not_orphan(self, validator):
        objects = [
            KnowledgeObject(
                id="file1.py", type="implementation", name="file1.py",
                ontology_class="Implementation",
                relationships=[Relationship(target="concept_x", predicate="example_of")],
            ),
            KnowledgeObject(
                id="concept_x", type="concept", name="X", ontology_class="Concept",
            ),
        ]
        errors = validator.validate(objects)
        assert not any(e.rule == "orphan_implementation" for e in errors)

    def test_type_mismatch_error(self, validator):
        objects = [
            KnowledgeObject(
                id="impl1", type="concept", name="Algo", ontology_class="Algorithm",
                relationships=[Relationship(target="ref1", predicate="example_of")]
            ),
            KnowledgeObject(
                id="ref1", type="reference", name="Paper", ontology_class="Reference",
            ),
        ]
        errors = validator.validate(objects)
        assert any(e.rule == "type_mismatch" for e in errors)
