#!/usr/bin/env python3
"""Cross-platform database setup: starts Docker containers and waits for readiness."""

import subprocess
import sys
import time
import urllib.request
from pathlib import Path

try:
    import yaml
except ImportError:
    yaml = None

PROJECT_ROOT = Path(__file__).parent.parent
COMPOSE_FILE = PROJECT_ROOT / "docker" / "docker-compose.yml"
CONFIG_FILE = PROJECT_ROOT / "config" / "settings.yaml"


def run(cmd: list[str]) -> tuple[int, str]:
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.returncode, result.stdout + result.stderr


def load_ports() -> dict:
    defaults = {"neo4j_http": 7474, "neo4j_bolt": 7687, "qdrant_http": 6333}
    if yaml is None or not CONFIG_FILE.exists():
        return defaults
    try:
        cfg = yaml.safe_load(CONFIG_FILE.read_text())
        db = cfg.get("databases", {})
        neo4j_uri = db.get("neo4j", {}).get("uri", "")
        if ":" in neo4j_uri:
            defaults["neo4j_bolt"] = int(neo4j_uri.rsplit(":", 1)[-1])
        qdrant_port = db.get("qdrant", {}).get("port")
        if qdrant_port:
            defaults["qdrant_http"] = int(qdrant_port)
    except Exception:
        pass
    return defaults


def wait_for_url(url: str, name: str, timeout: int = 30):
    print(f"  Waiting for {name}...", end="", flush=True)
    for _ in range(timeout):
        try:
            urllib.request.urlopen(url, timeout=2)
            print(" ready.")
            return True
        except Exception:
            time.sleep(1)
    print(" TIMEOUT (continuing anyway).")
    return False


def main():
    print("=== Knowledge OS Database Setup ===\n")

    code, out = run(["docker", "--version"])
    if code != 0:
        print("ERROR: Docker not found.")
        print()
        print("Install Docker Desktop:")
        print("  https://www.docker.com/products/docker-desktop/")
        print()
        print("After installing, make sure Docker Desktop is running.")
        sys.exit(1)

    ports = load_ports()

    print("[1/3] Starting Docker containers...")
    env_args = [
        "-e", f"NEO4J_HTTP_PORT={ports['neo4j_http']}",
        "-e", f"NEO4J_BOLT_PORT={ports['neo4j_bolt']}",
        "-e", f"QDRANT_HTTP_PORT={ports['qdrant_http']}",
    ]
    code, out = run(["docker", "compose", "-f", str(COMPOSE_FILE)] + env_args + ["up", "-d"])
    if code != 0:
        print(f"  Failed to start containers:\n{out}")
        sys.exit(1)
    print("  Containers started.")

    print(f"[2/3] Checking Neo4j (bolt://localhost:{ports['neo4j_bolt']})...")
    wait_for_url(f"http://localhost:{ports['neo4j_http']}", "Neo4j", timeout=30)

    print(f"[3/3] Checking Qdrant (localhost:{ports['qdrant_http']})...")
    wait_for_url(f"http://localhost:{ports['qdrant_http']}/healthz", "Qdrant", timeout=20)

    print()
    print("=== All databases started ===")
    print(f"  Neo4j Browser:    http://localhost:{ports['neo4j_http']}")
    print(f"  Qdrant Dashboard: http://localhost:{ports['qdrant_http']}/dashboard")


if __name__ == "__main__":
    main()
