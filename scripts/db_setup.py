#!/usr/bin/env python3
"""Cross-platform database setup: starts Docker containers and waits for readiness."""

import subprocess
import sys
import time
import urllib.request
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
COMPOSE_FILE = PROJECT_ROOT / "docker" / "docker-compose.yml"


def run(cmd: list[str]) -> tuple[int, str]:
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.returncode, result.stdout + result.stderr


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

    # Check docker is available
    code, out = run(["docker", "--version"])
    if code != 0:
        print("ERROR: Docker not found.")
        print()
        print("Install Docker Desktop for Windows:")
        print("  https://www.docker.com/products/docker-desktop/")
        print()
        print("After installing, make sure Docker Desktop is running.")
        sys.exit(1)

    # Start containers
    print("[1/4] Starting Docker containers...")
    code, out = run(["docker", "compose", "-f", str(COMPOSE_FILE), "up", "-d"])
    if code != 0:
        print(f"  Failed to start containers:\n{out}")
        sys.exit(1)
    print("  Containers started.")

    # Wait for services
    print("[2/4] Checking Neo4j (bolt://localhost:7687)...")
    wait_for_url("http://localhost:7474", "Neo4j", timeout=30)

    print("[3/4] Checking Qdrant (localhost:6333)...")
    wait_for_url("http://localhost:6333/healthz", "Qdrant", timeout=20)

    print("[4/4] Checking OpenSearch (localhost:9200)...")
    wait_for_url("http://localhost:9200", "OpenSearch", timeout=30)

    print()
    print("=== All databases started ===")
    print("  Neo4j Browser:    http://localhost:7474")
    print("  Qdrant Dashboard: http://localhost:6333/dashboard")
    print("  OpenSearch:       http://localhost:9200")


if __name__ == "__main__":
    main()
