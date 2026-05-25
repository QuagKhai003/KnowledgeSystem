# Knowledge OS

A local-first knowledge compiler that transforms an Obsidian vault into a structured, machine-usable intelligence engine.

This is **not** traditional RAG. Documents are raw material — knowledge must be compiled.

```
Raw Notes → Parser → Knowledge Objects → Ontology → Graph → Abstractions → Multi-Index → Retrieval → Model Adapters
```

## Architecture

| Layer | Purpose |
|-------|---------|
| Ingestion | Incremental file scanning with SHA-256 change detection |
| Parsing | Markdown (wikilinks, frontmatter, headings), Python AST, PDF layout |
| Compilation | Knowledge Objects with formal ontology (10 classes, 7 predicates) |
| Abstraction | 4-level hierarchy: raw → outline → concept summary → domain overview |
| Indexing | Dense vectors (Qdrant), sparse keywords (OpenSearch), graph (Neo4j) |
| Retrieval | Intent-driven query planning, parallel search, RRF fusion |
| Adapters | Model-specific context formatting (Claude, GPT, Codex, Qwen, Gemini) |

## Quick Start

```bash
# After install, index any folder
k-os -w /path/to/your/vault rebuild -v

# Query your knowledge from anywhere
k-os query "What is cryptography?" --live

# In Claude Code (any project)
/k-os what is cryptography
```

## Install

Prerequisites: [Docker Desktop](https://www.docker.com/products/docker-desktop/), Python 3.11+, Git.

```bash
# macOS / Linux / WSL / Git Bash
curl -fsSL https://raw.githubusercontent.com/QuagKhai003/KnowledgeSystem/master/scripts/bootstrap.sh | bash

# Windows (PowerShell 5.1+)
irm https://raw.githubusercontent.com/QuagKhai003/KnowledgeSystem/master/scripts/bootstrap.ps1 | iex
```

That's it. One command handles: clone, venv, dependencies, global CLI, databases, and Claude Code integration.

## CLI Usage

```bash
# Scan workspace for new/changed files
k-os scan

# Scan a different vault/folder
k-os -w /path/to/obsidian/vault scan -v

# Parse a single file
k-os parse path/to/file.md

# Full rebuild (scan + compile + index)
k-os -w /path/to/vault rebuild -v

# Check indexing status
k-os status

# Query with intent classification and plan generation
k-os query "How does Union Find work?" -m claude
k-os query "implement path compression" -m codex --json

# Query with live retrieval from databases
k-os query "What is cryptography?" --live
```

## AI CLI Integration

The install script auto-detects and configures all supported AI CLIs:

| AI CLI | Integration | How to use |
|--------|-------------|-----------|
| Claude Code | Slash command + MCP | `/k-os your question` |
| Cursor | MCP server | AI sees k-os tools automatically |
| Windsurf | MCP server | AI sees k-os tools automatically |
| Continue (VS Code) | MCP server | AI sees k-os tools automatically |
| Codex CLI (OpenAI) | MCP server | AI sees k-os tools automatically |
| Antigravity (Google) | MCP server | AI sees k-os tools automatically |

The MCP server exposes 5 tools: `k-os-query`, `k-os-scan`, `k-os-compile`, `k-os-rebuild`, `k-os-status`.

```bash
# Manual MCP setup (if needed)
k-os install --mcp    # shows JSON/TOML config to paste
k-os mcp              # start MCP server directly
```

## Project Structure

```
k-os                 # CLI entry point (works on all platforms)
k-os.bat             # Windows batch wrapper
src/
├── ingestion/       # File scanning, state tracking
│   └── parsers/     # Markdown, code AST, PDF parsers
├── compiler/        # Knowledge object compilation, ontology, abstractions
├── indexing/        # Qdrant, OpenSearch, Neo4j clients + manager
├── retrieval/       # Search coordinator, RRF reranking, context builder
├── planner/         # Intent classification, query planning
├── adapters/        # Model-specific formatters (XML, Markdown, JSON)
├── pipeline.py      # End-to-end orchestrator
└── mcp_server.py    # MCP server for AI CLI integration

scripts/
├── install.sh       # Global installer (macOS/Linux/WSL)
├── install.ps1      # Global installer (Windows PowerShell)
├── db_setup.sh      # Database bootstrap
└── db_setup.py      # Cross-platform database setup

config/              # settings.yaml, .knowledgeignore
docker/              # docker-compose.yml for Neo4j, Qdrant, OpenSearch
```

## Supported Models

| Model | Format | Token Budget |
|-------|--------|-------------|
| Claude | XML with ontology hierarchy | 150,000 |
| GPT | Structured Markdown | 8,000 |
| GPT-5 | Structured Markdown | 128,000 |
| Codex | Minimal comments + raw code | 8,000 |
| Qwen | Compact JSON | 32,000 |
| Gemini | Markdown with tables | 128,000 |

## Key Design Decisions

- **No fixed chunking** — abstraction levels replace arbitrary splits
- **Algorithmic first** — no LLM required, uses algorithmic abstraction generation
- **Incremental updates** — SHA-256 hashing skips unchanged files
- **Multi-signal retrieval** — dense + sparse + graph, fused with RRF
- **Model-agnostic** — adapter pattern for any downstream LLM

## Requirements

- Python 3.11+
- Docker (for Neo4j, Qdrant, OpenSearch)
- No LLM required (uses algorithmic abstraction)

## License

MIT
