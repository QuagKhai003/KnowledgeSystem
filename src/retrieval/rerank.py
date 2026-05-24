"""Reciprocal Rank Fusion (RRF) and cross-encoder reranking."""

from dataclasses import dataclass
from .coordinator import RetrievalResult


@dataclass
class RankedResult:
    id: str
    rrf_score: float
    sources: list[str]
    payload: dict


def rrf_merge(
    result_sets: dict[str, list[RetrievalResult]],
    weights: dict[str, float] | None = None,
    k: int = 60,
) -> list[RankedResult]:
    """Merge ranked results from multiple sources using Reciprocal Rank Fusion.

    RRF(d) = sum over sources m: weight_m / (k + rank_m(d))
    """
    if weights is None:
        weights = {source: 1.0 for source in result_sets}

    scores: dict[str, float] = {}
    sources_map: dict[str, list[str]] = {}
    payload_map: dict[str, dict] = {}

    for source, results in result_sets.items():
        w = weights.get(source, 1.0)
        for result in results:
            rrf_contribution = w / (k + result.rank)
            scores[result.id] = scores.get(result.id, 0.0) + rrf_contribution
            sources_map.setdefault(result.id, []).append(source)
            if result.id not in payload_map:
                payload_map[result.id] = result.payload

    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)

    return [
        RankedResult(
            id=doc_id,
            rrf_score=score,
            sources=sources_map.get(doc_id, []),
            payload=payload_map.get(doc_id, {}),
        )
        for doc_id, score in ranked
    ]


def cross_encoder_rerank(
    query: str,
    candidates: list[RankedResult],
    top_n: int = 10,
) -> list[RankedResult]:
    """Rerank using a cross-encoder model. Falls back to RRF order if unavailable."""
    try:
        from sentence_transformers import CrossEncoder
        model = CrossEncoder("BAAI/bge-reranker-base")
        pairs = [(query, c.payload.get("content", c.payload.get("name", c.id))) for c in candidates]
        scores = model.predict(pairs)

        for candidate, score in zip(candidates, scores):
            candidate.rrf_score = float(score)

        candidates.sort(key=lambda c: c.rrf_score, reverse=True)
    except (ImportError, Exception):
        pass

    return candidates[:top_n]
