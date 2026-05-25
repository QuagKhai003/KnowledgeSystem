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
LAUNCHER="/usr/local/bin/k-os"
NEEDS_SUDO=false

if [ ! -w "$(dirname "$LAUNCHER")" ]; then
    NEEDS_SUDO=true
fi

LAUNCHER_CONTENT="#!/usr/bin/env bash
# Knowledge OS global launcher — installed by install.sh
INSTALL_DIR=\"${INSTALL_DIR}\"
VENV=\"\${INSTALL_DIR}/.venv/bin/python\"
FALLBACK=\"python3\"

if [ -f \"\$VENV\" ]; then
    exec \"\$VENV\" \"\${INSTALL_DIR}/k-os\" \"\$@\"
else
    exec \$FALLBACK \"\${INSTALL_DIR}/k-os\" \"\$@\"
fi
"

if [ "$NEEDS_SUDO" = true ]; then
    echo "Need sudo to install to /usr/local/bin"
    echo "$LAUNCHER_CONTENT" | sudo tee "$LAUNCHER" > /dev/null
    sudo chmod +x "$LAUNCHER"
else
    echo "$LAUNCHER_CONTENT" > "$LAUNCHER"
    chmod +x "$LAUNCHER"
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
# Knowledge OS Query

Run a knowledge query against the user's indexed vault using the Knowledge OS system.

Usage: /k-os <query>

Execute the query by running:
```
k-os query "$ARGUMENTS" -m claude --live
```

If that fails (k-os not in PATH), try:
```
$INSTALL_DIR/.venv/bin/python $INSTALL_DIR/k-os query "$ARGUMENTS" -m claude --live
```

Show the results to the user. If databases aren't running, suggest: `docker compose -f $INSTALL_DIR/docker/docker-compose.yml up -d`
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

# 6. Check Docker and start databases
if ! command -v docker &> /dev/null; then
    echo ""
    echo "ERROR: Docker is required but not found." >&2
    echo "  Install Docker Desktop from https://www.docker.com/products/docker-desktop/"
    echo "  Then re-run this script."
    exit 1
fi

echo ""
echo "Starting databases..."
docker compose -f "${INSTALL_DIR}/docker/docker-compose.yml" up -d
echo "Waiting for databases to be ready..."
sleep 15

# Health checks
READY=true
curl -sf http://localhost:6333/healthz > /dev/null 2>&1 && echo "  Qdrant: ready" || { echo "  Qdrant: not ready yet"; READY=false; }
curl -sf http://localhost:9200 > /dev/null 2>&1 && echo "  OpenSearch: ready" || { echo "  OpenSearch: not ready yet"; READY=false; }
curl -sf http://localhost:7474 > /dev/null 2>&1 && echo "  Neo4j: ready" || { echo "  Neo4j: not ready yet"; READY=false; }

if [ "$READY" = false ]; then
    echo ""
    echo "  Some databases are still starting. Wait ~30s and they should be ready."
fi

echo ""
echo "=== Installation complete ==="
echo ""
echo "Usage from any directory:"
echo "  k-os -w /path/to/vault rebuild -v     # index a vault"
echo "  k-os query \"your question\" --live     # query knowledge"
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
