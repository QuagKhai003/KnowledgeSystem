"""Claude adapter: XML-structured pointer output."""

from .base_adapter import BaseAdapter


class ClaudeAdapter(BaseAdapter):

    @property
    def model_name(self) -> str:
        return "claude"
