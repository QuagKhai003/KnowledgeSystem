"""Qwen adapter: condensed JSON payload for maximum token density."""

import json
from src.retrieval.context_builder import ContextBlock
from .base_adapter import BaseAdapter


class QwenAdapter(BaseAdapter):

    @property
    def model_name(self) -> str:
        return "qwen"

    def format(self, blocks: list[ContextBlock], query: str, relationships: list[dict] | None = None) -> str:
        context_items = []

        for block in blocks:
            item = {
                "id": block.id,
                "name": block.title,
                "level": block.abstraction_level,
            }
            if block.abstraction_level == 0:
                item["code"] = block.content
            else:
                item["summary"] = block.content

            context_items.append(item)

        payload = {"query": query, "context": context_items}

        if relationships:
            payload["relationships"] = [
                {"src": r["source"], "tgt": r["target"], "rel": r["predicate"]}
                for r in relationships
            ]

        return json.dumps(payload, separators=(",", ":"))
