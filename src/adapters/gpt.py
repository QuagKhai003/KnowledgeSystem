"""GPT adapter: dense Markdown with headers, bullets, and code blocks."""

from src.retrieval.context_builder import ContextBlock
from .base_adapter import BaseAdapter


class GPTAdapter(BaseAdapter):

    @property
    def model_name(self) -> str:
        return "gpt"

    def format(self, blocks: list[ContextBlock], query: str, relationships: list[dict] | None = None) -> str:
        parts = ["# KNOWLEDGE CONTEXT", ""]

        if relationships:
            parts.append("## ONTOLOGY RELATIONSHIPS")
            for rel in relationships:
                parts.append(
                    f'* **{rel["source"]}** ──{rel["predicate"]}──> **{rel["target"]}**'
                )
            parts.append("")

        parts.append("## COMPILED CONCEPTS")
        parts.append("")

        for block in blocks:
            parts.append(f"### {block.title}")
            parts.append(f"*Level {block.abstraction_level} | Sources: {', '.join(block.sources)}*")
            parts.append("")

            if block.abstraction_level == 0:
                parts.append("```")
                parts.append(block.content)
                parts.append("```")
            else:
                parts.append(block.content)
            parts.append("")

        return "\n".join(parts)
