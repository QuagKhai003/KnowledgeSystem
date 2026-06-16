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
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS edges (
                source_id TEXT NOT NULL,
                target_id TEXT NOT NULL,
                predicate TEXT NOT NULL,
                PRIMARY KEY (source_id, target_id, predicate)
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

    # Common English words that add noise to keyword search, plus query
    # scaffolding ("what have I done..."). Filtered out before matching.
    _STOPWORDS = {
        "a", "an", "the", "of", "in", "on", "at", "to", "for", "with", "and",
        "or", "is", "are", "was", "were", "be", "been", "am", "do", "does",
        "did", "done", "have", "has", "had", "i", "you", "it", "this", "that",
        "these", "those", "my", "me", "we", "us", "our", "what", "which",
        "how", "when", "where", "who", "why", "as", "by", "from", "about",
    }

    def _query_tokens(self, query: str) -> list[str]:
        tokens = []
        for raw in query.lower().split():
            term = "".join(ch for ch in raw if ch.isalnum())
            if not term or term in self._STOPWORDS:
                continue
            # Drop single non-digit characters ("b", "x"); keep digits ("5")
            if len(term) < 2 and not term.isdigit():
                continue
            tokens.append(term)
        return tokens

    def search(self, query: str, limit: int = 10) -> list[dict]:
        tokens = self._query_tokens(query)
        safe_query = " OR ".join(f'"{t}"' for t in tokens)
        if not safe_query:
            return []

        # Column weights for bm25(). Order matches the fts5 table definition:
        # object_id, name, content, tags, file_path, domain, sections, keywords.
        # A filename / heading / keyword hit is far more telling than a single
        # mention buried in body text, so content is weighted lowest.
        weights = "0.0, 10.0, 1.0, 5.0, 8.0, 5.0, 6.0, 6.0"

        rows = self._conn.execute(
            f"SELECT object_id, name, file_path, domain, sections, keywords, "
            f"bm25(documents, {weights}) as score "
            f"FROM documents WHERE documents MATCH ? "
            f"ORDER BY bm25(documents, {weights}) LIMIT ?",
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

    def index_edges(self, source_id: str, edges: list[tuple[str, str]]):
        self._conn.execute("DELETE FROM edges WHERE source_id = ?", (source_id,))
        for target_id, predicate in edges:
            self._conn.execute(
                "INSERT OR IGNORE INTO edges (source_id, target_id, predicate) VALUES (?, ?, ?)",
                (source_id, target_id, predicate),
            )
        self._conn.commit()

    def get_hubs(self, limit: int = 20) -> list[dict]:
        rows = self._conn.execute("""
            SELECT e.target_id, m.name, m.file_path, m.domain, COUNT(*) as inbound
            FROM edges e
            LEFT JOIN doc_meta m ON e.target_id = m.object_id
            GROUP BY e.target_id
            ORDER BY inbound DESC
            LIMIT ?
        """, (limit,)).fetchall()
        return [
            {"id": r[0], "name": r[1] or r[0], "file_path": r[2] or "",
             "domain": r[3] or "", "inbound": r[4]}
            for r in rows
        ]

    def get_graph_data(self) -> dict:
        nodes = {}
        for row in self._conn.execute("SELECT object_id, name, file_path, domain FROM doc_meta").fetchall():
            nodes[row[0]] = {"id": row[0], "name": row[1], "file_path": row[2], "domain": row[3]}
        edges = []
        for row in self._conn.execute("SELECT source_id, target_id, predicate FROM edges").fetchall():
            edges.append({"source": row[0], "target": row[1], "predicate": row[2]})
            for nid in (row[0], row[1]):
                if nid not in nodes:
                    nodes[nid] = {"id": nid, "name": nid, "file_path": "", "domain": ""}
        return {"nodes": list(nodes.values()), "edges": edges}

    def wipe(self):
        self._conn.execute("DELETE FROM documents")
        self._conn.execute("DELETE FROM doc_meta")
        self._conn.execute("DELETE FROM edges")
        self._conn.commit()

    def count(self) -> int:
        row = self._conn.execute("SELECT COUNT(*) FROM doc_meta").fetchone()
        return row[0]

    def close(self):
        self._conn.close()
