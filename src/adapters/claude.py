"""Claude adapter: XML-structured context with semantic tags."""

from src.retrieval.context_builder import ContextBlock
from .base_adapter import BaseAdapter


class ClaudeAdapter(BaseAdapter):

    @property
    def model_name(self) -> str:
        return "claude"

    def format(self, blocks: list[ContextBlock], query: str, relationships: list[dict] | None = None) -> str:
        parts = ["<knowledge_context>"]

        if relationships:
            parts.append("  <ontology_hierarchy>")
            for rel in relationships:
                parts.append(
                    f'    <relation source="{rel["source"]}" '
                    f'target="{rel["target"]}" type="{rel["predicate"]}"/>'
                )
            parts.append("  </ontology_hierarchy>")

        parts.append("  <concepts>")
        for block in blocks:
            parts.append(f'    <concept id="{block.id}" level="{block.abstraction_level}">')
            parts.append(f"      <name>{block.title}</name>")

            if block.abstraction_level == 0:
                parts.append("      <implementation>")
                parts.append(f"        <![CDATA[{block.content}]]>")
                parts.append("      </implementation>")
            elif block.abstraction_level <= 2:
                parts.append(f"      <summary>{block.content}</summary>")
            else:
                parts.append(f"      <domain_context>{block.content}</domain_context>")

            parts.append("    </concept>")
        parts.append("  </concepts>")
        parts.append("</knowledge_context>")

        return "\n".join(parts)
