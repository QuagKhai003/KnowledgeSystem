"""GPT adapter: Markdown pointer output."""

from .base_adapter import BaseAdapter


class GPTAdapter(BaseAdapter):

    @property
    def model_name(self) -> str:
        return "gpt"
