#!/usr/bin/env bash
set -euo pipefail

# Knowledge OS — one-line installer
# Usage: curl -fsSL https://raw.githubusercontent.com/QuagKhai003/KnowledgeSystem/master/scripts/bootstrap.sh | bash

KOS_HOME="$HOME/.k-os"
KOS_REPO="$KOS_HOME/KnowledgeSystem"
REPO_URL="https://github.com/QuagKhai003/KnowledgeSystem.git"

echo "=== Knowledge OS Bootstrap ==="
echo ""

# Check prerequisites
if ! command -v git &> /dev/null; then
    echo "ERROR: git is required. Install git first." >&2
    exit 1
fi

if ! command -v python3 &> /dev/null; then
    echo "ERROR: python3 is required. Install Python 3.11+ first." >&2
    exit 1
fi

if ! command -v docker &> /dev/null; then
    echo "NOTE: Docker not found — optional databases (semantic search, graph) will be skipped."
    echo "  k-os works fully with keyword search (SQLite FTS5, built-in)."
    echo "  To add semantic search later, install Docker and run:"
    echo "    docker compose -f ~/.k-os/KnowledgeSystem/docker/docker-compose.yml up -d"
    echo ""
fi

# Clone or update repo
if [ -d "$KOS_REPO" ]; then
    echo "Updating existing installation..."
    git -C "$KOS_REPO" pull --quiet
else
    echo "Downloading Knowledge OS..."
    mkdir -p "$KOS_HOME"
    git clone --quiet "$REPO_URL" "$KOS_REPO"
fi

# Run the full install script
echo ""
export KOS_INSTALL_DIR="$KOS_REPO"
bash "$KOS_REPO/scripts/install.sh"
