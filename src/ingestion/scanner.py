import hashlib
import os
from fnmatch import fnmatch
from pathlib import Path
from typing import Generator

from .state_db import StateDB

SPECIALIZED_PARSERS = {
    ".md": "markdown",
    ".py": "code",
    ".js": "code",
    ".ts": "code",
    ".jsx": "code",
    ".tsx": "code",
    ".go": "code",
    ".rs": "code",
    ".java": "code",
    ".c": "code",
    ".h": "code",
    ".cpp": "code",
    ".cc": "code",
    ".cxx": "code",
    ".hpp": "code",
    ".cs": "code",
    ".rb": "code",
    ".sh": "code",
    ".bash": "code",
    ".pdf": "pdf",
}

BINARY_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".ico", ".svg", ".webp",
    ".mp3", ".mp4", ".wav", ".avi", ".mov", ".mkv", ".flac", ".ogg",
    ".zip", ".tar", ".gz", ".rar", ".7z", ".bz2", ".xz",
    ".exe", ".dll", ".so", ".dylib", ".bin", ".o", ".a",
    ".woff", ".woff2", ".ttf", ".otf", ".eot",
    ".db", ".sqlite", ".sqlite3",
    ".class", ".jar", ".war",
    ".pyc", ".pyo", ".wasm",
}

DEFAULT_IGNORE = {
    ".git", ".obsidian", "blueprint", "data", "docker",
    "scripts", "tests", "node_modules", "__pycache__",
    "build", "dist", "venv", ".venv", "env",
}

# Keep for backwards compatibility
EXTENSION_MAP = SPECIALIZED_PARSERS


class Scanner:
    """Incremental filesystem scanner with SHA-256 change detection."""

    def __init__(self, root: str | Path, state_db: StateDB, ignore_file: str | Path | None = None):
        self.root = Path(root)
        self.state_db = state_db
        self.ignore_patterns = self._load_ignore_patterns(ignore_file)

    def _load_ignore_patterns(self, ignore_file: str | Path | None) -> list[str]:
        patterns = []
        if ignore_file and Path(ignore_file).exists():
            for line in Path(ignore_file).read_text().splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    patterns.append(line)
        return patterns

    def _is_ignored(self, path: Path) -> bool:
        rel = path.relative_to(self.root)
        parts = rel.parts

        for part in parts:
            if part in DEFAULT_IGNORE:
                return True

        rel_str = str(rel)
        for pattern in self.ignore_patterns:
            if fnmatch(rel_str, pattern) or fnmatch(path.name, pattern):
                return True
        return False

    def _compute_hash(self, file_path: Path) -> str:
        h = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        return h.hexdigest()

    def _classify_file(self, path: Path) -> str | None:
        ext = path.suffix.lower()
        if ext in BINARY_EXTENSIONS:
            return None
        specialized = SPECIALIZED_PARSERS.get(ext)
        if specialized:
            return specialized
        if self._is_text_file(path):
            return "text"
        return None

    def _is_text_file(self, path: Path) -> bool:
        try:
            with open(path, "rb") as f:
                chunk = f.read(8192)
            if not chunk:
                return False
            if b"\x00" in chunk:
                return False
            chunk.decode("utf-8")
            return True
        except (UnicodeDecodeError, PermissionError, OSError):
            return False

    def walk(self) -> Generator[dict, None, None]:
        """Walk the workspace and yield files that are new or changed."""
        seen_paths: set[str] = set()

        for entry in self._scandir_recursive(self.root):
            path = Path(entry.path)
            if self._is_ignored(path):
                continue

            file_type = self._classify_file(path)
            if file_type is None:
                continue

            file_path_str = str(path)
            seen_paths.add(file_path_str)

            current_hash = self._compute_hash(path)
            stored_hash = self.state_db.get_hash(file_path_str)

            if stored_hash == current_hash:
                continue

            status = "NEW" if stored_hash is None else "CHANGED"
            self.state_db.upsert(file_path_str, current_hash, file_type, status="ACTIVE")

            yield {
                "path": file_path_str,
                "file_type": file_type,
                "status": status,
                "hash": current_hash,
            }

        self._mark_deleted(seen_paths)
        self.state_db.commit()

    def _scandir_recursive(self, directory: Path) -> Generator[os.DirEntry, None, None]:
        try:
            with os.scandir(directory) as entries:
                for entry in entries:
                    if entry.is_dir(follow_symlinks=False):
                        if entry.name not in DEFAULT_IGNORE:
                            yield from self._scandir_recursive(Path(entry.path))
                    elif entry.is_file(follow_symlinks=False):
                        yield entry
        except PermissionError:
            pass

    def _mark_deleted(self, seen_paths: set[str]):
        previously_known = self.state_db.get_all_active_paths()
        for old_path in previously_known - seen_paths:
            self.state_db.mark_deleted(old_path)
