"""Full pipeline orchestrator: scan → parse → compile → index → query (pointers)."""

import time
from pathlib import Path


def _connect_qdrant(config: dict):
    from src.indexing.qdrant_client import QdrantIndex
    db_cfg = config["databases"]["qdrant"]
    return QdrantIndex(host=db_cfg["host"], port=db_cfg["port"])


def _connect_neo4j(config: dict):
    import os
    from src.indexing.neo4j_client import Neo4jClient
    db_cfg = config["databases"]["neo4j"]
    password = os.environ.get("NEO4J_PASSWORD", db_cfg["password"])
    return Neo4jClient(uri=db_cfg["uri"], user=db_cfg["user"], password=password)


class KnowledgePipeline:
    """End-to-end orchestrator for the Knowledge OS."""

    def __init__(self, config: dict):
        self.config = config
        self.root = Path(config["workspace"]["root"])
        self.db_path = self.root / config["workspace"]["state_db"]
        self.ignore_file = self.root / config["workspace"]["ignore_file"]
        self._compiler = None
        self._validator = None
        self._fts = None
        self._qdrant = None
        self._neo4j = None
        self._embedder = None

    @property
    def compiler(self):
        if self._compiler is None:
            from src.compiler.pipeline import CompilerPipeline
            self._compiler = CompilerPipeline()
        return self._compiler

    @property
    def validator(self):
        if self._validator is None:
            from src.compiler.ontology_val import OntologyValidator
            self._validator = OntologyValidator()
        return self._validator

    @property
    def fts(self):
        if self._fts is None:
            from src.indexing.fts_index import FTSIndex
            self._fts = FTSIndex()
        return self._fts

    def _try_qdrant(self):
        if self._qdrant is None:
            try:
                self._qdrant = _connect_qdrant(self.config)
            except Exception:
                self._qdrant = False
        return self._qdrant if self._qdrant is not False else None

    def _try_neo4j(self):
        if self._neo4j is None:
            try:
                self._neo4j = _connect_neo4j(self.config)
            except Exception:
                self._neo4j = False
        return self._neo4j if self._neo4j is not False else None

    def _get_embedder(self):
        if self._embedder is None:
            from src.indexing.embeddings import EmbeddingModel
            self._embedder = EmbeddingModel()
        return self._embedder

    def scan_and_parse(self, verbose: bool = False) -> list[dict]:
        """Phase 1: Scan workspace and parse changed files."""
        from src.ingestion.scanner import Scanner
        from src.ingestion.state_db import StateDB
        from src.ingestion.parsers import parse_file as _parse_file
        self._parse_file = _parse_file

        state_db = StateDB(self.db_path)
        scanner = Scanner(self.root, state_db, self.ignore_file)
        results = []

        for file_info in scanner.walk():
            parsed = self._parse_file(file_info["path"], file_info["file_type"])
            results.append({
                "path": file_info["path"],
                "file_type": file_info["file_type"],
                "status": file_info["status"],
                "parsed": parsed,
            })
            if verbose:
                print(f"  [{file_info['status']}] {file_info['path']}")

        state_db.close()
        return results

    def compile(self, scan_results: list[dict], verbose: bool = False) -> list:
        """Phase 2: Compile parsed files into Knowledge Objects."""
        objects = []

        for item in scan_results:
            if item["parsed"] is None:
                continue

            file_type = item["file_type"]
            parsed = item["parsed"]

            try:
                objs = self.compiler.compile(parsed, file_type)
                if not objs:
                    continue

                errors = self.validator.validate(objs)
                error_ids = {e.object_id for e in errors}
                for obj in objs:
                    if obj.id not in error_ids:
                        objects.append(obj)
                    elif verbose:
                        obj_errors = [e for e in errors if e.object_id == obj.id]
                        print(f"  WARN: {obj.id} failed validation: {obj_errors}")

            except Exception as e:
                if verbose:
                    print(f"  ERROR compiling {item['path']}: {e}")

        return objects

    def index(self, objects, verbose: bool = False) -> dict:
        """Phase 3: Index into SQLite FTS5 (always) + Qdrant/Neo4j (if available)."""
        from src.ingestion.state_db import StateDB

        stats = {"indexed": 0, "failed": 0, "errors": []}
        global_db = StateDB(self._global_store_path())
        qdrant = self._try_qdrant()
        neo4j = self._try_neo4j()
        embedder = self._get_embedder() if qdrant else None

        for obj in objects:
            try:
                sections = obj.abstractions.level_1
                keywords = obj.abstractions.level_3
                embed_text = f"{obj.name} | {obj.abstractions.level_2} | {keywords}"

                self.fts.index_document({
                    "id": obj.id,
                    "type": obj.type,
                    "name": obj.name,
                    "content": embed_text,
                    "tags": obj.tags,
                    "file_path": obj.source_file,
                    "domain": obj.domain,
                    "sections": sections,
                    "keywords": keywords,
                })

                if obj.relationships:
                    edges = [(r.target, r.predicate) for r in obj.relationships]
                    self.fts.index_edges(obj.id, edges)

                if qdrant and embedder:
                    try:
                        vector = embedder.embed(embed_text)
                        payload = {
                            "type": obj.type,
                            "name": obj.name,
                            "domain": obj.domain,
                            "tags": obj.tags,
                            "file_path": obj.source_file,
                        }
                        qdrant.upsert(obj.id, vector, payload)
                    except Exception:
                        pass

                if neo4j:
                    try:
                        neo4j.sync_knowledge_object(obj)
                    except Exception:
                        pass

                global_db.store_knowledge_object(
                    obj.id, obj.name,
                    obj.abstractions.level_0,
                    obj.abstractions.level_1,
                    obj.abstractions.level_2,
                    obj.abstractions.level_3,
                )
                stats["indexed"] += 1

            except Exception as e:
                stats["failed"] += 1
                stats["errors"].append(f"{obj.id}: {e}")
                if verbose:
                    print(f"  ERROR indexing {obj.id}: {e}")

        global_db.commit()
        global_db.close()
        return stats

    def query(self, query_text: str, model: str = "default", verbose: bool = False) -> str:
        """Query returns pointers: file paths + matched terms + sections."""
        from src.ingestion.state_db import StateDB

        results = self.fts.search(query_text, limit=10)

        global_db = StateDB(self._global_store_path())
        obj_ids = [r["id"] for r in results]
        ko_store = global_db.get_knowledge_objects_batch(obj_ids)
        global_db.close()

        pointers = []
        seen_files = set()

        for r in results:
            file_path = r["file_path"]
            if not file_path or file_path in seen_files:
                continue
            seen_files.add(file_path)

            ko = ko_store.get(r["id"], {})
            matched_terms = self._extract_matched_terms(query_text, r, ko)

            pointer = {
                "file": file_path,
                "name": r["name"],
                "why": matched_terms,
                "sections": [s.strip() for s in r["sections"].split(";")[:5] if s.strip()],
                "score": round(r["score"], 3),
                "domain": r["domain"],
            }
            pointers.append(pointer)

        from src.adapters import get_adapter
        adapter = get_adapter(model)
        return adapter.format_pointers(pointers, query_text)

    def incremental_update(self, verbose: bool = False) -> dict:
        """Scan for new/changed files and index only the delta."""
        scan_results = self.scan_and_parse(verbose=verbose)
        if not scan_results:
            return {"files_scanned": 0, "objects_compiled": 0, "objects_indexed": 0}

        objects = self.compile(scan_results, verbose=verbose)
        if not objects:
            return {"files_scanned": len(scan_results), "objects_compiled": 0, "objects_indexed": 0}

        index_stats = self.index(objects, verbose=verbose)
        return {
            "files_scanned": len(scan_results),
            "objects_compiled": len(objects),
            "objects_indexed": index_stats["indexed"],
        }

    def full_rebuild(self, verbose: bool = False) -> dict:
        """Run complete pipeline: scan → compile → index."""
        start = time.time()

        self.fts.wipe()

        if verbose:
            print("Phase 1: Scanning and parsing...")
        scan_results = self.scan_and_parse(verbose=verbose)

        if verbose:
            print(f"\nPhase 2: Compiling {len(scan_results)} files...")
        objects = self.compile(scan_results, verbose=verbose)

        if verbose:
            print(f"\nPhase 3: Indexing {len(objects)} objects...")
        index_stats = self.index(objects, verbose=verbose)

        elapsed = time.time() - start

        return {
            "files_scanned": len(scan_results),
            "objects_compiled": len(objects),
            "objects_indexed": index_stats["indexed"],
            "index_failures": index_stats["failed"],
            "elapsed_seconds": round(elapsed, 2),
        }

    def _global_store_path(self) -> Path:
        store_dir = Path.home() / ".k-os"
        store_dir.mkdir(parents=True, exist_ok=True)
        return store_dir / "knowledge_store.db"

    def _extract_matched_terms(self, query: str, result: dict, ko: dict) -> str:
        """Find which terms from the result matched the query context."""
        query_words = set(query.lower().split())
        keywords = result.get("keywords", "") or ko.get("level_3", "")
        keyword_list = [k.strip() for k in keywords.split(";") if k.strip()]

        matched = []
        for kw in keyword_list:
            kw_words = set(kw.lower().split())
            if kw_words & query_words:
                matched.append(kw)

        if not matched:
            matched = keyword_list[:5]

        return ", ".join(matched[:8])
