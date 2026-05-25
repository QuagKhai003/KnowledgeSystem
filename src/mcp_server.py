"""Knowledge OS MCP Server — exposes knowledge tools to any AI CLI that supports MCP."""

import json
import sys
from pathlib import Path


def _load_global_config() -> dict:
    """Load global config from ~/.k-os/config.yaml"""
    config_path = Path.home() / ".k-os" / "config.yaml"
    if not config_path.exists():
        return {}
    import yaml
    return yaml.safe_load(config_path.read_text()) or {}


def _get_install_dir() -> Path:
    global_cfg = _load_global_config()
    if global_cfg.get("install_dir"):
        return Path(global_cfg["install_dir"])
    return Path(__file__).resolve().parent.parent


def _load_project_config(workspace: str | None = None) -> dict:
    install_dir = _get_install_dir()
    import yaml
    config_path = install_dir / "config" / "settings.yaml"
    config = yaml.safe_load(config_path.read_text())

    if workspace:
        config["workspace"]["root"] = str(Path(workspace).resolve())
    elif config["workspace"]["root"] == "auto":
        global_cfg = _load_global_config()
        default_vault = global_cfg.get("default_vault", "")
        if default_vault:
            config["workspace"]["root"] = default_vault
        else:
            config["workspace"]["root"] = str(install_dir)

    global_cfg = _load_global_config()
    if global_cfg.get("databases"):
        for db_name, db_cfg in global_cfg["databases"].items():
            if db_name in config.get("databases", {}):
                config["databases"][db_name].update(db_cfg)

    return config


TOOLS = [
    {
        "name": "k-os-query",
        "description": "Query the Knowledge OS knowledge base. Returns relevant context from indexed documents, code, and PDFs.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Natural language query to search the knowledge base"
                },
                "model": {
                    "type": "string",
                    "description": "Target model format (claude/gpt/codex/qwen/gemini)",
                    "default": "claude"
                },
                "workspace": {
                    "type": "string",
                    "description": "Path to vault/workspace (uses default if not specified)"
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "k-os-scan",
        "description": "Scan a workspace/vault for files and show what would be indexed.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "workspace": {
                    "type": "string",
                    "description": "Path to vault/workspace to scan"
                }
            },
            "required": ["workspace"]
        }
    },
    {
        "name": "k-os-compile",
        "description": "Compile files from a workspace into Knowledge Objects (without indexing to databases).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "workspace": {
                    "type": "string",
                    "description": "Path to vault/workspace to compile"
                }
            },
            "required": ["workspace"]
        }
    },
    {
        "name": "k-os-rebuild",
        "description": "Full rebuild: scan, compile, and index a workspace into all databases.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "workspace": {
                    "type": "string",
                    "description": "Path to vault/workspace to rebuild"
                }
            },
            "required": ["workspace"]
        }
    },
    {
        "name": "k-os-status",
        "description": "Show the current state of the Knowledge OS databases and indexed files.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "workspace": {
                    "type": "string",
                    "description": "Path to vault/workspace (uses default if not specified)"
                }
            }
        }
    }
]


def _require(params: dict, *keys: str):
    """Validate required parameters are present and non-empty."""
    for key in keys:
        if key not in params or not str(params[key]).strip():
            raise ValueError(f"Missing required parameter: {key}")


def handle_query(params: dict) -> str:
    _require(params, "query")
    install_dir = _get_install_dir()
    sys.path.insert(0, str(install_dir))

    query = str(params["query"])[:10000]
    config = _load_project_config(params.get("workspace"))
    model = params.get("model", "claude")

    from src.pipeline import KnowledgePipeline
    pipeline = KnowledgePipeline(config)

    try:
        context = pipeline.query(query, model=model)
        return context
    except Exception as e:
        return f"Query failed: {e}\nAre databases running? Try: docker compose -f {install_dir}/docker/docker-compose.yml up -d"


def handle_scan(params: dict) -> str:
    _require(params, "workspace")
    install_dir = _get_install_dir()
    sys.path.insert(0, str(install_dir))

    config = _load_project_config(params.get("workspace"))

    from src.pipeline import KnowledgePipeline
    pipeline = KnowledgePipeline(config)

    results = pipeline.scan_and_parse(verbose=False)
    summary = [f"[{r['status']}] {r['path']} ({r['file_type']})" for r in results]
    return f"Found {len(results)} files:\n" + "\n".join(summary)


