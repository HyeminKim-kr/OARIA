#!/bin/bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "Stopping all OARIA services..."

# Stop Node.js processes
pkill -f "node dist/main" 2>/dev/null || true
pkill -f "next start" 2>/dev/null || true

# Stop infrastructure
cd "$PROJECT_DIR/infra"
docker-compose down

echo "All services stopped!"
