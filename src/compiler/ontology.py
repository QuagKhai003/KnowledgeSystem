"""Ontology definitions: taxonomy classes, allowed predicates, and depth rules."""

ONTOLOGY_CLASSES = {
    "KnowledgeObject": {"depth": None, "parent": None},
    "Concept": {"depth": None, "parent": "KnowledgeObject"},
    "Implementation": {"depth": None, "parent": "KnowledgeObject"},
    "Reference": {"depth": None, "parent": "KnowledgeObject"},
    "Algorithm": {"depth": 3, "parent": "Concept"},
    "DataStructure": {"depth": 3, "parent": "Concept"},
    "ArchitecturePattern": {"depth": 2, "parent": "Concept"},
    "MathematicalTheory": {"depth": 2, "parent": "Concept"},
    "Domain": {"depth": 0, "parent": "Concept"},
    "SubDomain": {"depth": 1, "parent": "Concept"},
}

ALLOWED_PREDICATES = {
    "is_a", "part_of", "depends_on", "example_of",
    "extends", "uses", "optimized_by",
}

PREDICATE_TYPE_RULES = {
    "is_a": {"source": {"Concept", "Implementation", "Reference"}, "target": {"Concept"}},
    "part_of": {"source": {"Concept"}, "target": {"Concept"}},
    "depends_on": {"source": {"Concept", "Implementation"}, "target": {"Concept", "Implementation"}},
    "example_of": {"source": {"Implementation"}, "target": {"Concept"}},
    "extends": {"source": {"Concept", "Implementation"}, "target": {"Concept", "Implementation"}},
    "uses": {"source": {"Concept", "Implementation"}, "target": {"Concept", "Implementation"}},
    "optimized_by": {"source": {"Concept"}, "target": {"Concept"}},
}


class Ontology:
    """Manages ontology taxonomy lookups."""

    def is_valid_class(self, cls: str) -> bool:
        return cls in ONTOLOGY_CLASSES

    def get_parent_class(self, cls: str) -> str | None:
        entry = ONTOLOGY_CLASSES.get(cls)
        return entry["parent"] if entry else None

    def get_depth(self, cls: str) -> int | None:
        entry = ONTOLOGY_CLASSES.get(cls)
        return entry["depth"] if entry else None

    def is_valid_predicate(self, predicate: str) -> bool:
        return predicate in ALLOWED_PREDICATES

    def get_base_type(self, cls: str) -> str | None:
        """Walk up the hierarchy to find the base type (Concept/Implementation/Reference)."""
        visited = set()
        current = cls
        while current and current != "KnowledgeObject":
            if current in visited:
                return None
            visited.add(current)
            if current in ("Concept", "Implementation", "Reference"):
                return current
            parent = self.get_parent_class(current)
            if parent is None:
                return None
            current = parent
        return None

    def is_predicate_valid_for_types(self, predicate: str, source_class: str, target_class: str) -> bool:
        rule = PREDICATE_TYPE_RULES.get(predicate)
        if rule is None:
            return False
        source_base = self.get_base_type(source_class) or source_class
        target_base = self.get_base_type(target_class) or target_class
        return source_base in rule["source"] and target_base in rule["target"]
