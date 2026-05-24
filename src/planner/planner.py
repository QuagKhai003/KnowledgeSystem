"""Query Planner: builds Search Execution Plans from classified intent."""

from dataclasses import dataclass, field

from .intent import IntentClassifier, QueryIntent, ClassifiedIntent
from src.retrieval.coordinator import SearchPlan


INTENT_ROUTING = {
    QueryIntent.DEFINITION: {
        "dense_vector": True,
        "sparse_keyword": True,
        "graph_traversal": True,
        "dense_weight": 0.4,
        "sparse_weight": 0.3,
        "graph_weight": 0.3,
        "graph_max_hops": 1,
        "target_abstractions": ["level_2", "level_3"],
        "max_results": 8,
    },
    QueryIntent.IMPLEMENTATION: {
        "dense_vector": True,
        "sparse_keyword": True,
        "graph_traversal": True,
        "dense_weight": 0.3,
        "sparse_weight": 0.5,
        "graph_weight": 0.2,
        "graph_max_hops": 2,
        "target_abstractions": ["level_0", "level_1"],
        "max_results": 10,
    },
    QueryIntent.COMPARISON: {
        "dense_vector": True,
        "sparse_keyword": True,
        "graph_traversal": True,
        "dense_weight": 0.4,
        "sparse_weight": 0.2,
        "graph_weight": 0.4,
        "graph_max_hops": 2,
        "target_abstractions": ["level_2"],
        "max_results": 12,
    },
    QueryIntent.RESEARCH: {
        "dense_vector": True,
        "sparse_keyword": True,
        "graph_traversal": True,
        "dense_weight": 0.5,
        "sparse_weight": 0.2,
        "graph_weight": 0.3,
        "graph_max_hops": 3,
        "target_abstractions": ["level_2", "level_3"],
        "max_results": 15,
    },
    QueryIntent.NAVIGATION: {
        "dense_vector": False,
        "sparse_keyword": True,
        "graph_traversal": True,
        "dense_weight": 0.0,
        "sparse_weight": 0.6,
        "graph_weight": 0.4,
        "graph_max_hops": 3,
        "target_abstractions": ["level_1"],
        "max_results": 10,
    },
}

TOKEN_BUDGETS = {
    "claude": 150000,
    "gpt": 8000,
    "gpt5": 128000,
    "codex": 8000,
    "qwen": 32000,
    "gemini": 128000,
    "default": 8000,
}


class QueryPlanner:
    """Builds optimized Search Execution Plans from user queries."""

    def __init__(self, classifier: IntentClassifier | None = None):
        self.classifier = classifier or IntentClassifier()

    def plan(self, query: str, target_model: str = "default") -> SearchPlan:
        classified = self.classifier.classify(query)
        exact_targets = self.classifier.detect_exact_targets(query)
        routing = INTENT_ROUTING[classified.intent]
        budget = TOKEN_BUDGETS.get(target_model, TOKEN_BUDGETS["default"])

        return SearchPlan(
            query=query,
            dense_vector=routing["dense_vector"],
            sparse_keyword=routing["sparse_keyword"],
            graph_traversal=routing["graph_traversal"],
            dense_weight=routing["dense_weight"],
            sparse_weight=routing["sparse_weight"],
            graph_weight=routing.get("graph_weight", 0.2),
            graph_max_hops=routing["graph_max_hops"],
            target_abstractions=routing["target_abstractions"],
            max_results=routing["max_results"],
            max_token_budget=budget,
            force_exact_matches=exact_targets,
        )

    def plan_with_metadata(self, query: str, target_model: str = "default") -> dict:
        classified = self.classifier.classify(query)
        search_plan = self.plan(query, target_model)
        return {
            "query": query,
            "intent": classified.intent.value,
            "confidence": classified.confidence,
            "target_model": target_model,
            "plan": {
                "dense_vector": search_plan.dense_vector,
                "sparse_keyword": search_plan.sparse_keyword,
                "graph_traversal": search_plan.graph_traversal,
                "weights": {
                    "dense": search_plan.dense_weight,
                    "sparse": search_plan.sparse_weight,
                },
                "graph_max_hops": search_plan.graph_max_hops,
                "target_abstractions": search_plan.target_abstractions,
                "max_results": search_plan.max_results,
                "max_token_budget": search_plan.max_token_budget,
                "force_exact_matches": search_plan.force_exact_matches,
            },
        }