def handle_compile(params: dict) -> str:
    _require(params, "workspace")
    install_dir = _get_install_dir()
    sys.path.insert(0, str(install_dir))

    config = _load_project_config(params.get("workspace"))

    from src.pipeline import KnowledgePipeline
    pipeline = KnowledgePipeline(config)

    scan_results = pipeline.scan_and_parse()
    objects = pipeline.compile(scan_results)
    lines = [f"  [{obj.ontology_class}] {obj.name} ({obj.id})" for obj in objects]
    return f"Compiled {len(objects)} knowledge objects:\n" + "\n".join(lines)


def handle_rebuild(params: dict) -> str:
    _require(params, "workspace")
    install_dir = _get_install_dir()
    sys.path.insert(0, str(install_dir))

    config = _load_project_config(params.get("workspace"))

    from src.pipeline import KnowledgePipeline
    pipeline = KnowledgePipeline(config)

    result = pipeline.full_rebuild()
    return (
        f"Rebuild complete:\n"
        f"  Files scanned:    {result['files_scanned']}\n"
        f"  Objects compiled: {result['objects_compiled']}\n"
        f"  Objects indexed:  {result['objects_indexed']}\n"
        f"  Index failures:   {result['index_failures']}\n"
        f"  Time:             {result['elapsed_seconds']}s"
    )


def handle_status(params: dict) -> str:
    install_dir = _get_install_dir()
    sys.path.insert(0, str(install_dir))

    config = _load_project_config(params.get("workspace"))
    root = Path(config["workspace"]["root"])
    db_path = root / config["workspace"]["state_db"]

    if not db_path.exists():
        return "No state database found. Run k-os-rebuild first."

    import sqlite3
    conn = sqlite3.connect(str(db_path))
    row = conn.execute(
        "SELECT COUNT(*) as total, "
        "SUM(CASE WHEN status='ACTIVE' THEN 1 ELSE 0 END) as active, "
        "SUM(CASE WHEN status='DELETED' THEN 1 ELSE 0 END) as deleted "
        "FROM file_state"
    ).fetchone()
    conn.close()

    return f"Total tracked files: {row[0]}\n  Active: {row[1]}\n  Deleted: {row[2]}"


HANDLERS = {
    "k-os-query": handle_query,
    "k-os-scan": handle_scan,
    "k-os-compile": handle_compile,
    "k-os-rebuild": handle_rebuild,
    "k-os-status": handle_status,
}


def main():
    """MCP stdio server — reads JSON-RPC from stdin, writes to stdout."""
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue

        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue

        method = msg.get("method", "")
        msg_id = msg.get("id")

        if method == "initialize":
            response = {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {"listChanged": False}},
                    "serverInfo": {"name": "knowledge-os", "version": "0.1.0"},
                }
            }
        elif method == "notifications/initialized":
            continue
        elif method == "tools/list":
            response = {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {"tools": TOOLS}
            }
        elif method == "tools/call":
            tool_name = msg["params"]["name"]
            tool_args = msg["params"].get("arguments", {})
            handler = HANDLERS.get(tool_name)

            if handler is None:
                response = {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "error": {"code": -32601, "message": f"Unknown tool: {tool_name}"}
                }
            else:
                try:
                    result_text = handler(tool_args)
                    response = {
                        "jsonrpc": "2.0",
                        "id": msg_id,
                        "result": {
                            "content": [{"type": "text", "text": result_text}]
                        }
                    }
                except Exception as e:
                    response = {
                        "jsonrpc": "2.0",
                        "id": msg_id,
                        "result": {
                            "content": [{"type": "text", "text": f"Error: {e}"}],
                            "isError": True,
                        }
                    }
        else:
            response = {
                "jsonrpc": "2.0",
                "id": msg_id,
                "error": {"code": -32601, "message": f"Unknown method: {method}"}
            }

        sys.stdout.write(json.dumps(response) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
