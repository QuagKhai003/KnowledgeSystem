# Knowledge OS

A local-first knowledge compiler that turns any folder of files into a searchable knowledge base for AI coding assistants.

## The Problem

AI coding assistants (Claude Code, Cursor, Codex, Gemini CLI) are powerful, but they have no memory of your local files beyond what's open. When you ask a question, the AI can't search your lecture notes, project documentation, or reference material unless you manually paste it in.

Traditional RAG systems solve this by chunking documents into fragments and feeding compressed snippets to the AI. This loses context — the AI sees a paragraph, not the full document, and has no way to verify or read further.

## The Solution

Knowledge OS takes a different approach: **compile, don't chunk.**

1. **Index any folder** — point `k-os` at a folder and it scans every readable file (not just specific extensions)
2. **Compile into Knowledge Objects** — each file becomes a structured object with four abstraction levels: raw content, outline, summary, and keywords
3. **Return pointers, not passages** — queries return ranked file paths with matched terms and section headings, so the AI reads the original files directly

The AI gets the full source material with zero information loss.

```
Any Text File → Parse → Knowledge Object → Abstractions → Index → Query → File Pointer → AI Reads Raw File
```

## Getting Started

### Prerequisites

- Python 3.11+
- Git
- Docker (optional, for semantic search and graph traversal)

### Installation

```bash
# macOS / Linux / WSL / Git Bash
curl -fsSL https://raw.githubusercontent.com/QuagKhai003/KnowledgeSystem/master/scripts/bootstrap.sh | bash

# Windows (PowerShell 5.1+)
irm https://raw.githubusercontent.com/QuagKhai003/KnowledgeSystem/master/scripts/bootstrap.ps1 | iex
```

The installer handles cloning, virtual environment setup, dependency installation, global CLI registration, and AI CLI integration.

### Quick Start

```bash
# Index a folder of documents
k-os -w /path/to/your/folder rebuild -v

# Query your knowledge base
k-os query "What is cryptography?"

# Use within Claude Code or any supported AI CLI
/k-os query what is cryptography
```

## How It Works

### 1. Scan

Point `k-os` at any folder. The scanner reads every file and classifies it automatically:

- **Specialized parsers** for `.md`, `.py`, `.js`, `.ts`, `.jsx`, `.tsx`, `.pdf` — extract structure (AST, headings, frontmatter)
- **Universal text parser** for everything else — any UTF-8 readable file (`.txt`, `.yaml`, `.toml`, `.csv`, `.sql`, `.sh`, config files, logs, etc.)
- **Binary files** (images, audio, archives, compiled objects) are skipped automatically

SHA-256 hashing ensures only changed files are reprocessed on subsequent runs.

### 2. Compile

Each file is compiled into a Knowledge Object with four abstraction levels:

| Level | Content | Method |
|-------|---------|--------|
| L0 | Full raw content | Verbatim storage |
| L1 | Structural outline | Headings (docs), class/function signatures (code), first sentences (text) |
| L2 | Concept summary (800 chars) | Docstrings + comments (code), key topics + sampled passages (docs) |
| L3 | Keywords (100 terms) | TF-IDF with bigrams, proper nouns, and identifier extraction |

For code files, the compiler extracts natural language from docstrings, comments, and identifier names (`calculateTotalPrice` → "calculate total price") to make code searchable by concept, not just symbol name.

Each object is also assigned an ontology class, domain, tags, and relationship metadata.

### 3. Index

Knowledge Objects are indexed into a tiered storage architecture:

| Engine | Search Type | Requirement |
|--------|-------------|-------------|
| SQLite FTS5 | BM25 keyword search | Built-in (no dependencies) |
| Qdrant | Dense vector semantic search | Docker (optional) |
| Neo4j | Graph traversal for related concepts | Docker (optional) |

The basic tier (SQLite FTS5) works out of the box with no external dependencies.

### 4. Query

Queries are matched against the index and return ranked file pointers containing:

- **File path** to the source document
- **Matched terms** explaining why the file is relevant
- **Section headings** to guide the reader to specific content
- **Relevance score** based on BM25 ranking

The AI reads the raw files directly, preserving full context and eliminating compression artifacts.

## CLI Reference

```bash
k-os -w <path> scan -v           # Scan folder for files (dry run)
k-os -w <path> compile --json    # Compile files into Knowledge Objects
k-os -w <path> rebuild -v        # Full pipeline: scan, compile, index
k-os status                      # Display database summary
k-os parse path/to/file.md       # Parse a single file (debug)
k-os query "question"            # Query and return file pointers
k-os query "question" -m claude  # Query with a specific output adapter
k-os mcp                         # Start the MCP server
k-os install --mcp               # Display MCP configuration for manual setup
```

The `-w` flag specifies the workspace path and must precede the subcommand.

## AI CLI Integration

