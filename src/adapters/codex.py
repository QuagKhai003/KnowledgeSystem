"""Codex adapter: raw code signatures, imports, and minimal comments."""

from src.retrieval.context_builder import ContextBlock
from .base_adapter import BaseAdapter


class CodexAdapter(BaseAdapter):

    @property
    def model_name(self) -> str:
        return "codex"

    def format(self, blocks: list[ContextBlock], query: str, relationships: list[dict] | None = None) -> str:
        parts = [f"# Query: {query}", ""]

        if relationships:
            deps = [rel["target"] for rel in relationships]
            parts.append(f"# Dependencies: {', '.join(deps)}")
            parts.append("")

        for block in blocks:
            parts.append(f"# {block.title}")
            if block.abstraction_level == 0:
                parts.append(block.content)
            elif block.abstraction_level == 1:
                parts.append(f"# {block.content}")
            else:
                parts.append(f"# Summary: {block.content}")
            parts.append("")

        return "\n".join(parts)
