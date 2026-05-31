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
4. **Stay fresh automatically** — registered workspaces are incrementally updated on every query; git hooks can trigger indexing on each commit

The AI gets the full source material with zero information loss.

```
Any Text File → Parse → Knowledge Object → Abstractions → Index → Query → File Pointer → AI Reads Raw File
```

## Getting Started

### Prerequisites

- Python 3.11+
- Git

Docker is **not required**. The core system (keyword search, indexing, auto-update) runs entirely on SQLite FTS5 with zero external dependencies. Docker is only needed if you want optional semantic vector search (Qdrant) or graph traversal (Neo4j).

### Installation

#### Option A: Without Docker (default — works immediately)

**macOS / Linux / WSL / Git Bash:**

```bash
# 1. Run the one-line installer
curl -fsSL https://raw.githubusercontent.com/QuagKhai003/KnowledgeSystem/master/scripts/bootstrap.sh | bash

# 2. Restart your terminal (or source your shell profile)
source ~/.bashrc   # or: source ~/.zshrc

# 3. Verify installation
k-os status

# 4. Index your first folder
k-os -w /path/to/your/folder rebuild -v

# 5. Query your knowledge base
k-os query "your question here"
```

**Windows (PowerShell 5.1+):**

```powershell
# 1. Run the one-line installer
irm https://raw.githubusercontent.com/QuagKhai003/KnowledgeSystem/master/scripts/bootstrap.ps1 | iex

# 2. Restart your terminal (PATH update takes effect)

# 3. Verify installation
k-os status

# 4. Index your first folder
k-os -w C:\path\to\your\folder rebuild -v

# 5. Query your knowledge base
k-os query "your question here"
```

**What the installer does:**
1. Clones the repository to `~/.k-os/KnowledgeSystem`
2. Creates a Python virtual environment and installs dependencies
3. Registers the `k-os` command globally (`~/.local/bin/k-os` on Unix, `~/.k-os/bin/k-os.cmd` on Windows)
4. Configures AI CLI integrations (Claude Code slash command + MCP servers for Cursor, Windsurf, Continue, Codex, Antigravity)

This gives you the full pipeline: scan, compile, index, query, hubs, graph, git hooks, and all AI CLI integrations.

---

#### Option B: With Docker (adds semantic search + graph traversal)

**macOS / Linux / WSL / Git Bash:**

```bash
# 1. Ensure Docker is running
docker info

# 2. Run the one-line installer (auto-detects Docker and starts containers)
curl -fsSL https://raw.githubusercontent.com/QuagKhai003/KnowledgeSystem/master/scripts/bootstrap.sh | bash

# 3. Restart your terminal
source ~/.bashrc   # or: source ~/.zshrc

# 4. Verify everything is running
k-os status
docker ps   # Should show qdrant and neo4j containers

# 5. Index and query
k-os -w /path/to/your/folder rebuild -v
k-os query "your question here"
```

**Windows (PowerShell 5.1+):**

```powershell
# 1. Ensure Docker Desktop is running
docker info

# 2. Run the one-line installer (auto-detects Docker and starts containers)
irm https://raw.githubusercontent.com/QuagKhai003/KnowledgeSystem/master/scripts/bootstrap.ps1 | iex

# 3. Restart your terminal

# 4. Verify everything is running
k-os status
docker ps   # Should show qdrant and neo4j containers

# 5. Index and query
k-os -w C:\path\to\your\folder rebuild -v
k-os query "your question here"
```

**What Docker adds:**
- **Qdrant** (vector database) — enables semantic search that finds conceptually similar files even when keywords don't match
- **Neo4j** (graph database) — enables graph traversal queries to explore transitive dependencies

**Adding Docker later** (if you installed without it first):

```bash
# Start the containers
docker compose -f ~/.k-os/KnowledgeSystem/docker/docker-compose.yml up -d

# Verify health
curl -sf http://localhost:6333/healthz   # Qdrant
curl -sf http://localhost:7474           # Neo4j

# Re-index to populate vector and graph stores
k-os -w /path/to/your/folder rebuild -v
```

