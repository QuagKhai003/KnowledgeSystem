#!/usr/bin/env bash
set -euo pipefail

# Knowledge OS — global installer for macOS / Linux / WSL / Git Bash

KOS_VERSION="0.1.0"
CONFIG_DIR="$HOME/.k-os"
CONFIG_FILE="$CONFIG_DIR/config.yaml"

echo "=== Knowledge OS Installer v${KOS_VERSION} ==="

# Detect install path (where this repo lives)
if [ -n "${KOS_INSTALL_DIR:-}" ]; then
    INSTALL_DIR="$KOS_INSTALL_DIR"
elif [ -f "$(dirname "$0")/../k-os" ]; then
    INSTALL_DIR="$(cd "$(dirname "$0")/.." && pwd)"
else
    echo "Error: Run this from the KnowledgeSystem repo, or set KOS_INSTALL_DIR"
    exit 1
fi

echo "Install dir: $INSTALL_DIR"

# 1. Create global config directory
mkdir -p "$CONFIG_DIR"

# 2. Write global config (preserve existing)
if [ ! -f "$CONFIG_FILE" ]; then
    cat > "$CONFIG_FILE" << EOF
install_dir: "${INSTALL_DIR}"
default_vault: ""
databases:
  neo4j:
    uri: bolt://localhost:7687
    user: neo4j
    password: knowledge_os
  qdrant:
    host: localhost
    port: 6333
  opensearch:
    host: localhost
    port: 9200
EOF
    echo "Created config: $CONFIG_FILE"
else
    # Update install_dir in existing config
    sed -i.bak "s|^install_dir:.*|install_dir: \"${INSTALL_DIR}\"|" "$CONFIG_FILE"
    rm -f "${CONFIG_FILE}.bak"
    echo "Updated config: $CONFIG_FILE"
fi

# 3. Create global launcher script
BIN_DIR="$HOME/.local/bin"
mkdir -p "$BIN_DIR"
LAUNCHER="$BIN_DIR/k-os"

cat > "$LAUNCHER" << EOF
#!/usr/bin/env bash
# Knowledge OS global launcher — installed by install.sh
INSTALL_DIR="${INSTALL_DIR}"
VENV="\${INSTALL_DIR}/.venv/bin/python"

if [ -f "\$VENV" ]; then
    exec "\$VENV" "\${INSTALL_DIR}/k-os" "\$@"
else
    exec python3 "\${INSTALL_DIR}/k-os" "\$@"
fi
EOF
chmod +x "$LAUNCHER"

# Ensure ~/.local/bin is in PATH
if [[ ":$PATH:" != *":$BIN_DIR:"* ]]; then
    for rc in "$HOME/.bashrc" "$HOME/.zshrc"; do
        if [ -f "$rc" ] && ! grep -q '.local/bin' "$rc"; then
            echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$rc"
        fi
    done
    export PATH="$BIN_DIR:$PATH"
fi
echo "Installed launcher: $LAUNCHER"

# 4. Configure AI CLI integrations
PYTHON_BIN="${INSTALL_DIR}/.venv/bin/python"
MCP_SCRIPT="${INSTALL_DIR}/src/mcp_server.py"
MCP_ENTRY="{\"command\":\"${PYTHON_BIN}\",\"args\":[\"${MCP_SCRIPT}\"]}"

configure_mcp() {
    local name="$1"
    local config_file="$2"
    local key_path="$3"

    mkdir -p "$(dirname "$config_file")"

    if [ -f "$config_file" ]; then
        if command -v python3 &> /dev/null; then
            python3 -c "
import json, sys
cfg = json.load(open('$config_file'))
keys = '$key_path'.split('.')
obj = cfg
for k in keys[:-1]:
    obj = obj.setdefault(k, {})
obj[keys[-1]] = json.loads('$MCP_ENTRY')
json.dump(cfg, open('$config_file', 'w'), indent=2)
"
        fi
    else
        python3 -c "
import json
keys = '$key_path'.split('.')
cfg = {}
obj = cfg
for k in keys[:-1]:
    obj[k] = {}
    obj = obj[k]
obj[keys[-1]] = json.loads('$MCP_ENTRY')
json.dump(cfg, open('$config_file', 'w'), indent=2)
"
    fi
    echo "  $name: configured"
}

echo "Configuring AI CLI integrations..."

# Claude Code — slash command
CLAUDE_CMD_DIR="$HOME/.claude/commands"
mkdir -p "$CLAUDE_CMD_DIR"

cat > "$CLAUDE_CMD_DIR/k-os.md" << 'CMDEOF'
# Knowledge OS

Run Knowledge OS commands against any folder.

## Usage

`/k-os <command> [args]`

## Commands

| Command | Example | Description |
|---------|---------|-------------|
| `rebuild <path>` | `/k-os rebuild /path/to/vault` | Full pipeline: scan, compile, index a folder |
| `query <question>` | `/k-os query what is cryptography` | Query your knowledge base |
| `scan <path>` | `/k-os scan /path/to/folder` | Scan folder for files (dry run) |
| `compile <path>` | `/k-os compile /path/to/folder` | Compile files into Knowledge Objects |
| `status` | `/k-os status` | Show database summary |
| `help` | `/k-os help` | Show this help |

If no command is given, show this help.

## Execution

Parse the first word of `$ARGUMENTS` as the command.

