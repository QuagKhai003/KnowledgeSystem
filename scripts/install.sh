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

# 4. Set up Claude Code slash command (global)
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

sed -i "s|\$INSTALL_DIR|${INSTALL_DIR}|g" "$CLAUDE_CMD_DIR/k-os.md"
echo "Installed Claude Code command: /k-os"

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
echo "In Claude Code (any directory):"
echo "  /k-os what is cryptography"
echo ""
echo "Config: $CONFIG_FILE"
