"""Neo4j graph database client for Knowledge OS."""

from typing import Optional

try:
    from neo4j import GraphDatabase
    HAS_NEO4J = True
except ImportError:
    HAS_NEO4J = False

from src.compiler.schemas import KnowledgeObject

PREDICATE_TO_REL = {
    "is_a": "IS_A",
    "part_of": "PART_OF",
    "depends_on": "DEPENDS_ON",
    "example_of": "EXAMPLE_OF",
    "extends": "EXTENDS",
    "uses": "USES",
    "optimized_by": "OPTIMIZED_BY",
}


class Neo4jClient:
    """Manages node and relationship sync with Neo4j."""

    def __init__(self, uri: str, user: str, password: str):
        if not HAS_NEO4J:
            raise RuntimeError("neo4j package not installed")
        self._driver = GraphDatabase.driver(uri, auth=(user, password))

    def close(self):
        self._driver.close()

    def init_constraints(self):
        with self._driver.session() as session:
            session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (c:Concept) REQUIRE c.id IS UNIQUE")
            session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (f:File) REQUIRE f.id IS UNIQUE")
            session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (a:Abstraction) REQUIRE a.id IS UNIQUE")
            session.run("CREATE INDEX IF NOT EXISTS FOR (c:Concept) ON (c.name)")
            session.run("CREATE INDEX IF NOT EXISTS FOR (c:Concept) ON (c.domain)")

    def upsert_knowledge_object(self, obj: KnowledgeObject):
        label = self._label_for_type(obj.type)
        with self._driver.session() as session:
            session.run(
                f"MERGE (n:{label} {{id: $id}}) "
                "SET n.name = $name, n.domain = $domain, "
                "n.ontology_class = $ontology_class, n.depth = $depth, "
                "n.source_file = $source_file, "
                "n.level_1 = $level_1, n.level_2 = $level_2",
                id=obj.id,
                name=obj.name,
                domain=obj.domain,
                ontology_class=obj.ontology_class,
                depth=obj.ontology_depth,
                source_file=obj.source_file,
                level_1=obj.abstractions.level_1,
                level_2=obj.abstractions.level_2,
            )

    def upsert_relationship(self, source_id: str, target_id: str, predicate: str):
        rel_type = PREDICATE_TO_REL.get(predicate)
        if rel_type is None:
            return
        with self._driver.session() as session:
            session.run(
                f"MATCH (a {{id: $src}}) "
                f"MATCH (b {{id: $tgt}}) "
                f"MERGE (a)-[:{rel_type}]->(b)",
                src=source_id,
                tgt=target_id,
            )

    def sync_knowledge_object(self, obj: KnowledgeObject):
        self._purge_relationships(obj.id)
        self.upsert_knowledge_object(obj)
        for rel in obj.relationships:
            self._ensure_target_exists(rel.target)
            self.upsert_relationship(obj.id, rel.target, rel.predicate)

    def _purge_relationships(self, node_id: str):
        with self._driver.session() as session:
            session.run(
                "MATCH (n {id: $id})-[r]-() DELETE r",
                id=node_id,
            )

    def _ensure_target_exists(self, target_id: str):
        with self._driver.session() as session:
            session.run(
                "MERGE (n:Concept {id: $id})",
                id=target_id,
            )

    def delete_by_file(self, file_path: str):
        with self._driver.session() as session:
            session.run(
                "MATCH (n {source_file: $fp}) DETACH DELETE n",
                fp=file_path,
            )

    def get_concept_context(self, concept_id: str, hops: int = 2) -> list[dict]:
        hops = max(1, min(int(hops), 5))
        with self._driver.session() as session:
            result = session.run(
                "MATCH (c {id: $id}) "
                f"OPTIONAL MATCH path = (c)-[*1..{hops}]-(related) "
                "RETURN c.id AS source, c.name AS source_name, "
                "[n IN nodes(path) | {id: n.id, name: n.name}] AS path_nodes, "
                "[r IN relationships(path) | type(r)] AS path_rels",
                id=concept_id,
            )
            return [dict(record) for record in result]

    def _label_for_type(self, obj_type: str) -> str:
        return {
            "concept": "Concept",
            "implementation": "File",
            "reference": "Concept",
        }.get(obj_type, "Concept")