- **rebuild**: run `k-os -w <path> rebuild -v`
- **query**: run `k-os query "<question>"`. The output contains file pointers — read the listed files to answer the question.
- **scan**: run `k-os -w <path> scan -v`
- **compile**: run `k-os -w <path> compile --json`
- **status**: run `k-os status`
- **help** or empty: display the commands table above

If `k-os` is not in PATH, use the full path:
```
$INSTALL_DIR/.venv/bin/python $INSTALL_DIR/k-os
```

If databases aren't running, suggest:
```
docker compose -f $INSTALL_DIR/docker/docker-compose.yml up -d
```
CMDEOF

sed -i.bak "s|\$INSTALL_DIR|${INSTALL_DIR}|g" "$CLAUDE_CMD_DIR/k-os.md"
rm -f "$CLAUDE_CMD_DIR/k-os.md.bak"
echo "  Claude Code: /k-os slash command installed"

# Claude Code — MCP server
CLAUDE_MCP="$HOME/.claude/settings.json"
if [ -d "$HOME/.claude" ]; then
    configure_mcp "Claude Code MCP" "$CLAUDE_MCP" "mcpServers.knowledge-os"
fi

# Cursor — MCP server
CURSOR_MCP="$HOME/.cursor/mcp.json"
if [ -d "$HOME/.cursor" ] || command -v cursor &> /dev/null; then
    configure_mcp "Cursor" "$CURSOR_MCP" "mcpServers.knowledge-os"
fi

# Windsurf — MCP server
WINDSURF_MCP="$HOME/.codeium/windsurf/mcp_config.json"
if [ -d "$HOME/.codeium/windsurf" ] || command -v windsurf &> /dev/null; then
    configure_mcp "Windsurf" "$WINDSURF_MCP" "mcpServers.knowledge-os"
fi

# VS Code + Continue — MCP server
CONTINUE_MCP="$HOME/.continue/config.json"
if [ -d "$HOME/.continue" ]; then
    configure_mcp "Continue" "$CONTINUE_MCP" "mcpServers.knowledge-os"
fi

# Codex CLI (OpenAI) — TOML config
CODEX_CONFIG="$HOME/.codex/config.toml"
if [ -d "$HOME/.codex" ] || command -v codex &> /dev/null; then
    mkdir -p "$HOME/.codex"
    # Append MCP server block if not already present
    if [ -f "$CODEX_CONFIG" ] && grep -q "mcp_servers.knowledge-os" "$CODEX_CONFIG" 2>/dev/null; then
        echo "  Codex CLI: already configured"
    else
        cat >> "$CODEX_CONFIG" << EOF

[mcp_servers.knowledge-os]
enabled = true
command = "${PYTHON_BIN}"
args = ["${MCP_SCRIPT}"]
EOF
        echo "  Codex CLI: configured"
    fi
fi

# Antigravity (Google/Gemini CLI) — MCP server
ANTIGRAVITY_MCP="$HOME/.gemini/config/mcp_config.json"
if [ -d "$HOME/.gemini" ] || command -v antigravity &> /dev/null || [ -d "$HOME/.antigravitycli" ]; then
    configure_mcp "Antigravity" "$ANTIGRAVITY_MCP" "mcpServers.knowledge-os"
fi

# 5. Set up Python virtual environment and install dependencies
if [ ! -d "${INSTALL_DIR}/.venv" ]; then
    echo "Setting up Python venv..."
    python3 -m venv "${INSTALL_DIR}/.venv"
fi
echo "Installing dependencies..."
"${INSTALL_DIR}/.venv/bin/pip" install -q -r "${INSTALL_DIR}/requirements.txt" 2>/dev/null || \
    "${INSTALL_DIR}/.venv/bin/pip" install -q pyyaml
echo "Virtual environment ready"

# 6. Optional: Docker databases for semantic search + graph traversal
if command -v docker &> /dev/null; then
    echo ""
    echo "Docker found. Starting optional databases (Qdrant + Neo4j)..."
    docker compose -f "${INSTALL_DIR}/docker/docker-compose.yml" up -d
    echo "Waiting for databases to be ready..."
    sleep 15

    # Health checks
    curl -sf http://localhost:6333/healthz > /dev/null 2>&1 && echo "  Qdrant: ready" || echo "  Qdrant: not ready yet (wait ~30s)"
    curl -sf http://localhost:7474 > /dev/null 2>&1 && echo "  Neo4j: ready" || echo "  Neo4j: not ready yet (wait ~30s)"
else
    echo ""
    echo "Docker not found — skipping optional databases."
    echo "  k-os works fully with keyword search (SQLite FTS5, built-in)."
    echo "  For semantic search + graph traversal, install Docker and run:"
    echo "    docker compose -f ${INSTALL_DIR}/docker/docker-compose.yml up -d"
fi

echo ""
echo "=== Installation complete ==="
echo ""
echo "Usage from any directory:"
echo "  k-os -w /path/to/vault rebuild -v     # index a folder"
echo "  k-os query \"your question\"             # query knowledge (returns file pointers)"
echo ""
echo "In any AI CLI:"
echo "  Claude Code:   /k-os what is cryptography"
echo "  Cursor:        uses k-os tools automatically (MCP)"
echo "  Windsurf:      uses k-os tools automatically (MCP)"
echo "  Continue:      uses k-os tools automatically (MCP)"
echo "  Codex CLI:     uses k-os tools automatically (MCP)"
echo "  Antigravity:   uses k-os tools automatically (MCP)"
echo ""
echo "Config: $CONFIG_FILE"
