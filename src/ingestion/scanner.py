import hashlib
import os
from fnmatch import fnmatch
from pathlib import Path
from typing import Generator

from .state_db import StateDB

EXTENSION_MAP = {
    ".md": "markdown",
    ".py": "code",
    ".js": "code",
    ".ts": "code",
    ".jsx": "code",
    ".tsx": "code",
    ".pdf": "pdf",
}

DEFAULT_IGNORE = {
    ".git", ".obsidian", "blueprint", "data", "docker",
    "scripts", "tests", "node_modules", "__pycache__",
    "build", "dist", "venv", ".venv", "env",
}


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

    def _get_file_type(self, path: Path) -> str | None:
        return EXTENSION_MAP.get(path.suffix.lower())

    def walk(self) -> Generator[dict, None, None]:
        """Walk the workspace and yield files that are new or changed."""
        seen_paths: set[str] = set()

        for entry in self._scandir_recursive(self.root):
            path = Path(entry.path)
            if self._is_ignored(path):
                continue

            file_type = self._get_file_type(path)
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