**Custom ports** (avoid conflicts with other Docker services):

```bash
NEO4J_HTTP_PORT=17474 NEO4J_BOLT_PORT=17687 QDRANT_HTTP_PORT=16333 QDRANT_GRPC_PORT=16334 \
  docker compose -f ~/.k-os/KnowledgeSystem/docker/docker-compose.yml up -d
```

---

#### Comparison

| Tier | Requirement | Capabilities |
|------|-------------|--------------|
| **Core** | Python + Git | BM25 keyword search, hub detection, graph visualization, auto-indexing, git hooks |
| **+ Qdrant** | Docker | Dense vector semantic search (finds conceptually similar files) |
| **+ Neo4j** | Docker | Graph traversal queries (find all transitive dependencies) |

### Quick Start

```bash
# Index a folder
k-os -w /path/to/your/folder rebuild -v

# Query your knowledge base
k-os query "What is cryptography?"

# Use within Claude Code or any supported AI CLI
/k-os query what is cryptography

# See which files are architectural hubs
k-os hubs

# Generate an interactive dependency graph
k-os graph
```

## How It Works

### 1. Scan

Point `k-os` at any folder. The scanner reads every file and classifies it automatically:

- **Tree-sitter AST** for 30+ programming languages — extracts classes, functions, methods, imports, and comments with full structural understanding
- **Python AST** for `.py` files — native `ast` module for maximum accuracy
- **Markdown parser** for `.md` — wikilinks, frontmatter, heading hierarchy
- **PDF layout extractor** for `.pdf` — page text, outline, heading detection
- **Universal text parser** for everything else — any UTF-8 readable file (`.txt`, `.yaml`, `.toml`, `.csv`, `.sql`, config files, logs, etc.)
- **Binary files** (images, audio, archives, compiled objects) are skipped automatically

SHA-256 hashing ensures only changed files are reprocessed. Registered workspaces are auto-updated on every query, so the index is never stale.

### Supported Languages

| Parser | Languages |
|--------|-----------|
| Python AST | Python |
| Tree-sitter | JavaScript, TypeScript, JSX, TSX, Go, Rust, Java, C, C++, C#, Ruby, Bash |
| Universal text | Any UTF-8 readable file not covered above |

Tree-sitter grammars are modular — adding a new language requires only installing its grammar package.

### 2. Compile

Each file is compiled into a Knowledge Object with four abstraction levels:

| Level | Content | Method |
|-------|---------|--------|
| L0 | Full raw content | Verbatim storage |
| L1 | Structural outline | Headings (docs), class/function signatures (code), first sentences (text) |
| L2 | Concept summary (800 chars) | Docstrings + comments (code), key topics + sampled passages (docs) |
| L3 | Keywords (100 terms) | TF-IDF with bigrams, proper nouns, and identifier extraction |

For code files, the compiler extracts natural language from docstrings, comments, and identifier names (`calculateTotalPrice` → "calculate total price") to make code searchable by concept, not just symbol name.

Each object is assigned an ontology class, domain, tags, and dependency relationships. Relationships are persisted as edges in the index for hub detection and graph visualization.

### 3. Index

Knowledge Objects are indexed into a tiered storage architecture:

| Engine | Search Type | Requirement |
|--------|-------------|-------------|
| SQLite FTS5 | BM25 keyword search + edge graph | Built-in (no dependencies) |
| Qdrant | Dense vector semantic search | Docker (optional) |
| Neo4j | Graph traversal for related concepts | Docker (optional) |

The basic tier (SQLite FTS5) works out of the box with no external dependencies. Docker ports are configurable in `settings.yaml` to avoid conflicts with other services.

### 4. Query

Queries are matched against the index and return ranked file pointers containing:

- **File path** to the source document
- **Matched terms** explaining why the file is relevant
- **Section headings** to guide the reader to specific content
- **Relevance score** based on BM25 ranking

Before searching, all registered workspaces are incrementally scanned for new or changed files. If nothing changed, this adds negligible overhead. If files were added or modified, they're compiled and indexed automatically — no manual rebuild needed.

