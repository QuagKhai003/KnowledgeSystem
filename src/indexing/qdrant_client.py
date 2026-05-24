"""Qdrant vector database client for dense retrieval."""

from typing import Optional

try:
    from qdrant_client import QdrantClient as _QdrantClient
    from qdrant_client.models import (
        Distance, VectorParams, PointStruct,
        Filter, FieldCondition, MatchValue,
    )
    HAS_QDRANT = True
except ImportError:
    HAS_QDRANT = False

from .embeddings import EMBEDDING_DIM

COLLECTION_NAME = "knowledge_objects"


class QdrantIndex:
    """Manages Qdrant collection for dense vector search."""

    def __init__(self, host: str = "localhost", port: int = 6333):
        if not HAS_QDRANT:
            raise RuntimeError("qdrant-client package not installed")
        self._client = _QdrantClient(host=host, port=port)

    def init_collection(self):
        collections = [c.name for c in self._client.get_collections().collections]
        if COLLECTION_NAME not in collections:
            self._client.create_collection(
                collection_name=COLLECTION_NAME,
                vectors_config=VectorParams(
                    size=EMBEDDING_DIM,
                    distance=Distance.COSINE,
                ),
            )

    def upsert(self, point_id: str, vector: list[float], payload: dict):
        import uuid
        uid = uuid.uuid5(uuid.NAMESPACE_URL, point_id)
        self._client.upsert(
            collection_name=COLLECTION_NAME,
            points=[PointStruct(
                id=str(uid),
                vector=vector,
                payload={**payload, "knowledge_id": point_id},
            )],
        )

    def search(
        self,
        query_vector: list[float],
        limit: int = 10,
        domain_filter: str | None = None,
        type_filter: str | None = None,
    ) -> list[dict]:
        conditions = []
        if domain_filter:
            conditions.append(FieldCondition(key="domain", match=MatchValue(value=domain_filter)))
        if type_filter:
            conditions.append(FieldCondition(key="type", match=MatchValue(value=type_filter)))

        search_filter = Filter(must=conditions) if conditions else None

        results = self._client.query_points(
            collection_name=COLLECTION_NAME,
            query=query_vector,
            limit=limit,
            query_filter=search_filter,
        )

        return [
            {
                "id": hit.payload.get("knowledge_id", ""),
                "score": hit.score,
                "payload": hit.payload,
            }
            for hit in results.points
        ]

    def delete_by_id(self, point_id: str):
        import uuid
        uid = uuid.uuid5(uuid.NAMESPACE_URL, point_id)
        self._client.delete(
            collection_name=COLLECTION_NAME,
            points_selector=[str(uid)],
        )

    def close(self):
        self._client.close()
