# Knowledge OS

A local-first knowledge compiler that transforms any folder of documents into a structured, machine-usable knowledge engine.

This is **not** traditional RAG. Documents are raw material — knowledge must be compiled.

```
Raw Files → Parse → Knowledge Objects → Ontology → Abstractions → Index → Query → File Pointers → AI reads raw files
```

## Install

Prerequisites: Python 3.11+, Git. Optional: [Docker Desktop](https://www.docker.com/products/docker-desktop/) for semantic search + graph traversal.

```bash
# macOS / Linux / WSL / Git Bash
curl -fsSL https://raw.githubusercontent.com/QuagKhai003/KnowledgeSystem/master/scripts/bootstrap.sh | bash

# Windows (PowerShell 5.1+)
irm https://raw.githubusercontent.com/QuagKhai003/KnowledgeSystem/master/scripts/bootstrap.ps1 | iex
```

One command handles: clone, Python venv, dependencies, global `k-os` CLI, database containers, and AI CLI integration.

## Quick Start

```bash
# Index any folder (Obsidian vault, notes, code, PDFs — anything)
k-os -w /path/to/your/folder rebuild -v

# Query — returns file pointers, AI reads the raw files
k-os query "What is cryptography?"

# In Claude Code or any supported AI CLI
/k-os query what is cryptography
```

## How It Works

```
1. SCAN        You point k-os at a folder. It finds all .md, .py, .js, .ts, .pdf files.
               SHA-256 hashing detects changes — unchanged files are skipped.

2. COMPILE     Each file becomes a Knowledge Object with:
               - L0: full raw content
               - L1: heading/section outline
               - L2: concept summary (sampled from full document, 800 chars)
               - L3: TF-IDF keywords (100 terms, bigrams, proper noun boost)
               - Ontology class, domain, tags, relationships

3. INDEX       Tiered storage — basic works out of the box, full adds Docker:
               - SQLite FTS5: BM25 keyword search (always, no Docker)
               - Qdrant: vector embeddings for semantic search (optional, Docker)
               - Neo4j: relationship graph for connected concepts (optional, Docker)

4. QUERY       When you ask a question:
               - BM25 search across FTS5 index (+ Qdrant/Neo4j if available)
               - Returns file pointers: paths, matched terms, sections, scores
               - AI reads the raw files directly — zero information loss
```

All indexes are global — rebuild multiple folders and query across all of them.

## CLI Commands

```bash
k-os -w <path> scan -v           # Scan folder for files (dry run, no indexing)
k-os -w <path> compile --json    # Compile files into Knowledge Objects
k-os -w <path> rebuild -v        # Full pipeline: scan → compile → index
k-os status                      # Show database summary
k-os parse path/to/file.md       # Parse a single file (debug)
k-os query "question"            # Query — returns file pointers
k-os query "question" -m claude  # Query with specific output adapter
k-os mcp                         # Start MCP server for AI CLI integration
k-os install --mcp               # Show MCP config for manual setup
```

The `-w` flag goes **before** the command and accepts any folder path.

## AI CLI Integration

The install script auto-detects and configures all supported AI CLIs via MCP:

| AI CLI | Integration | How to use |
|--------|-------------|-----------|
| Claude Code | Slash command + MCP | `/k-os your question` |
| Cursor | MCP server | AI sees k-os tools automatically |
| Windsurf | MCP server | AI sees k-os tools automatically |
| Continue (VS Code) | MCP server | AI sees k-os tools automatically |
| Codex CLI (OpenAI) | MCP server | AI sees k-os tools automatically |
| Antigravity (Google) | MCP server | AI sees k-os tools automatically |

MCP exposes 5 tools: `k-os-query`, `k-os-scan`, `k-os-compile`, `k-os-rebuild`, `k-os-status`.

## Output Adapters

The adapter is **auto-detected** based on which AI CLI you're using — no `-m` flag needed. You can still override manually with `-m claude`, `-m codex`, etc.

| Adapter | Auto-detected when |
|---------|-------------------|
| Claude | `CLAUDE_CODE` or `CLAUDE_ACCESS_TOKEN` set |
| Codex | `OPENAI_API_KEY` set |
| Gemini | `GEMINI_API_KEY` or `GOOGLE_API_KEY` set |
| Qwen | `DASHSCOPE_API_KEY` set |
| GPT | Default fallback |

Adapters format the file pointers (paths, matched terms, sections, scores) for each AI CLI. These are **not** models that Knowledge OS runs — no API keys or LLMs are needed.

## Architecture

| Layer | Purpose |
|-------|---------|
| Ingestion | Incremental file scanning with SHA-256 change detection |
| Parsing | Markdown (wikilinks, frontmatter, headings), Python/JS AST, PDF layout |
| Compilation | Knowledge Objects with formal ontology (10 classes, 7 predicates) |
| Abstraction | 4-level hierarchy: L0 raw → L1 outline → L2 summary → L3 TF-IDF keywords |
| Indexing | SQLite FTS5 (always) + Qdrant vectors + Neo4j graph (optional, Docker) |
| Retrieval | BM25 search → file pointers (paths, matched terms, sections, scores) |
| Adapters | Pointer formatting per target AI CLI |

## Project Structure

```
k-os                 # CLI entry point (cross-platform)
k-os.bat             # Windows batch wrapper
src/
├── ingestion/       # File scanning, state tracking
│   └── parsers/     # Markdown, code AST, PDF parsers
├── compiler/        # Knowledge Objects, ontology, abstraction generation
├── indexing/        # SQLite FTS5, Qdrant, Neo4j clients
├── retrieval/       # Context builder
├── planner/         # Intent classification, query planning
├── adapters/        # Output formatters (Claude, GPT, Codex, Qwen, Gemini)
├── pipeline.py      # End-to-end orchestrator
└── mcp_server.py    # MCP server for AI CLI integration

scripts/
├── bootstrap.sh     # One-line installer (macOS/Linux/WSL)
├── bootstrap.ps1    # One-line installer (Windows PowerShell)
├── install.sh       # Full installer (bash)
├── install.ps1      # Full installer (PowerShell)
└── db_setup.py      # Cross-platform database health check

config/              # settings.yaml, .knowledgeignore
docker/              # docker-compose.yml for Neo4j, Qdrant (optional)
```

## Uninstall

### Full uninstall (macOS / Linux / WSL)

```bash
# Stop and remove database containers + data
docker compose -f ~/.k-os/KnowledgeSystem/docker/docker-compose.yml down -v

# Remove global CLI
rm -f ~/.local/bin/k-os

# Remove all Knowledge OS files and config
rm -rf ~/.k-os

# Remove AI CLI integrations
rm -f ~/.claude/commands/k-os.md
# Remove "knowledge-os" entry from these files if they exist:
#   ~/.claude/settings.json
#   ~/.cursor/mcp.json
#   ~/.codeium/windsurf/mcp_config.json
#   ~/.continue/config.json
#   ~/.codex/config.toml        (delete the [mcp_servers.knowledge-os] block)
#   ~/.gemini/config/mcp_config.json
```

### Full uninstall (Windows PowerShell)

```powershell
# Stop and remove database containers + data
docker compose -f "$env:USERPROFILE\.k-os\KnowledgeSystem\docker\docker-compose.yml" down -v

# Remove all Knowledge OS files, config, and global CLI
Remove-Item -Recurse -Force "$env:USERPROFILE\.k-os"

# Remove from PATH
$path = [Environment]::GetEnvironmentVariable("Path", "User")
$path = ($path -split ";" | Where-Object { $_ -notlike "*\.k-os\bin*" }) -join ";"
[Environment]::SetEnvironmentVariable("Path", $path, "User")

# Remove AI CLI integrations
Remove-Item -Force "$env:USERPROFILE\.claude\commands\k-os.md" -ErrorAction SilentlyContinue
# Remove "knowledge-os" entry from these files if they exist:
#   ~/.claude/settings.json
#   ~/.cursor/mcp.json
#   ~/.codeium/windsurf/mcp_config.json
#   ~/.continue/config.json
#   ~/.codex/config.toml        (delete the [mcp_servers.knowledge-os] block)
#   ~/.gemini/config/mcp_config.json
```

### What each part removes

| What | Location | Purpose |
|------|----------|---------|
| `~/.k-os/` | Config + cloned repo | Global config, source code, venv |
| `~/.local/bin/k-os` | Global CLI (Linux/Mac/WSL) | Launcher script |
| `~/.k-os/bin/k-os.cmd` | Global CLI (Windows) | Launcher batch file |
| `~/.claude/commands/k-os.md` | Claude Code | `/k-os` slash command |
| `knowledge-os` in MCP configs | AI CLI settings | MCP server entries |
| Docker containers | Docker | Neo4j, Qdrant (optional) + their indexed data |

## Key Design Decisions

- **No LLM required** — all abstraction is algorithmic, no API keys needed
- **No Docker required** — SQLite FTS5 provides keyword search out of the box
- **No fixed chunking** — abstraction levels replace arbitrary splits
- **No information loss** — queries return file pointers, AI reads raw files directly
- **Incremental updates** — SHA-256 hashing skips unchanged files
- **Tiered infrastructure** — basic (SQLite only) or full (+ Qdrant + Neo4j with Docker)
- **Model-agnostic output** — adapter pattern formats pointers for any AI CLI
- **Global indexes** — rebuild multiple folders, query across all of them