The AI reads the raw files directly, preserving full context and eliminating compression artifacts.

## CLI Reference

```bash
# Core pipeline
k-os -w <path> rebuild -v        # Full pipeline: scan, compile, index
k-os -w <path> update -v         # Incremental: index only changed files
k-os -w <path> scan -v           # Scan folder for files (dry run)
k-os -w <path> compile --json    # Compile files into Knowledge Objects

# Search and analysis
k-os query "question"            # Query and return file pointers
k-os query "question" -m claude  # Query with a specific output adapter
k-os hubs                        # Show most-connected nodes (architectural hubs)
k-os graph                       # Generate interactive dependency graph HTML
k-os graph -o deps.html          # Generate graph to specific path

# Utilities
k-os status                      # Display database summary
k-os parse path/to/file.md       # Parse a single file (debug)
k-os mcp                         # Start the MCP server
k-os install --mcp               # Display MCP configuration for manual setup
k-os install --hook              # Install git post-commit hook for auto-indexing
```

The `-w` flag specifies the workspace path and must precede the subcommand.

## Auto-Indexing

Knowledge OS provides two mechanisms to keep the index fresh without manual rebuilds:

**Query-time auto-update** — Every `k-os query` automatically scans all previously rebuilt workspaces for new or changed files. Only the delta is compiled and indexed. If nothing changed, the scan adds ~0.4s.

**Git post-commit hook** — Run `k-os install --hook` in any git repository to install a post-commit hook. After each commit, changed files are indexed in the background with zero impact on git performance.

Both mechanisms use SHA-256 change detection and only reprocess files that actually changed.

## Using with AI Agents

Knowledge OS gives AI coding assistants access to your local files as a searchable knowledge base. After installation, the AI can search your indexed folders and read the original files directly — no copy-pasting needed.

### How it works with AI

