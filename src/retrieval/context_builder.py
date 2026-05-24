"""Context constructor: assembles retrieved results into token-budgeted context blocks."""

from dataclasses import dataclass, field
from .rerank import RankedResult


def _estimate_tokens(text: str) -> int:
    """Rough token estimate: ~4 chars per token for English."""
    return max(1, len(text) // 4)


@dataclass
class ContextBlock:
    id: str
    title: str
    content: str
    abstraction_level: int
    sources: list[str]
    tokens: int = 0

    def __post_init__(self):
        self.tokens = _estimate_tokens(self.content)


class ContextBuilder:
    """Assembles ranked results into a structured, token-budgeted context payload."""

    def __init__(self, knowledge_store: dict[str, dict] | None = None):
        self.knowledge_store = knowledge_store or {}

    def build(
        self,
        ranked_results: list[RankedResult],
        token_budget: int = 8000,
        target_levels: list[str] | None = None,
    ) -> list[ContextBlock]:
        if target_levels is None:
            target_levels = ["level_0", "level_1", "level_2"]

        blocks = []
        for result in ranked_results:
            ko = self.knowledge_store.get(result.id)
            if ko is None:
                ko = result.payload

            block = self._build_block(result, ko, target_levels)
            if block:
                blocks.append(block)

        blocks = self._fit_to_budget(blocks, token_budget)
        return blocks

    def _build_block(
        self,
        result: RankedResult,
        ko: dict,
        target_levels: list[str],
    ) -> ContextBlock | None:
        abstractions = ko.get("abstractions", {})
        content = ""
        level = 0

        for level_key in ["level_0", "level_1", "level_2", "level_3"]:
            if level_key in target_levels and abstractions.get(level_key):
                content = abstractions[level_key]
                level = int(level_key.split("_")[1])

        if not content:
            content = ko.get("content", ko.get("name", result.id))

        title = ko.get("name", result.id)

        return ContextBlock(
            id=result.id,
            title=title,
            content=content,
            abstraction_level=level,
            sources=result.sources,
        )

    def _fit_to_budget(self, blocks: list[ContextBlock], budget: int) -> list[ContextBlock]:
        total = sum(b.tokens for b in blocks)
        if total <= budget:
            return blocks

        blocks.sort(key=lambda b: b.tokens, reverse=True)

        for i, block in enumerate(blocks):
            if total <= budget:
                break
            if block.abstraction_level == 0:
                ko = self.knowledge_store.get(block.id, {})
                abstractions = ko.get("abstractions", {})
                l2 = abstractions.get("level_2", "")
                if l2:
                    old_tokens = block.tokens
                    block.content = l2
                    block.abstraction_level = 2
                    block.tokens = _estimate_tokens(l2)
                    total -= (old_tokens - block.tokens)

        # If still over budget, truncate from the end
        fitted = []
        used = 0
        for block in blocks:
            if used + block.tokens > budget:
                remaining = budget - used
                if remaining > 50:
                    block.content = block.content[:remaining * 4]
                    block.tokens = remaining
                    fitted.append(block)
                break
            fitted.append(block)
            used += block.tokens

        return fitted

    def format_context(self, blocks: list[ContextBlock], style: str = "markdown") -> str:
        if style == "xml":
            return self._format_xml(blocks)
        return self._format_markdown(blocks)

    def _format_markdown(self, blocks: list[ContextBlock]) -> str:
        parts = []
        for block in blocks:
            parts.append(f"### {block.title}")
            parts.append(f"*Sources: {', '.join(block.sources)} | Level {block.abstraction_level}*")
            parts.append("")
            parts.append(block.content)
            parts.append("")
        return "\n".join(parts)

    def _format_xml(self, blocks: list[ContextBlock]) -> str:
        parts = ["<context>"]
        for block in blocks:
            parts.append(f'  <document id="{block.id}" level="{block.abstraction_level}">')
            parts.append(f"    <title>{block.title}</title>")
            parts.append(f"    <content>{block.content}</content>")
            parts.append(f"    <sources>{', '.join(block.sources)}</sources>")
            parts.append("  </document>")
        parts.append("</context>")
        return "\n".join(parts)
