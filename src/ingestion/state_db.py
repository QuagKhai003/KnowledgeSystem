import sqlite3
import time
from pathlib import Path
from typing import Optional


class StateDB:
    """SQLite-backed file state tracker for incremental ingestion."""

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.db_path))
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self):
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS file_state (
                file_path TEXT PRIMARY KEY,
                sha256_hash TEXT NOT NULL,
                last_modified INTEGER NOT NULL,
                file_type TEXT NOT NULL,
                indexed_at INTEGER NOT NULL,
                status TEXT NOT NULL
            )
        """)
        self._conn.commit()

    def get_hash(self, file_path: str) -> Optional[str]:
        row = self._conn.execute(
            "SELECT sha256_hash FROM file_state WHERE file_path = ?",
            (file_path,)
        ).fetchone()
        return row["sha256_hash"] if row else None

    def upsert(self, file_path: str, sha256_hash: str, file_type: str, status: str = "ACTIVE"):
        now = int(time.time())
        self._conn.execute("""
            INSERT INTO file_state (file_path, sha256_hash, last_modified, file_type, indexed_at, status)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(file_path) DO UPDATE SET
                sha256_hash = excluded.sha256_hash,
                last_modified = excluded.last_modified,
                file_type = excluded.file_type,
                indexed_at = excluded.indexed_at,
                status = excluded.status
        """, (file_path, sha256_hash, now, file_type, now, status))

    def mark_deleted(self, file_path: str):
        self._conn.execute(
            "UPDATE file_state SET status = 'DELETED' WHERE file_path = ?",
            (file_path,)
        )

    def commit(self):
        self._conn.commit()

    def get_all_active_paths(self) -> set[str]:
        rows = self._conn.execute(
            "SELECT file_path FROM file_state WHERE status != 'DELETED'"
        ).fetchall()
        return {row["file_path"] for row in rows}

    def close(self):
        self._conn.close()
