#!/bin/bash
# Start script for hybrid Docker + local development environment
# Starts: PostgreSQL, Redis (Docker) + Django server, RQ worker (local with uv)

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo -e "${GREEN}Starting Easy Access Platform - Hybrid Development Mode${NC}"
echo "=================================================="
echo ""

# Function to cleanup on exit
cleanup() {
    echo ""
    echo -e "${YELLOW}Stopping services...${NC}"
    echo -e "${YELLOW}Note: Docker containers (db, redis) remain running - use 'docker compose down' to stop them${NC}"

    # Kill background processes
    if [[ -n "$DJANGO_PID" ]]; then
        kill "$DJANGO_PID" 2>/dev/null || true
        echo -e "${GREEN}✓ Django server stopped${NC}"
    fi

    if [[ -n "$WORKER_PID" ]]; then
        kill "$WORKER_PID" 2>/dev/null || true
        echo -e "${GREEN}✓ RQ worker stopped${NC}"
    fi

    exit 0
}

# Trap SIGINT and SIGTERM
trap cleanup SIGINT SIGTERM

# Step 1: Start Docker containers (db + redis)
echo -e "${GREEN}[1/5] Starting Docker containers (db, redis)...${NC}"
docker compose up -d

# Wait for containers to be healthy
echo -e "${YELLOW}Waiting for containers to be healthy...${NC}"
max_wait=30
waited=0
while [ $waited -lt $max_wait ]; do
    if docker compose ps | grep -q "healthy"; then
        # Check if both are healthy (count lines containing "healthy")
        healthy_count=$(docker compose ps --format json | jq -s '[.[] | select(.Health == "healthy")] | length')
        if [ "$healthy_count" -eq 2 ]; then
            echo -e "${GREEN}✓ All containers healthy${NC}"
            break
        fi
    fi
    sleep 1
    waited=$((waited + 1))
    echo -n "."
done

if [ $waited -eq $max_wait ]; then
    echo -e "${RED}✗ Containers didn't become healthy in time${NC}"
    docker compose ps
    exit 1
fi

echo ""

# Step 2: Load environment variables
echo -e "${GREEN}[2/5] Loading environment variables...${NC}"
if [ -f .env ]; then
    set -a
    source .env
    set +a
    echo -e "${GREEN}✓ Environment variables loaded from .env${NC}"
else
    echo -e "${RED}✗ .env file not found${NC}"
    exit 1
fi

echo ""

# Step 3: Run migrations
echo -e "${GREEN}[3/5] Running database migrations...${NC}"
uv run python src/manage.py migrate --no-input
echo -e "${GREEN}✓ Migrations complete${NC}"

echo ""

# Step 4: Start RQ worker (background)
echo -e "${GREEN}[4/5] Starting RQ worker...${NC}"
mkdir -p logs
uv run python src/manage.py rqworker --job-class django_tasks.backends.rq.Job default > logs/rqworker.log 2>&1 &
WORKER_PID=$!
sleep 2

if ps -p $WORKER_PID > /dev/null; then
    echo -e "${GREEN}✓ RQ worker started (PID: $WORKER_PID)${NC}"
    echo "  Logs: logs/rqworker.log"
else
    echo -e "${RED}✗ RQ worker failed to start${NC}"
    tail -20 logs/rqworker.log
    exit 1
fi

echo ""

# Step 5: Start Django development server
echo -e "${GREEN}[5/5] Starting Django development server...${NC}"
echo ""
echo -e "${GREEN}═══════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  Easy Access Platform is ready!${NC}"
echo -e "${GREEN}═══════════════════════════════════════════════════${NC}"
echo ""
echo -e "  Django:     ${YELLOW}http://localhost:8000${NC}"
echo -e "  Admin:      ${YELLOW}http://localhost:8000/admin${NC}"
echo -e "  RQ Worker:  running (PID: $WORKER_PID)"
echo ""
echo -e "  Logs:"
echo -e "    Worker:  ${YELLOW}logs/rqworker.log${NC}"
echo ""
echo -e "  Press ${YELLOW}Ctrl+C${NC} to stop all services"
echo -e "${GREEN}═══════════════════════════════════════════════════${NC}"
echo ""

# Start Django server in foreground
uv run python src/manage.py runserver 0.0.0.0:8000 &
DJANGO_PID=$!

# Wait for Django server process
wait $DJANGO_PID
