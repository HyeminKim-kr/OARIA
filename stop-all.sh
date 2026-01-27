#!/bin/bash
# OARIA - 모든 서비스 중지 스크립트

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "=== Docker Compose 중지 ==="
docker compose -f docker-compose.yml -f docker-compose.dev.yml down 2>/dev/null || \
docker compose down 2>/dev/null || \
echo "Docker Compose 서비스 없음"

echo ""
echo "=== Next.js 개발 서버 중지 ==="
NEXT_PIDS=$(pgrep -f 'next-server' 2>/dev/null || true)
if [ -n "$NEXT_PIDS" ]; then
  echo "$NEXT_PIDS" | xargs kill 2>/dev/null || true
  echo "Next.js 서버 종료됨 (PIDs: $NEXT_PIDS)"
else
  echo "실행 중인 Next.js 서버 없음"
fi

echo ""
echo "=== Uvicorn 서버 중지 ==="
UVICORN_PIDS=$(pgrep -f 'uvicorn' 2>/dev/null || true)
if [ -n "$UVICORN_PIDS" ]; then
  echo "$UVICORN_PIDS" | xargs kill 2>/dev/null || true
  echo "Uvicorn 서버 종료됨 (PIDs: $UVICORN_PIDS)"
else
  echo "실행 중인 Uvicorn 서버 없음"
fi

echo ""
echo "=== 완료 ==="
echo "남은 리스닝 포트:"
ss -tlnp 2>/dev/null | grep LISTEN | grep -v 'sshd\|systemd\|resolved' || echo "없음"
