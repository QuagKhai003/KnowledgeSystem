"""Intent classifier: categorizes user queries into retrieval strategy types."""

import re
from dataclasses import dataclass
from enum import Enum


class QueryIntent(Enum):
    DEFINITION = "definition_theory"
    IMPLEMENTATION = "implementation_generation"
    COMPARISON = "comparison_synthesis"
    RESEARCH = "deep_research"
    NAVIGATION = "navigation_lookup"


INTENT_PATTERNS = {
    QueryIntent.IMPLEMENTATION: [
        r"\b(implement|write|code|build|create|generate|function|class|method)\b",
        r"\b(how to|show me|give me).*(code|implementation|example)\b",
        r"\b(python|javascript|typescript|java|rust)\b.*\b(code|class|function)\b",
    ],
    QueryIntent.DEFINITION: [
        r"\b(what is|define|explain|describe|meaning of)\b",
        r"\b(concept|theory|principle|definition)\b",
        r"\b(how does|how do).*(work|function|operate)\b",
    ],
    QueryIntent.COMPARISON: [
        r"\b(compare|versus|vs|difference|similarities|tradeoff)\b",
        r"\b(which is better|pros and cons|advantages)\b",
        r"\b(between|compared to)\b",
    ],
    QueryIntent.RESEARCH: [
        r"\b(research|paper|mathematical|proof|bounds|theorem)\b",
        r"\b(in-depth|comprehensive|detailed analysis)\b",
        r"\b(complexity|formal|rigorous)\b",
        r"\b(mathematical|theoretical)\b.*\b(bounds|analysis|proof)\b",
    ],
    QueryIntent.NAVIGATION: [
        r"\b(where is|locate|which file|path to)\b",
        r"\b(find the|find where|find me)\b",
        r"\b(imports|depends on|used by|references)\b",
    ],
}


@dataclass
class ClassifiedIntent:
    intent: QueryIntent
    confidence: float
    matched_patterns: list[str]


class IntentClassifier:
    """Rules-based intent classification for user queries."""

    def classify(self, query: str) -> ClassifiedIntent:
        scores: dict[QueryIntent, float] = {}
        matches: dict[QueryIntent, list[str]] = {}

        query_lower = query.lower()

        for intent, patterns in INTENT_PATTERNS.items():
            matched = []
            for pattern in patterns:
                if re.search(pattern, query_lower):
                    matched.append(pattern)
            if matched:
                scores[intent] = len(matched) / len(patterns)
                matches[intent] = matched

        if not scores:
            return ClassifiedIntent(
                intent=QueryIntent.DEFINITION,
                confidence=0.3,
                matched_patterns=[],
            )

        best_intent = max(scores, key=scores.get)
        confidence = min(scores[best_intent], 1.0)

        return ClassifiedIntent(
            intent=best_intent,
            confidence=confidence,
            matched_patterns=matches[best_intent],
        )

    def detect_exact_targets(self, query: str) -> list[str]:
        """Find PascalCase or snake_case identifiers that should be exact-matched."""
        pascal = re.findall(r"\b([A-Z][a-z]+(?:[A-Z][a-z]+)+)\b", query)
        snake = re.findall(r"\b([a-z]+_[a-z_]+)\b", query)
        quoted = re.findall(r'[`"\']([^`"\']+)[`"\']', query)
        return pascal + snake + quoted
