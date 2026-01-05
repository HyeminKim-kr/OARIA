#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "==================================="
echo "OARIA Cancer Paper Collection Service"
echo "==================================="
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo -e "${RED}Error: Docker is not running${NC}"
    exit 1
fi

# Start infrastructure
echo -e "${YELLOW}[1/4] Starting infrastructure...${NC}"
cd "$PROJECT_DIR/infra"
docker-compose up -d
sleep 3
echo -e "${GREEN}Infrastructure started!${NC}"

# Build and start backend
echo -e "${YELLOW}[2/4] Starting backend...${NC}"
cd "$PROJECT_DIR/admin/backend"
npm run build > /dev/null 2>&1
node dist/main.js &
BACKEND_PID=$!
sleep 2
echo -e "${GREEN}Backend started (PID: $BACKEND_PID)${NC}"

# Build and start frontend
echo -e "${YELLOW}[3/4] Starting frontend...${NC}"
cd "$PROJECT_DIR/admin/frontend"
npm run build > /dev/null 2>&1
npm run start &
FRONTEND_PID=$!
sleep 2
echo -e "${GREEN}Frontend started (PID: $FRONTEND_PID)${NC}"

echo ""
echo -e "${GREEN}==================================${NC}"
echo -e "${GREEN}All services are running!${NC}"
echo -e "${GREEN}==================================${NC}"
echo ""
echo "URLs:"
echo "  Admin UI:    http://localhost:13001"
echo "  Admin API:   http://localhost:13000"
echo "  Swagger:     http://localhost:13000/api"
echo "  MinIO:       http://localhost:19001 (admin/admin123)"
echo ""
echo "To stop all services, run: ./scripts/stop-all.sh"
echo ""

# Keep script running and handle Ctrl+C
trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; cd $PROJECT_DIR/infra && docker-compose down; exit 0" SIGINT SIGTERM

wait
