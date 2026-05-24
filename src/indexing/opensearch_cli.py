"""OpenSearch client for sparse BM25 keyword retrieval."""

try:
    from opensearchpy import OpenSearch
    HAS_OPENSEARCH = True
except ImportError:
    HAS_OPENSEARCH = False

INDEX_NAME = "knowledge_objects"

INDEX_MAPPINGS = {
    "mappings": {
        "properties": {
            "id": {"type": "keyword"},
            "type": {"type": "keyword"},
            "name": {
                "type": "text",
                "analyzer": "whitespace",
                "search_analyzer": "whitespace",
            },
            "content": {
                "type": "text",
                "analyzer": "english",
            },
            "tags": {"type": "keyword"},
            "file_path": {"type": "keyword"},
            "domain": {"type": "keyword"},
        }
    }
}


class OpenSearchIndex:
    """Manages OpenSearch index for BM25 sparse keyword search."""

    def __init__(self, host: str = "localhost", port: int = 9200):
        if not HAS_OPENSEARCH:
            raise RuntimeError("opensearch-py package not installed")
        self._client = OpenSearch(
            hosts=[{"host": host, "port": port}],
            use_ssl=False,
            verify_certs=False,
        )

    def init_index(self):
        if not self._client.indices.exists(INDEX_NAME):
            self._client.indices.create(index=INDEX_NAME, body=INDEX_MAPPINGS)

    def index_document(self, doc_id: str, document: dict):
        self._client.index(index=INDEX_NAME, id=doc_id, body=document)

    def search(self, query: str, limit: int = 10, filters: dict | None = None) -> list[dict]:
        must_clauses = [
            {
                "multi_match": {
                    "query": query,
                    "fields": ["name^3", "content", "tags^2"],
                    "type": "best_fields",
                }
            }
        ]
        if filters:
            for field, value in filters.items():
                must_clauses.append({"term": {field: value}})

        body = {
            "query": {"bool": {"must": must_clauses}},
            "size": limit,
        }

        response = self._client.search(index=INDEX_NAME, body=body)
        return [
            {
                "id": hit["_id"],
                "score": hit["_score"],
                "source": hit["_source"],
            }
            for hit in response["hits"]["hits"]
        ]

    def delete_document(self, doc_id: str):
        self._client.delete(index=INDEX_NAME, id=doc_id, ignore=[404])

    def close(self):
        self._client.close()
