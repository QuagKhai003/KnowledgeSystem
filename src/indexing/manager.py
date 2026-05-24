"""Index Manager: coordinates writes across Qdrant, OpenSearch, and Neo4j."""

from src.compiler.schemas import KnowledgeObject
from .embeddings import EmbeddingModel


class IndexManager:
    """Orchestrates indexing a Knowledge Object across all storage engines."""

    def __init__(
        self,
        embedding_model: EmbeddingModel | None = None,
        qdrant=None,
        opensearch=None,
        neo4j=None,
        config: dict | None = None,
    ):
        self.embedder = embedding_model
        self.qdrant = qdrant
        self.opensearch = opensearch
        self.neo4j = neo4j

        if config and not any([qdrant, opensearch, neo4j]):
            self._connect_from_config(config)

    def _connect_from_config(self, config: dict):
        from .qdrant_client import QdrantIndex
        from .opensearch_cli import OpenSearchIndex
        from .neo4j_client import Neo4jClient

        db = config.get("databases", {})
        try:
            q = db["qdrant"]
            self.qdrant = QdrantIndex(host=q["host"], port=q["port"])
        except Exception:
            pass
        try:
            o = db["opensearch"]
            self.opensearch = OpenSearchIndex(host=o["host"], port=o["port"])
        except Exception:
            pass
        try:
            n = db["neo4j"]
            self.neo4j = Neo4jClient(uri=n["uri"], user=n["user"], password=n["password"])
        except Exception:
            pass
        if not self.embedder:
            self.embedder = EmbeddingModel()

    def index_object(self, obj: KnowledgeObject) -> dict:
        """Index a single Knowledge Object across all available stores.
        Returns a status dict indicating which stores succeeded."""
        status = {"qdrant": False, "opensearch": False, "neo4j": False}

        embed_text = self._build_embed_text(obj)

        if self.qdrant and self.embedder:
            try:
                vector = self.embedder.embed(embed_text)
                payload = {
                    "type": obj.type,
                    "name": obj.name,
                    "domain": obj.domain,
                    "tags": obj.tags,
                    "file_path": obj.source_file,
                    "abstraction_level": self._best_abstraction_level(obj),
                }
                self.qdrant.upsert(obj.id, vector, payload)
                status["qdrant"] = True
            except Exception:
                pass

        if self.opensearch:
            try:
                doc = {
                    "id": obj.id,
                    "type": obj.type,
                    "name": obj.name,
                    "content": embed_text,
                    "tags": obj.tags,
                    "file_path": obj.source_file,
                    "domain": obj.domain,
                }
                self.opensearch.index_document(obj.id, doc)
                status["opensearch"] = True
            except Exception:
                pass

        if self.neo4j:
            try:
                self.neo4j.sync_knowledge_object(obj)
                status["neo4j"] = True
            except Exception:
                pass

        return status

    def index_batch(self, objects: list[KnowledgeObject]) -> list[dict]:
        return [self.index_object(obj) for obj in objects]

    def delete_object(self, obj_id: str):
        if self.qdrant:
            try:
                self.qdrant.delete_by_id(obj_id)
            except Exception:
                pass
        if self.opensearch:
            try:
                self.opensearch.delete_document(obj_id)
            except Exception:
                pass
        if self.neo4j:
            try:
                self.neo4j.delete_by_file(obj_id)
            except Exception:
                pass

    def _build_embed_text(self, obj: KnowledgeObject) -> str:
        parts = [obj.name]
        if obj.abstractions.level_2:
            parts.append(obj.abstractions.level_2)
        elif obj.abstractions.level_1:
            parts.append(obj.abstractions.level_1)
        elif obj.abstractions.level_0:
            parts.append(obj.abstractions.level_0[:2000])
        if obj.tags:
            parts.append(" ".join(obj.tags))
        return " | ".join(parts)

    def _best_abstraction_level(self, obj: KnowledgeObject) -> int:
        if obj.abstractions.level_2:
            return 2
        if obj.abstractions.level_1:
            return 1
        return 0
