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

    def format_pointers(self, pointers: list[dict], query: str) -> str:
        """Format file pointers for AI CLI consumption."""
        if not pointers:
            return "No relevant documents found for this query."

        parts = [f"# Search Results for: {query}", ""]
        parts.append("The following files contain relevant information. Read the files to answer the query.")
        parts.append("")

        for i, p in enumerate(pointers, 1):
            parts.append(f"## {i}. {p['name']}")
            parts.append(f"**File:** `{p['file']}`")
            parts.append(f"**Relevance:** {p['score']}")
            if p.get("why"):
                parts.append(f"**Matched terms:** {p['why']}")
            if p.get("sections"):
                parts.append(f"**Sections:** {'; '.join(p['sections'])}")
            if p.get("domain"):
                parts.append(f"**Domain:** {p['domain']}")
            parts.append("")

        return "\n".join(parts)

    def estimate_tokens(self, text: str) -> int:
        return max(1, len(text) // 4)


def detect_cli() -> str:
    """Detect which AI CLI is currently running based on environment."""
    import os

    # Claude Code sets CLAUDE_CODE or runs as 'claude'
    if os.environ.get("CLAUDE_CODE") or os.environ.get("CLAUDE_ACCESS_TOKEN"):
        return "claude"

    # OpenAI Codex CLI
    if os.environ.get("CODEX_CLI") or os.environ.get("OPENAI_API_KEY"):
        return "codex"

    # Google Gemini / Antigravity
    if os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY"):
        return "gemini"

    # Qwen
    if os.environ.get("DASHSCOPE_API_KEY"):
        return "qwen"

    # Check parent process name as fallback
    try:
        import psutil
        parent = psutil.Process(os.getppid()).name().lower()
        if "claude" in parent:
            return "claude"
        if "cursor" in parent or "windsurf" in parent:
            return "claude"
        if "codex" in parent:
            return "codex"
    except Exception:
        pass

    # Check if running inside an MCP call (set by mcp_server.py)
    mcp_model = os.environ.get("KOS_MCP_MODEL")
    if mcp_model:
        return mcp_model

    return "default"


def get_adapter(model: str) -> "BaseAdapter":
    if model == "default" or model == "auto":
        model = detect_cli()

    model = model.lower()

    if model == "claude":
        from .claude import ClaudeAdapter
        return ClaudeAdapter()
    elif model == "codex":
        from .codex import CodexAdapter
        return CodexAdapter()
    elif model == "qwen":
        from .qwen import QwenAdapter
        return QwenAdapter()
    elif model == "gemini":
        from .gemini import GeminiAdapter
        return GeminiAdapter()
    else:
        from .gpt import GPTAdapter
        return GPTAdapter()
