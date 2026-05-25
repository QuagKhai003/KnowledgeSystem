"""Qwen adapter: pointer output."""

from .base_adapter import BaseAdapter


class QwenAdapter(BaseAdapter):

    @property
    def model_name(self) -> str:
        return "qwen"
