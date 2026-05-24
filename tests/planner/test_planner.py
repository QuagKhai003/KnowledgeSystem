import pytest

from src.planner.intent import IntentClassifier, QueryIntent
from src.planner.planner import QueryPlanner


class TestIntentClassifier:
    @pytest.fixture
    def classifier(self):
        return IntentClassifier()

    def test_definition_query(self, classifier):
        result = classifier.classify("What is path compression in Union Find?")
        assert result.intent == QueryIntent.DEFINITION

    def test_implementation_query(self, classifier):
        result = classifier.classify("Write a Python implementation of Kruskal's MST")
        assert result.intent == QueryIntent.IMPLEMENTATION

    def test_comparison_query(self, classifier):
        result = classifier.classify("Compare Kruskal vs Prim algorithm complexity")
        assert result.intent == QueryIntent.COMPARISON

    def test_research_query(self, classifier):
        result = classifier.classify("Explain the mathematical bounds of Disjoint Set Union")
        assert result.intent == QueryIntent.RESEARCH

    def test_navigation_query(self, classifier):
        result = classifier.classify("Where is the scanner module defined?")
        assert result.intent == QueryIntent.NAVIGATION

    def test_code_generation_keywords(self, classifier):
        result = classifier.classify("Generate a function to sort edges by weight")
        assert result.intent == QueryIntent.IMPLEMENTATION

    def test_ambiguous_defaults_to_definition(self, classifier):
        result = classifier.classify("hello")
        assert result.intent == QueryIntent.DEFINITION
        assert result.confidence < 0.5

    def test_confidence_increases_with_matches(self, classifier):
        weak = classifier.classify("code")
        strong = classifier.classify("Write a Python class implementation of code")
        assert strong.confidence >= weak.confidence

    def test_detect_exact_targets_pascal(self, classifier):
        targets = classifier.detect_exact_targets("How does UnionFind work?")
        assert "UnionFind" in targets

    def test_detect_exact_targets_snake(self, classifier):
        targets = classifier.detect_exact_targets("Find the knowledge_state module")
        assert "knowledge_state" in targets

    def test_detect_exact_targets_quoted(self, classifier):
        targets = classifier.detect_exact_targets('Search for `StateDB` class')
        assert "StateDB" in targets


class TestQueryPlanner:
    @pytest.fixture
    def planner(self):
        return QueryPlanner()

    def test_plan_returns_search_plan(self, planner):
        plan = planner.plan("What is Union Find?")
        assert plan.query == "What is Union Find?"
        assert plan.dense_vector is True

    def test_implementation_prioritizes_sparse(self, planner):
        plan = planner.plan("Write a Python function for BFS")
        assert plan.sparse_weight > plan.dense_weight

    def test_implementation_targets_l0(self, planner):
        plan = planner.plan("Implement binary search in Python")
        assert "level_0" in plan.target_abstractions

    def test_definition_targets_l2(self, planner):
        plan = planner.plan("What is the concept of memoization?")
        assert "level_2" in plan.target_abstractions

    def test_navigation_disables_dense(self, planner):
        plan = planner.plan("Where is the scanner defined?")
        assert plan.dense_vector is False

    def test_claude_model_gets_large_budget(self, planner):
        plan = planner.plan("Explain graphs", target_model="claude")
        assert plan.max_token_budget == 150000

    def test_gpt_model_gets_small_budget(self, planner):
        plan = planner.plan("Explain graphs", target_model="gpt")
        assert plan.max_token_budget == 8000

    def test_exact_matches_detected(self, planner):
        plan = planner.plan("How does UnionFind integrate with KruskalAlgorithm?")
        assert "UnionFind" in plan.force_exact_matches
        assert "KruskalAlgorithm" in plan.force_exact_matches

    def test_plan_with_metadata(self, planner):
        result = planner.plan_with_metadata("Implement sorting", target_model="codex")
        assert result["intent"] == "implementation_generation"
        assert result["target_model"] == "codex"
        assert "plan" in result
        assert result["plan"]["max_token_budget"] == 8000

    def test_research_uses_deep_hops(self, planner):
        plan = planner.plan("Research the formal complexity proof of path compression")
        assert plan.graph_max_hops == 3