1. You index a folder (once): `k-os -w /path/to/folder rebuild -v`
2. The AI queries your knowledge base and gets back file pointers (paths + why they're relevant)
3. The AI reads those files directly to answer your question with full context

The AI never sees compressed snippets — it reads your actual files. Knowledge OS just tells it *which* files to read.

### Claude Code

The installer adds a `/k-os` slash command automatically.

```
# In Claude Code, just type:
/k-os query how does authentication work

# Claude reads the returned file pointers and answers with full context
```

You can also ask Claude to use k-os directly in conversation:

```
You: "Search my notes for anything about database migrations"
Claude: (runs k-os query internally via MCP, reads the files, gives you a complete answer)
```

### Cursor / Windsurf / Continue (VS Code)

These editors connect via MCP (Model Context Protocol). After installation, tools are available automatically in the AI chat:

```
# In the AI chat panel, just ask naturally:
"What do my notes say about API rate limiting?"
"Find all files related to the payment system"
"How is the auth middleware structured in this project?"

# The AI uses k-os-query tool behind the scenes
```

Available MCP tools:
- `k-os-query` — search your knowledge base
- `k-os-rebuild` — re-index a folder
- `k-os-scan` — scan a folder (dry run)
- `k-os-compile` — compile files into Knowledge Objects
- `k-os-status` — show index statistics

### Codex CLI (OpenAI)

```bash
# Codex can call k-os tools via MCP automatically
codex "search my indexed notes for cryptography concepts"

# Or use k-os directly and pipe context to Codex
k-os query "cryptography" | codex "explain these files"
```

### Antigravity / Gemini CLI (Google)

```bash
# Same MCP integration — tools available automatically
antigravity "what files in my project handle user authentication?"
```

### Terminal-only usage (no AI agent)

k-os works standalone as a CLI tool:

```bash
# Search and get file pointers printed to terminal
k-os query "how does the build system work"

# Output shows:
#   /path/to/Makefile — matched: build, compile, target — score: 12.3
#   /path/to/docs/building.md — matched: build system, dependencies — score: 9.1

# Then read those files yourself, or feed them to any tool
cat $(k-os query "build system" --paths-only)
```

### Manual MCP setup (if auto-detection missed your tool)

```bash
# Show the MCP configuration JSON to add manually
k-os install --mcp
```

Add the output to your AI tool's MCP config file:
- Claude Code: `~/.claude/settings.json` under `mcpServers`
- Cursor: `~/.cursor/mcp.json` under `mcpServers`
- Windsurf: `~/.codeium/windsurf/mcp_config.json` under `mcpServers`
- Continue: `~/.continue/config.json` under `mcpServers`
- Codex: `~/.codex/config.toml` under `[mcp_servers.knowledge-os]`
- Antigravity: `~/.gemini/config/mcp_config.json` under `mcpServers`

### Output Adapters

Output format is auto-detected based on which AI CLI is active. Manual override:

```bash
k-os query "your question" -m claude    # Format for Claude Code
k-os query "your question" -m codex     # Format for Codex
k-os query "your question" -m gemini    # Format for Gemini
```

| Adapter | Auto-detected when |
|---------|-------------------|
| Claude | `CLAUDE_CODE` or `CLAUDE_ACCESS_TOKEN` env var present |
| Codex | `OPENAI_API_KEY` env var present |
| Gemini | `GEMINI_API_KEY` or `GOOGLE_API_KEY` env var present |
| Qwen | `DASHSCOPE_API_KEY` env var present |
| GPT | Default fallback |

Knowledge OS does not call any external APIs or language models. Adapters only control output formatting.

## Architecture

| Layer | Responsibility |
|-------|---------------|
| Ingestion | Universal file scanning with UTF-8 text detection and SHA-256 change tracking |
| Parsing | Tree-sitter AST (30+ languages), Python AST, Markdown, PDF layout, universal text fallback |
| Compilation | Knowledge Object construction with identifier-to-prose, TF-IDF keywords, formal ontology (10 classes, 7 predicates) |
| Abstraction | Four-level hierarchy: L0 (raw) → L1 (outline) → L2 (summary) → L3 (keywords) |
| Indexing | SQLite FTS5 with edge graph (default), optional Qdrant vector and Neo4j graph indexes |
| Query | BM25-ranked file pointers with auto-update, matched terms, sections, and relevance scores |
| Analysis | Hub detection (inbound edge ranking), interactive dependency graph visualization |
| Adapters | Pointer formatting tailored to target AI CLI |

## Project Structure

```
k-os                    CLI entry point
k-os.bat                Windows batch wrapper

src/
├── ingestion/          Universal file scanning and state tracking
│   └── parsers/        Tree-sitter, Python AST, Markdown, PDF, and universal text parsers
├── compiler/           Knowledge Object compilation and ontology validation
├── indexing/           SQLite FTS5 (with edges), Qdrant, and Neo4j clients
├── adapters/           Output formatters (Claude, GPT, Codex, Qwen, Gemini)
├── graph_view.py       Interactive HTML graph generator
├── pipeline.py         End-to-end orchestrator
└── mcp_server.py       MCP server for AI CLI integration

scripts/
├── bootstrap.sh        One-line installer (macOS / Linux / WSL)
├── bootstrap.ps1       One-line installer (Windows PowerShell)
├── install.sh          Full installer (bash)
├── install.ps1         Full installer (PowerShell)
└── db_setup.py         Cross-platform database health check

config/                 settings.yaml, .knowledgeignore
docker/                 docker-compose.yml (Neo4j, Qdrant — ports configurable)
```

## Design Principles

- **Any file, any format** — indexes every readable text file, not just specific extensions
- **30+ languages** — tree-sitter provides real AST parsing, not regex heuristics
- **No LLM dependency** — all abstraction is algorithmic; no API keys required
- **No Docker dependency** — SQLite FTS5 provides full keyword search out of the box
- **No fixed chunking** — abstraction levels replace arbitrary document splitting
- **Zero information loss** — queries return pointers; the AI reads raw files directly
- **Always fresh** — auto-update on query + git hooks ensure the index is never stale
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
