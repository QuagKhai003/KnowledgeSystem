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
    echo "ERROR: Docker is required." >&2
    echo "  Install Docker Desktop from https://www.docker.com/products/docker-desktop/"
    echo "  Then re-run:"
    echo '  curl -fsSL https://raw.githubusercontent.com/QuagKhai003/KnowledgeSystem/master/scripts/bootstrap.sh | bash'
    exit 1
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
