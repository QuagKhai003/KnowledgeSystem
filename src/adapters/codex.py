"""Codex adapter: minimal pointer output."""

from .base_adapter import BaseAdapter


class CodexAdapter(BaseAdapter):

    @property
    def model_name(self) -> str:
        return "codex"
