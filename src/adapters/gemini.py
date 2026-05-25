"""Gemini adapter: pointer output."""

from .base_adapter import BaseAdapter


class GeminiAdapter(BaseAdapter):

    @property
    def model_name(self) -> str:
        return "gemini"
