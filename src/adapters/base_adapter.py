"""Base adapter interface for model-specific context formatting."""

from abc import ABC, abstractmethod
from src.retrieval.context_builder import ContextBlock


class BaseAdapter(ABC):
    """Abstract base for all model adapters."""

    @property
    @abstractmethod
    def model_name(self) -> str:
        ...

    @abstractmethod
    def format(self, blocks: list[ContextBlock], query: str, relationships: list[dict] | None = None) -> str:
        """Format context blocks into model-specific prompt context."""
        ...

    def estimate_tokens(self, text: str) -> int:
        return max(1, len(text) // 4)


def get_adapter(model: str) -> "BaseAdapter":
    from .claude import ClaudeAdapter
    from .gpt import GPTAdapter
    from .codex import CodexAdapter
    from .qwen import QwenAdapter
    from .gemini import GeminiAdapter

    adapters = {
        "claude": ClaudeAdapter(),
        "gpt": GPTAdapter(),
        "gpt5": GPTAdapter(),
        "codex": CodexAdapter(),
        "qwen": QwenAdapter(),
        "gemini": GeminiAdapter(),
    }
    return adapters.get(model.lower(), GPTAdapter())
