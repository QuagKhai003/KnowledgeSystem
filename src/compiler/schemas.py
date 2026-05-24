from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Abstraction:
    level_0: str = ""
    level_1: str = ""
    level_2: str = ""
    level_3: str = ""


@dataclass
class Relationship:
    target: str
    predicate: str


@dataclass
class KnowledgeObject:
    id: str
    type: str  # "concept", "implementation", "reference"
    name: str
    domain: str = ""
    source_file: str = ""
    abstractions: Abstraction = field(default_factory=Abstraction)
    ontology_class: str = ""
    ontology_depth: int = 3
    relationships: list[Relationship] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "type": self.type,
            "name": self.name,
            "domain": self.domain,
            "source_file": self.source_file,
            "abstractions": {
                "level_0": self.abstractions.level_0,
                "level_1": self.abstractions.level_1,
                "level_2": self.abstractions.level_2,
                "level_3": self.abstractions.level_3,
            },
            "ontology": {
                "class": self.ontology_class,
                "depth": self.ontology_depth,
            },
            "relationships": [
                {"target": r.target, "predicate": r.predicate}
                for r in self.relationships
            ],
            "tags": self.tags,
        }
