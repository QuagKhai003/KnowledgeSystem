#!/usr/bin/env bash
set -uo pipefail

# Knowledge OS — one-command uninstaller for macOS / Linux / WSL / Git Bash
# Usage: curl -fsSL https://raw.githubusercontent.com/QuagKhai003/KnowledgeSystem/master/scripts/uninstall.sh | bash
#
# Reads the install manifest written at install time and reverses every change:
# Docker containers, MCP config entries, the Claude slash command, the launcher,
# the PATH lines, and the ~/.k-os directory. No manual cleanup required.

KOS_HOME="$HOME/.k-os"
MANIFEST_FILE="$KOS_HOME/install-manifest.json"

echo "=== Knowledge OS Uninstaller ==="

if ! command -v python3 &> /dev/null; then
    echo "ERROR: python3 is required to parse the manifest." >&2
    exit 1
fi

# Pull individual fields out of the manifest (empty string if missing)
get_field() {
    if [ -f "$MANIFEST_FILE" ]; then
        python3 -c "import json,sys; d=json.load(open('$MANIFEST_FILE')); print(d.get('$1',''))" 2>/dev/null
    fi
}

COMPOSE_FILE="$(get_field compose_file)"
DOCKER="$(get_field docker)"
LAUNCHER="$(get_field launcher)"
CLAUDE_CMD="$(get_field claude_command)"
KOS_HOME_M="$(get_field kos_home)"
[ -z "$KOS_HOME_M" ] && KOS_HOME_M="$KOS_HOME"
[ -z "$COMPOSE_FILE" ] && COMPOSE_FILE="$KOS_HOME/KnowledgeSystem/docker/docker-compose.yml"
[ -z "$LAUNCHER" ] && LAUNCHER="$HOME/.local/bin/k-os"
[ -z "$CLAUDE_CMD" ] && CLAUDE_CMD="$HOME/.claude/commands/k-os.md"

# 1. Stop and remove Docker containers (best effort; needs compose file + daemon)
if [ "$DOCKER" = "True" ] || [ "$DOCKER" = "true" ]; then
    if [ -f "$COMPOSE_FILE" ] && command -v docker &> /dev/null && docker info &> /dev/null; then
        echo "Stopping Docker databases..."
        docker compose -f "$COMPOSE_FILE" down -v 2>/dev/null || true
    fi
fi

# 2. Remove our MCP entries from shared editor configs (leave other entries intact)
if [ -f "$MANIFEST_FILE" ]; then
    python3 - "$MANIFEST_FILE" << 'PYEOF'
import json, os, re, sys
manifest = json.load(open(sys.argv[1]))
for edit in manifest.get("mcp_edits", []):
    path, key_path, fmt = edit.get("file"), edit.get("key_path"), edit.get("format")
    if not path or not os.path.exists(path):
        continue
    try:
        if fmt == "toml":
            lines = open(path).read().splitlines()
            out, skip = [], False
            section = re.compile(r"^\s*\[" + re.escape(key_path) + r"\]\s*$")
            for line in lines:
                if line.lstrip().startswith("["):
                    skip = bool(section.match(line))
                if not skip:
                    out.append(line)
            open(path, "w").write("\n".join(out).rstrip() + "\n")
        else:
            cfg = json.load(open(path))
            keys = key_path.split(".")
            obj = cfg
            ok = True
            for k in keys[:-1]:
                if isinstance(obj, dict) and k in obj:
                    obj = obj[k]
                else:
                    ok = False
                    break
            if ok and isinstance(obj, dict):
                obj.pop(keys[-1], None)
                # prune now-empty parent container
                if len(keys) >= 2:
                    parent = cfg
                    for k in keys[:-2]:
                        parent = parent[k]
                    if not parent.get(keys[-2]):
                        parent.pop(keys[-2], None)
                json.dump(cfg, open(path, "w"), indent=2)
        print(f"  Cleaned MCP entry: {path}")
    except Exception as e:
        print(f"  Skipped {path}: {e}")
PYEOF
fi

# 3. Remove standalone files we created (slash command, launcher, manifest extras)
for f in "$CLAUDE_CMD" "$LAUNCHER"; do
    if [ -n "$f" ] && [ -f "$f" ]; then
        rm -f "$f"
        echo "  Removed: $f"
    fi
done
if [ -f "$MANIFEST_FILE" ]; then
    while IFS= read -r f; do
        [ -n "$f" ] && [ -f "$f" ] && rm -f "$f" && echo "  Removed: $f"
    done < <(python3 -c "import json; [print(x) for x in json.load(open('$MANIFEST_FILE')).get('files',[])]" 2>/dev/null)
fi

# 4. Remove the PATH export lines we appended to shell rc files
for rc in "$HOME/.bashrc" "$HOME/.zshrc"; do
    if [ -f "$rc" ] && grep -q 'export PATH="$HOME/.local/bin:$PATH"' "$rc"; then
        tmp="$(mktemp)"
        grep -v 'export PATH="$HOME/.local/bin:$PATH"' "$rc" > "$tmp" && mv "$tmp" "$rc"
        echo "  Cleaned PATH line in: $rc"
    fi
done

# 5. Remove the entire Knowledge OS home (repo, venv, config, manifest)
if [ -n "$KOS_HOME_M" ] && [ -d "$KOS_HOME_M" ]; then
    rm -rf "$KOS_HOME_M"
    echo "  Removed: $KOS_HOME_M"
fi

echo ""
echo "=== Knowledge OS uninstalled ==="
echo "Restart your terminal to clear any PATH changes."
