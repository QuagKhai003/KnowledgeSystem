"""Gemini adapter: structured Markdown with clear section boundaries and metadata."""

from src.retrieval.context_builder import ContextBlock
from .base_adapter import BaseAdapter


class GeminiAdapter(BaseAdapter):

    @property
    def model_name(self) -> str:
        return "gemini"

    def format(self, blocks: list[ContextBlock], query: str, relationships: list[dict] | None = None) -> str:
        parts = ["---", "# Knowledge Context", f"**Query:** {query}", "---", ""]

        if relationships:
            parts.append("## Relationships")
            parts.append("")
            parts.append("| Source | Predicate | Target |")
            parts.append("|--------|-----------|--------|")
            for rel in relationships:
                parts.append(f'| {rel["source"]} | {rel["predicate"]} | {rel["target"]} |')
            parts.append("")

        parts.append("## Retrieved Concepts")
        parts.append("")

        for block in blocks:
            parts.append(f"### {block.title}")
            parts.append(f"> Level {block.abstraction_level} | Sources: {', '.join(block.sources)}")
            parts.append("")

            if block.abstraction_level == 0:
                parts.append("```")
                parts.append(block.content)
                parts.append("```")
            else:
                parts.append(block.content)
            parts.append("")

        parts.append("---")
        return "\n".join(parts)