The installer automatically detects and configures supported AI CLIs via the [Model Context Protocol](https://modelcontextprotocol.io/) (MCP):

| AI CLI | Integration | Usage |
|--------|-------------|-------|
| Claude Code | Slash command + MCP | `/k-os query your question` |
| Cursor | MCP server | Tools available automatically |
| Windsurf | MCP server | Tools available automatically |
| Continue (VS Code) | MCP server | Tools available automatically |
| Codex CLI (OpenAI) | MCP server | Tools available automatically |
| Antigravity (Google) | MCP server | Tools available automatically |

MCP exposes five tools: `k-os-query`, `k-os-scan`, `k-os-compile`, `k-os-rebuild`, and `k-os-status`.

## Output Adapters

The output adapter is auto-detected based on the active AI CLI environment. Manual override is available via the `-m` flag.

| Adapter | Detection |
|---------|-----------|
| Claude | `CLAUDE_CODE` or `CLAUDE_ACCESS_TOKEN` environment variable |
| Codex | `OPENAI_API_KEY` environment variable |
| Gemini | `GEMINI_API_KEY` or `GOOGLE_API_KEY` environment variable |
| Qwen | `DASHSCOPE_API_KEY` environment variable |
| GPT | Default fallback |

Adapters control how file pointers are formatted for each AI CLI. Knowledge OS does not call any external APIs or language models.

## Architecture

| Layer | Responsibility |
|-------|---------------|
| Ingestion | Universal file scanning with UTF-8 text detection and SHA-256 change tracking |
| Parsing | Markdown (wikilinks, frontmatter), Python AST (docstrings, comments), PDF layout, universal text fallback |
| Compilation | Knowledge Object construction with identifier-to-prose, TF-IDF keywords, formal ontology (10 classes, 7 predicates) |
| Abstraction | Four-level hierarchy: L0 (raw) → L1 (outline) → L2 (summary) → L3 (keywords) |
| Indexing | SQLite FTS5 (default) with optional Qdrant vector and Neo4j graph indexes |
| Query | BM25-ranked file pointers with matched terms, sections, and relevance scores |
| Adapters | Pointer formatting tailored to target AI CLI |

## Project Structure

```
k-os                    CLI entry point
k-os.bat                Windows batch wrapper

src/
├── ingestion/          Universal file scanning and state tracking
│   └── parsers/        Markdown, code AST, PDF, and universal text parsers
├── compiler/           Knowledge Object compilation and ontology validation
├── indexing/           SQLite FTS5, Qdrant, and Neo4j clients
├── adapters/           Output formatters (Claude, GPT, Codex, Qwen, Gemini)
├── pipeline.py         End-to-end orchestrator
└── mcp_server.py       MCP server for AI CLI integration

scripts/
├── bootstrap.sh        One-line installer (macOS / Linux / WSL)
├── bootstrap.ps1       One-line installer (Windows PowerShell)
├── install.sh          Full installer (bash)
├── install.ps1         Full installer (PowerShell)
└── db_setup.py         Cross-platform database health check

config/                 settings.yaml, .knowledgeignore
docker/                 docker-compose.yml (Neo4j, Qdrant)
```

## Design Principles

- **Any file, any format** — indexes every readable text file, not just specific extensions
- **No LLM dependency** — all abstraction is algorithmic; no API keys required
- **No Docker dependency** — SQLite FTS5 provides full keyword search out of the box
- **No fixed chunking** — abstraction levels replace arbitrary document splitting
- **Zero information loss** — queries return pointers; the AI reads raw files directly
- **Incremental processing** — SHA-256 hashing ensures only changed files are reprocessed
- **Tiered infrastructure** — scales from SQLite-only to SQLite + Qdrant + Neo4j
- **Model-agnostic output** — adapter pattern formats results for any AI CLI
- **Global indexes** — index multiple folders and query across all of them

## Uninstall

### macOS / Linux / WSL

```bash
# Stop and remove database containers
docker compose -f ~/.k-os/KnowledgeSystem/docker/docker-compose.yml down -v

# Remove global CLI
rm -f ~/.local/bin/k-os

# Remove all Knowledge OS data and configuration
rm -rf ~/.k-os

# Remove Claude Code slash command
rm -f ~/.claude/commands/k-os.md
```

Remove the `knowledge-os` entry from any of the following MCP configuration files, if present:

- `~/.claude/settings.json`
- `~/.cursor/mcp.json`
- `~/.codeium/windsurf/mcp_config.json`
- `~/.continue/config.json`
- `~/.codex/config.toml`
- `~/.gemini/config/mcp_config.json`

### Windows (PowerShell)

```powershell
# Stop and remove database containers
docker compose -f "$env:USERPROFILE\.k-os\KnowledgeSystem\docker\docker-compose.yml" down -v

# Remove all Knowledge OS data, configuration, and global CLI
Remove-Item -Recurse -Force "$env:USERPROFILE\.k-os"

# Remove from PATH
$path = [Environment]::GetEnvironmentVariable("Path", "User")
$path = ($path -split ";" | Where-Object { $_ -notlike "*\.k-os\bin*" }) -join ";"
[Environment]::SetEnvironmentVariable("Path", $path, "User")

# Remove Claude Code slash command
Remove-Item -Force "$env:USERPROFILE\.claude\commands\k-os.md" -ErrorAction SilentlyContinue
```

Remove the `knowledge-os` entry from the same MCP configuration files listed above.