"""Multi-index retrieval coordinator: parallel fetch from dense, sparse, and graph."""

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field


@dataclass
class SearchPlan:
    query: str
    dense_vector: bool = True
    sparse_keyword: bool = True
    graph_traversal: bool = True
    dense_weight: float = 0.4
    sparse_weight: float = 0.4
    graph_weight: float = 0.2
    graph_max_hops: int = 2
    target_abstractions: list[str] = field(default_factory=lambda: ["level_0", "level_1", "level_2"])
    max_results: int = 10
    max_token_budget: int = 8000
    force_exact_matches: list[str] = field(default_factory=list)


@dataclass
class RetrievalResult:
    id: str
    source: str  # "dense", "sparse", "graph"
    rank: int
    score: float
    payload: dict = field(default_factory=dict)


class RetrievalCoordinator:
    """Executes parallel retrieval across multiple indexes."""

    def __init__(self, qdrant=None, opensearch=None, neo4j=None, embedder=None):
        self.qdrant = qdrant
        self.opensearch = opensearch
        self.neo4j = neo4j
        self.embedder = embedder

    def execute(self, plan: SearchPlan) -> dict[str, list[RetrievalResult]]:
        results: dict[str, list[RetrievalResult]] = {}
        futures = {}

        with ThreadPoolExecutor(max_workers=3) as pool:
            if plan.dense_vector and self.qdrant and self.embedder:
                futures["dense"] = pool.submit(
                    self._search_dense, plan.query, plan.max_results
                )
            if plan.sparse_keyword and self.opensearch:
                futures["sparse"] = pool.submit(
                    self._search_sparse, plan.query, plan.max_results
                )
            if plan.graph_traversal and self.neo4j:
                futures["graph"] = pool.submit(
                    self._search_graph, plan.query, plan.graph_max_hops
                )

            for source, future in futures.items():
                try:
                    results[source] = future.result(timeout=30)
                except Exception:
                    results[source] = []

        return results

    def _search_dense(self, query: str, limit: int) -> list[RetrievalResult]:
        query_vector = self.embedder.embed(query)
        hits = self.qdrant.search(query_vector, limit=limit)
        return [
            RetrievalResult(
                id=hit["id"],
                source="dense",
                rank=i + 1,
                score=hit["score"],
                payload=hit.get("payload", {}),
            )
            for i, hit in enumerate(hits)
        ]

    def _search_sparse(self, query: str, limit: int) -> list[RetrievalResult]:
        hits = self.opensearch.search(query, limit=limit)
        return [
            RetrievalResult(
                id=hit["id"],
                source="sparse",
                rank=i + 1,
                score=hit["score"],
                payload=hit.get("source", {}),
            )
            for i, hit in enumerate(hits)
        ]

    def _search_graph(self, query: str, max_hops: int) -> list[RetrievalResult]:
        concept_id = f"concept_{query.lower().replace(' ', '_')}"
        paths = self.neo4j.get_concept_context(concept_id, hops=max_hops)
        results = []
        for i, path in enumerate(paths):
            results.append(RetrievalResult(
                id=path.get("source", concept_id),
                source="graph",
                rank=i + 1,
                score=1.0 / (i + 1),
                payload=path,
            ))
        return results
