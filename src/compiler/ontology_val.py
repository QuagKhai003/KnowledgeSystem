"""Ontology integrity validator: cycle detection, type checking, orphan detection."""

from .ontology import Ontology
from .schemas import KnowledgeObject


class OntologyValidationError:
    def __init__(self, object_id: str, rule: str, message: str):
        self.object_id = object_id
        self.rule = rule
        self.message = message

    def __repr__(self):
        return f"ValidationError({self.rule}: {self.object_id} - {self.message})"


class OntologyValidator:
    def __init__(self, ontology: Ontology | None = None):
        self.ontology = ontology or Ontology()

    def validate(self, objects: list[KnowledgeObject]) -> list[OntologyValidationError]:
        errors = []
        obj_map = {o.id: o for o in objects}

        for obj in objects:
            errors.extend(self._validate_class(obj))
            errors.extend(self._validate_predicates(obj, obj_map))

        errors.extend(self._detect_cycles(objects, obj_map))
        errors.extend(self._detect_orphans(objects, obj_map))

        return errors

    def _validate_class(self, obj: KnowledgeObject) -> list[OntologyValidationError]:
        if not obj.ontology_class:
            return []
        if not self.ontology.is_valid_class(obj.ontology_class):
            return [OntologyValidationError(
                obj.id, "invalid_class",
                f"Class '{obj.ontology_class}' is not in the ontology taxonomy"
            )]
        return []

    def _validate_predicates(self, obj: KnowledgeObject, obj_map: dict) -> list[OntologyValidationError]:
        errors = []
        for rel in obj.relationships:
            if not self.ontology.is_valid_predicate(rel.predicate):
                errors.append(OntologyValidationError(
                    obj.id, "invalid_predicate",
                    f"Predicate '{rel.predicate}' is not allowed"
                ))
                continue

            target_obj = obj_map.get(rel.target)
            if target_obj is None:
                continue

            if obj.ontology_class and target_obj.ontology_class:
                if not self.ontology.is_predicate_valid_for_types(
                    rel.predicate, obj.ontology_class, target_obj.ontology_class
                ):
                    errors.append(OntologyValidationError(
                        obj.id, "type_mismatch",
                        f"Predicate '{rel.predicate}' invalid between "
                        f"'{obj.ontology_class}' and '{target_obj.ontology_class}'"
                    ))
        return errors

    def _detect_cycles(self, objects: list[KnowledgeObject], obj_map: dict) -> list[OntologyValidationError]:
        """Detect circular is_a / part_of chains."""
        errors = []
        hierarchy_predicates = {"is_a", "part_of"}

        adj: dict[str, set[str]] = {}
        for obj in objects:
            for rel in obj.relationships:
                if rel.predicate in hierarchy_predicates:
                    adj.setdefault(obj.id, set()).add(rel.target)

        visited: set[str] = set()
        path: set[str] = set()

        def dfs(node_id: str) -> bool:
            if node_id in path:
                errors.append(OntologyValidationError(
                    node_id, "cycle_detected",
                    f"Circular taxonomy chain detected involving '{node_id}'"
                ))
                return True
            if node_id in visited:
                return False
            visited.add(node_id)
            path.add(node_id)
            for neighbor in adj.get(node_id, []):
                if dfs(neighbor):
                    return True
            path.discard(node_id)
            return False

        for obj_id in adj:
            if obj_id not in visited:
                dfs(obj_id)

        return errors

    def _detect_orphans(self, objects: list[KnowledgeObject], obj_map: dict) -> list[OntologyValidationError]:
        """Flag Implementation nodes with no parent concept link."""
        errors = []
        concept_linking_predicates = {"example_of", "is_a", "part_of"}

        for obj in objects:
            if obj.type != "implementation":
                continue
            has_concept_link = any(
                rel.predicate in concept_linking_predicates
                and obj_map.get(rel.target, None) is not None
                and obj_map[rel.target].type == "concept"
                for rel in obj.relationships
            )
            if not has_concept_link:
                errors.append(OntologyValidationError(
                    obj.id, "orphan_implementation",
                    "Implementation node has no link to a parent concept"
                ))
        return errors
