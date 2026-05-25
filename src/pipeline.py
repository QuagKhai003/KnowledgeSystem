"""Full pipeline orchestrator: scan → parse → compile → index → retrieve → format."""

import time
from pathlib import Path

from src.ingestion.scanner import Scanner
from src.ingestion.state_db import StateDB
from src.ingestion.parsers import parse_file
from src.compiler.pipeline import CompilerPipeline
from src.compiler.ontology_val import OntologyValidator
from src.compiler.schemas import KnowledgeObject
from src.indexing.manager import IndexManager
from src.indexing.embeddings import EmbeddingModel
from src.planner import QueryPlanner
from src.retrieval.coordinator import RetrievalCoordinator
from src.retrieval.context_builder import ContextBuilder
from src.adapters import get_adapter


def _connect_qdrant(config: dict):
    from src.indexing.qdrant_client import QdrantIndex
    db_cfg = config["databases"]["qdrant"]
    return QdrantIndex(host=db_cfg["host"], port=db_cfg["port"])


def _connect_opensearch(config: dict):
    from src.indexing.opensearch_cli import OpenSearchIndex
    db_cfg = config["databases"]["opensearch"]
    return OpenSearchIndex(host=db_cfg["host"], port=db_cfg["port"])


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
        self.compiler = CompilerPipeline()
        self.validator = OntologyValidator()
        self.planner = QueryPlanner()
        self._index_manager = None
        self._retrieval = None
        self._embedder = None

    def _get_embedder(self) -> EmbeddingModel:
        if self._embedder is None:
            self._embedder = EmbeddingModel()
        return self._embedder

    @property
    def index_manager(self) -> IndexManager:
        if self._index_manager is None:
            qdrant = _connect_qdrant(self.config)
            opensearch = _connect_opensearch(self.config)
            neo4j = _connect_neo4j(self.config)
            self._index_manager = IndexManager(
                embedding_model=self._get_embedder(),
                qdrant=qdrant,
                opensearch=opensearch,
                neo4j=neo4j,
            )
        return self._index_manager

    @property
    def retrieval(self) -> RetrievalCoordinator:
        if self._retrieval is None:
            qdrant = _connect_qdrant(self.config)
            opensearch = _connect_opensearch(self.config)
            neo4j = _connect_neo4j(self.config)
            self._retrieval = RetrievalCoordinator(
                qdrant=qdrant,
                opensearch=opensearch,
                neo4j=neo4j,
                embedder=self._get_embedder(),
            )
        return self._retrieval

    def scan_and_parse(self, verbose: bool = False) -> list[dict]:
        """Phase 1: Scan workspace and parse changed files."""
        state_db = StateDB(self.db_path)
        scanner = Scanner(self.root, state_db, self.ignore_file)
        results = []

        for file_info in scanner.walk():
            parsed = parse_file(file_info["path"], file_info["file_type"])
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

    def compile(self, scan_results: list[dict], verbose: bool = False) -> list[KnowledgeObject]:
        """Phase 2: Compile parsed files into Knowledge Objects."""
        objects = []

        for item in scan_results:
            if item["parsed"] is None:
                continue

            file_type = item["file_type"]
            parsed = item["parsed"]

            try:
                if file_type == "markdown":
                    objs = self.compiler.compile_markdown(parsed)
                elif file_type == "code":
                    objs = self.compiler.compile_code(parsed)
                elif file_type == "pdf":
                    objs = self.compiler.compile_markdown(parsed)
                else:
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

    def index(self, objects: list[KnowledgeObject], verbose: bool = False) -> dict:
        """Phase 3: Index Knowledge Objects into all databases + local store."""
        stats = {"indexed": 0, "failed": 0, "errors": []}
        state_db = StateDB(self.db_path)

        for obj in objects:
            try:
                result = self.index_manager.index_object(obj)
                if any(result.values()):
                    stats["indexed"] += 1
                else:
                    stats["failed"] += 1
                state_db.store_knowledge_object(
                    obj.id, obj.name,
                    obj.abstractions.level_0,
                    obj.abstractions.level_1,
                    obj.abstractions.level_2,
                    obj.abstractions.level_3,
                )
            except Exception as e:
                stats["failed"] += 1
                stats["errors"].append(f"{obj.id}: {e}")
                if verbose:
                    print(f"  ERROR indexing {obj.id}: {e}")

        state_db.commit()
        state_db.close()
        return stats

    def query(self, query_text: str, model: str = "default", verbose: bool = False) -> str:
        """Two-phase retrieval: locate documents, then extract relevant passages."""
        from src.retrieval.rerank import rrf_merge
        from src.retrieval.passage_extractor import extract_passages, Passage

        plan = self.planner.plan(query_text, target_model=model)

        # Phase 1: Locate — search L2/L3 across all databases to find relevant documents
        multi_results = self.retrieval.execute(plan)

        weights = {
            "dense": plan.dense_weight,
            "sparse": plan.sparse_weight,
            "graph": plan.graph_weight,
        }
        merged = rrf_merge(multi_results, weights=weights, k=60)
        top_ids = [r.id for r in merged[:plan.max_results]]

        # Phase 2: Extract — fetch L0/L1 from local store and extract relevant passages
        state_db = StateDB(self.db_path)
        ko_store = state_db.get_knowledge_objects_batch(top_ids)
        state_db.close()

        builder = ContextBuilder()
        blocks = []

        for result in merged[:plan.max_results]:
            ko = ko_store.get(result.id)
            if ko and ko["level_0"]:
                passages = extract_passages(
                    query=query_text,
                    level_0=ko["level_0"],
                    level_1=ko["level_1"],
                    max_passages=3,
                    passage_window=800,
                )
                if passages:
                    content = "\n\n".join(
                        f"[{p.section}]\n{p.text}" for p in passages
                    )
                    from src.retrieval.context_builder import ContextBlock
                    blocks.append(ContextBlock(
                        id=result.id,
                        title=ko["name"],
                        content=content,
                        abstraction_level=0,
                        sources=result.sources,
                    ))
                    continue

            block = builder._build_block(result, result.payload, ["level_2", "level_3"])
            if block:
                blocks.append(block)

        blocks = builder._fit_to_budget(blocks, plan.max_token_budget)

        adapter = get_adapter(model)
        relationships = self._extract_relationships_from_results(multi_results)
        formatted = adapter.format(blocks, query_text, relationships or None)

        return formatted

    def full_rebuild(self, verbose: bool = False) -> dict:
        """Run complete pipeline: scan → compile → index."""
        start = time.time()

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

    def _extract_relationships_from_results(self, multi_results: dict) -> list[dict]:
        """Extract relationship data from graph retrieval results."""
        rels = []
        for result in multi_results.get("graph", []):
            payload = result.payload
            if "source" in payload and "target" in payload:
                rels.append({
                    "source": payload["source"],
                    "target": payload["target"],
                    "predicate": payload.get("predicate", "related_to"),
                })
        return rels
