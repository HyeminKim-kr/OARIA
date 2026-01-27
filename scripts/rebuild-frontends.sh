#!/bin/bash
set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

echo "=== Rebuilding frontends with domain URLs ==="
echo "NEXT_PUBLIC_API_URL=$(grep NEXT_PUBLIC_API_URL .env | head -1 | cut -d= -f2)"
echo "NEXT_PUBLIC_ADMIN_API_URL=$(grep NEXT_PUBLIC_ADMIN_API_URL .env | head -1 | cut -d= -f2)"
echo ""

echo "[1/3] Stopping frontend containers..."
docker compose -f docker-compose.yml -f docker-compose.prod.yml stop service-frontend admin-frontend

echo "[2/3] Rebuilding frontend images (no cache)..."
docker compose -f docker-compose.yml -f docker-compose.prod.yml build --no-cache service-frontend admin-frontend

echo "[3/3] Starting frontend containers..."
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d service-frontend admin-frontend

echo ""
echo "=== Done ==="
docker compose -f docker-compose.yml -f docker-compose.prod.yml ps service-frontend admin-frontend
