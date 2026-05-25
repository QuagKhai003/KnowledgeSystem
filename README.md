# Knowledge OS

A local-first knowledge compiler that transforms any folder of documents into a structured, machine-usable knowledge engine.

This is **not** traditional RAG. Documents are raw material — knowledge must be compiled.

```
Raw Files → Parse → Knowledge Objects → Ontology → Abstractions → Multi-Index → Retrieval → Formatted Context
```

## Install

Prerequisites: [Docker Desktop](https://www.docker.com/products/docker-desktop/), Python 3.11+, Git.

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

# Query your knowledge from any directory
k-os query "What is cryptography?" --live

# In Claude Code or any supported AI CLI
/k-os what is cryptography
```

## How It Works

```
1. SCAN        You point k-os at a folder. It finds all .md, .py, .js, .ts, .pdf files.
               SHA-256 hashing detects changes — unchanged files are skipped.

2. COMPILE     Each file becomes a Knowledge Object with:
               - L0: full raw content
               - L1: algorithmic outline (key sentences, headings)
               - L2: concept summary (key terms, definitions, bullet points)
               - Ontology class, domain, tags, relationships (wikilinks, imports, inheritance)

3. INDEX       Objects are stored in 3 databases (running in Docker):
               - Qdrant: vector embeddings for semantic search
               - OpenSearch: keyword index for exact matches
               - Neo4j: relationship graph for connected concepts

4. QUERY       When you ask a question:
               - Intent classifier determines search strategy
               - Parallel search across all 3 databases
               - Results fused with Reciprocal Rank Fusion (RRF)
               - Context formatted for your AI CLI's consumption
```

All databases are global — you can rebuild multiple folders and query across all of them.

## CLI Commands

```bash
k-os -w <path> scan -v           # Scan folder for files (dry run, no indexing)
k-os -w <path> compile --json    # Compile files into Knowledge Objects
k-os -w <path> rebuild -v        # Full pipeline: scan → compile → index
k-os status                      # Show database summary
k-os parse path/to/file.md       # Parse a single file (debug)
k-os query "question" --live     # Query with live database retrieval
k-os query "question" -m claude  # Query plan only (no database needed)
k-os query "question" --json     # Output full query plan as JSON
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

When context is retrieved, it is formatted differently depending on which AI model will consume it:

| Adapter | Format | Context Budget |
|---------|--------|---------------|
| Claude (`-m claude`) | XML with ontology hierarchy | 150,000 tokens |
| GPT (`-m gpt`) | Structured Markdown | 8,000 tokens |
| Codex (`-m codex`) | Minimal comments + raw code | 8,000 tokens |
| Qwen (`-m qwen`) | Compact JSON | 32,000 tokens |
| Gemini (`-m gemini`) | Markdown with tables | 128,000 tokens |

These are **not** models that Knowledge OS runs. They control how retrieved context is formatted before being passed to your AI CLI. No API keys or LLMs are needed.

## Architecture

| Layer | Purpose |
|-------|---------|
| Ingestion | Incremental file scanning with SHA-256 change detection |
| Parsing | Markdown (wikilinks, frontmatter, headings), Python/JS AST, PDF layout |
| Compilation | Knowledge Objects with formal ontology (10 classes, 7 predicates) |
| Abstraction | 3-level hierarchy: L0 raw → L1 outline → L2 concept summary |
| Indexing | Dense vectors (Qdrant), sparse keywords (OpenSearch), graph (Neo4j) |
| Retrieval | Intent-driven query planning, parallel search, RRF fusion |
| Adapters | Output formatting per target model (XML, Markdown, JSON) |

## Project Structure

```
k-os                 # CLI entry point (cross-platform)
k-os.bat             # Windows batch wrapper
src/
├── ingestion/       # File scanning, state tracking
│   └── parsers/     # Markdown, code AST, PDF parsers
├── compiler/        # Knowledge Objects, ontology, abstraction generation
├── indexing/        # Qdrant, OpenSearch, Neo4j clients + index manager
├── retrieval/       # Search coordinator, RRF reranking, context builder
├── planner/         # Intent classification, query planning
├── adapters/        # Output formatters (Claude, GPT, Codex, Qwen, Gemini)
├── pipeline.py      # End-to-end orchestrator
└── mcp_server.py    # MCP server for AI CLI integration

scripts/
├── bootstrap.sh     # One-line installer (macOS/Linux/WSL)
├── bootstrap.ps1    # One-line installer (Windows PowerShell)
├── install.sh       # Full installer (bash)
├── install.ps1      # Full installer (PowerShell)
├── db_setup.sh      # Database health check
└── db_setup.py      # Cross-platform database setup

config/              # settings.yaml, .knowledgeignore
docker/              # docker-compose.yml for Neo4j, Qdrant, OpenSearch
```

## Uninstall

### Full uninstall (macOS / Linux / WSL)

```bash
# Stop and remove database containers + data
docker compose -f ~/.k-os/KnowledgeSystem/docker/docker-compose.yml down -v

# Remove global CLI
sudo rm -f /usr/local/bin/k-os

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
| `/usr/local/bin/k-os` | Global CLI (Linux/Mac) | Launcher script |
| `~/.k-os/bin/k-os.cmd` | Global CLI (Windows) | Launcher batch file |
| `~/.claude/commands/k-os.md` | Claude Code | `/k-os` slash command |
| `knowledge-os` in MCP configs | AI CLI settings | MCP server entries |
| Docker containers | Docker | Neo4j, Qdrant, OpenSearch + all indexed data |

## Key Design Decisions

- **No LLM required** — all abstraction is algorithmic, no API keys needed
- **No fixed chunking** — abstraction levels replace arbitrary splits
- **Incremental updates** — SHA-256 hashing skips unchanged files
- **Multi-signal retrieval** — dense + sparse + graph, fused with RRF
- **Model-agnostic output** — adapter pattern formats context for any AI
- **Global databases** — rebuild multiple folders, query across all of them
