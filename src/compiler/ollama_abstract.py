"""Local LLM abstraction generator via Ollama API."""

import json
import hashlib
import sqlite3
import time
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.error import URLError

DEFAULT_MODEL = "mistral:7b-instruct"
DEFAULT_OLLAMA_URL = "http://localhost:11434"

PROMPTS = {
    "level_1": (
        "You are a technical documentation engine. "
        "Produce a one-sentence outline of the following content. "
        "Focus on what it defines, its parameters, and its direct purpose.\n\n"
        "Content:\n{content}"
    ),
    "level_2": (
        "You are a knowledge engine. Summarize the following technical content "
        "into a single-paragraph high-density summary. Focus entirely on definitions, "
        "functions, time complexity, and core utility. "
        "Do not include introductory remarks or generic filler words.\n\n"
        "Content:\n{content}"
    ),
    "level_3": (
        "You are a domain analyst. Given the following technical concept summaries, "
        "write a one-paragraph overview that explains how these concepts relate within "
        "their domain. Focus on architectural role, dependencies, and practical applications.\n\n"
        "Summaries:\n{content}"
    ),
}


class AbstractionCache:
    """SQLite cache for LLM-generated abstractions keyed by content hash."""

    def __init__(self, cache_path: str | Path):
        self._conn = sqlite3.connect(str(cache_path))
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS abstraction_cache (
                content_hash TEXT NOT NULL,
                level TEXT NOT NULL,
                result TEXT NOT NULL,
                created_at INTEGER NOT NULL,
                PRIMARY KEY (content_hash, level)
            )
        """)
        self._conn.commit()

    def get(self, content_hash: str, level: str) -> str | None:
        row = self._conn.execute(
            "SELECT result FROM abstraction_cache WHERE content_hash = ? AND level = ?",
            (content_hash, level)
        ).fetchone()
        return row[0] if row else None

    def put(self, content_hash: str, level: str, result: str):
        self._conn.execute(
            "INSERT OR REPLACE INTO abstraction_cache VALUES (?, ?, ?, ?)",
            (content_hash, level, result, int(time.time()))
        )
        self._conn.commit()

    def close(self):
        self._conn.close()


class OllamaAbstractor:
    """Generates L1-L3 abstractions using a local Ollama model."""

    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        ollama_url: str = DEFAULT_OLLAMA_URL,
        cache_path: str | Path | None = None,
    ):
        self.model = model
        self.ollama_url = ollama_url.rstrip("/")
        self.cache = AbstractionCache(cache_path) if cache_path else None

    def _content_hash(self, content: str) -> str:
        return hashlib.sha256(content.encode()).hexdigest()

    def _call_ollama(self, prompt: str) -> str:
        payload = json.dumps({
            "model": self.model,
            "prompt": prompt,
            "stream": False,
        }).encode()

        req = Request(
            f"{self.ollama_url}/api/generate",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        with urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read())
            return data.get("response", "").strip()

    def generate(self, content: str, level: str) -> str:
        if not content.strip():
            return ""

        content_hash = self._content_hash(content)

        if self.cache:
            cached = self.cache.get(content_hash, level)
            if cached is not None:
                return cached

        prompt_template = PROMPTS.get(level)
        if prompt_template is None:
            return ""

        prompt = prompt_template.format(content=content[:4000])

        try:
            result = self._call_ollama(prompt)
        except (URLError, OSError, TimeoutError):
            return ""

        if self.cache and result:
            self.cache.put(content_hash, level, result)

        return result

    def generate_all_levels(self, content: str) -> dict[str, str]:
        l1 = self.generate(content, "level_1")
        l2 = self.generate(content, "level_2")
        return {
            "level_0": content,
            "level_1": l1,
            "level_2": l2,
            "level_3": "",  # generated at domain aggregation stage
        }

    def close(self):
        if self.cache:
            self.cache.close()
