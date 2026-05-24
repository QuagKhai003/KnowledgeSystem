#!/usr/bin/env bash
# Database bootstrap script — starts Docker services and waits for readiness.

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
COMPOSE_FILE="$PROJECT_ROOT/docker/docker-compose.yml"

echo "=== Knowledge OS Database Setup ==="
echo ""

# Start containers
echo "[1/4] Starting Docker containers..."
docker compose -f "$COMPOSE_FILE" up -d

# Wait for Neo4j
echo "[2/4] Waiting for Neo4j (bolt://localhost:7687)..."
for i in $(seq 1 30); do
    if docker compose -f "$COMPOSE_FILE" exec -T neo4j cypher-shell -u neo4j -p knowledge_os "RETURN 1" >/dev/null 2>&1; then
        echo "  Neo4j ready."
        break
    fi
    if [ "$i" -eq 30 ]; then
        echo "  WARNING: Neo4j not ready after 30s, continuing anyway."
    fi
    sleep 1
done

# Wait for Qdrant
echo "[3/4] Waiting for Qdrant (localhost:6333)..."
for i in $(seq 1 20); do
    if curl -s http://localhost:6333/healthz >/dev/null 2>&1; then
        echo "  Qdrant ready."
        break
    fi
    if [ "$i" -eq 20 ]; then
        echo "  WARNING: Qdrant not ready after 20s, continuing anyway."
    fi
    sleep 1
done

# Wait for OpenSearch
echo "[4/4] Waiting for OpenSearch (localhost:9200)..."
for i in $(seq 1 30); do
    if curl -s http://localhost:9200/_cluster/health >/dev/null 2>&1; then
        echo "  OpenSearch ready."
        break
    fi
    if [ "$i" -eq 30 ]; then
        echo "  WARNING: OpenSearch not ready after 30s, continuing anyway."
    fi
    sleep 1
done

echo ""
echo "=== All databases started ==="
echo "  Neo4j Browser:  http://localhost:7474"
echo "  Qdrant Dashboard: http://localhost:6333/dashboard"
echo "  OpenSearch:     http://localhost:9200"
