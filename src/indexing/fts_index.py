"""SQLite FTS5 full-text search index for keyword/BM25 search."""

import sqlite3
from pathlib import Path


class FTSIndex:
    """SQLite FTS5 keyword search. No Docker, no dependencies beyond Python."""

    def __init__(self, db_path: str | Path | None = None):
        if db_path is None:
            db_path = Path.home() / ".k-os" / "fts_index.db"
        self._path = Path(db_path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self._path))
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self):
        self._conn.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS documents USING fts5(
                object_id,
                name,
                content,
                tags,
                file_path,
                domain,
                sections,
                keywords
            )
        """)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS doc_meta (
                object_id TEXT PRIMARY KEY,
                name TEXT,
                file_path TEXT,
                domain TEXT,
                doc_type TEXT,
                sections TEXT,
                keywords TEXT
            )
        """)
        self._conn.commit()

    def index_document(self, doc: dict):
        obj_id = doc["id"]
        self._conn.execute("DELETE FROM documents WHERE object_id = ?", (obj_id,))
        self._conn.execute(
            "INSERT INTO documents (object_id, name, content, tags, file_path, domain, sections, keywords) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                obj_id,
                doc.get("name", ""),
                doc.get("content", ""),
                " ".join(doc.get("tags", [])),
                doc.get("file_path", ""),
                doc.get("domain", ""),
                doc.get("sections", ""),
                doc.get("keywords", ""),
            ),
        )
        self._conn.execute(
            "INSERT OR REPLACE INTO doc_meta VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                obj_id,
                doc.get("name", ""),
                doc.get("file_path", ""),
                doc.get("domain", ""),
                doc.get("type", ""),
                doc.get("sections", ""),
                doc.get("keywords", ""),
            ),
        )
        self._conn.commit()

    def search(self, query: str, limit: int = 10) -> list[dict]:
        safe_query = " OR ".join(
            f'"{term}"' for term in query.split() if term.strip()
        )
        if not safe_query:
            return []

        rows = self._conn.execute(
            "SELECT object_id, name, file_path, domain, sections, keywords, "
            "bm25(documents) as score "
            "FROM documents WHERE documents MATCH ? "
            "ORDER BY bm25(documents) LIMIT ?",
            (safe_query, limit),
        ).fetchall()

        return [
            {
                "id": row["object_id"],
                "name": row["name"],
                "file_path": row["file_path"],
                "domain": row["domain"],
                "sections": row["sections"],
                "keywords": row["keywords"],
                "score": abs(row["score"]),
            }
            for row in rows
        ]

    def wipe(self):
        self._conn.execute("DELETE FROM documents")
        self._conn.execute("DELETE FROM doc_meta")
        self._conn.commit()

    def count(self) -> int:
        row = self._conn.execute("SELECT COUNT(*) FROM doc_meta").fetchone()
        return row[0]

    def close(self):
        self._conn.close()
