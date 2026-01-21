#!/bin/bash

# ============================================================
# OARIA 개발 환경 시작 및 모니터링 스크립트
# ============================================================
#
# 자세한 도움말: ./scripts/dev.sh help
#
# 기본 명령어 (인터랙티브):
#   ./scripts/dev.sh start     - 개발 환경 시작 (로컬/Docker 선택)
#   ./scripts/dev.sh stop      - 개발 환경 중지
#   ./scripts/dev.sh restart   - 재시작
#   ./scripts/dev.sh status    - 상태 확인
#   ./scripts/dev.sh logs      - 로그 보기
#   ./scripts/dev.sh monitor   - 실시간 모니터링
#
# 로컬 개발 모드 (직접 실행):
#   ./scripts/dev.sh local start/stop/restart       - 로컬 모드 (인프라 Docker + 로컬 앱)
#
# Docker 개발 모드 (직접 실행):
#   ./scripts/dev.sh docker-dev start/stop/restart/rebuild  - 개발 모드 (Hot Reload)
#   ./scripts/dev.sh prod start/stop/restart/rebuild        - 프로덕션 모드
#
# 인프라 제어:
#   ./scripts/dev.sh docker start/stop/restart  - 인프라만 (DB, Redis 등)
#
# 로컬 서비스 개별 제어:
#   ./scripts/dev.sh admin start/stop/restart    - Admin 서비스만 (로컬)
#   ./scripts/dev.sh service start/stop/restart  - User 서비스만 (로컬)
#
# 개별 컨테이너 제어:
#   ./scripts/dev.sh container <name> start/stop/restart/rebuild/logs
#   예: ./scripts/dev.sh container celery-backfill restart
#
# 유틸리티:
#   ./scripts/dev.sh install   - 의존성 설치
#   ./scripts/dev.sh migrate   - DB 마이그레이션
#
# ============================================================

# set -e 제거: 에러 발생 시 중간에 멈추면 Docker 상태 불일치 발생 가능

# 프로젝트 루트 디렉토리
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
LOG_DIR="$PROJECT_ROOT/.dev-logs"
LOCK_FILE="$PROJECT_ROOT/.dev-lock"

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# 포트 정의
PORTS=(
    "15432:PostgreSQL"
    "16379:Redis"
    "19000:MinIO API"
    "19001:MinIO Console"
    "18080:Weaviate"
    "15555:Flower"
    "13000:Admin Backend"
    "13001:Admin Frontend"
    "8000:Service Backend"
    "3000:Service Frontend"
)

# PID 파일 위치
PID_DIR="$PROJECT_ROOT/.pids"

# ============================================================
# 안전 장치 함수들
# ============================================================

# Docker 데몬 상태 확인
check_docker_daemon() {
    if ! docker info >/dev/null 2>&1; then
        echo -e "${RED}오류: Docker 데몬이 실행 중이지 않습니다${NC}"
        echo -e "  Docker Desktop을 시작하거나 'docker' 서비스를 확인하세요."
        return 1
    fi
    return 0
}

# Lock 파일로 동시 실행 방지
acquire_lock() {
    local timeout=${1:-30}  # 기본 30초 대기
    local count=0

    while [ -f "$LOCK_FILE" ]; do
        local lock_pid=$(cat "$LOCK_FILE" 2>/dev/null || echo "")

        # Lock을 건 프로세스가 죽었으면 lock 파일 제거
        if [ -n "$lock_pid" ] && ! kill -0 "$lock_pid" 2>/dev/null; then
            echo -e "${YELLOW}⚠${NC} 이전 프로세스가 종료됨, lock 해제"
            rm -f "$LOCK_FILE"
            break
        fi

        if [ $count -ge $timeout ]; then
            echo -e "${RED}오류: 다른 dev.sh 프로세스가 실행 중입니다 (PID: $lock_pid)${NC}"
            echo -e "  강제 해제: rm $LOCK_FILE"
            return 1
        fi

        if [ $count -eq 0 ]; then
            echo -e "${YELLOW}▸${NC} 다른 프로세스 대기 중... (PID: $lock_pid)"
        fi

        sleep 1
        count=$((count + 1))
    done

    echo $$ > "$LOCK_FILE"
    trap release_lock EXIT INT TERM
    return 0
}

# Lock 해제
release_lock() {
    rm -f "$LOCK_FILE"
}

# Docker 컨테이너가 완전히 중지될 때까지 대기
wait_for_container_stop() {
    local container_name=$1
    local max_wait=${2:-30}
    local count=0

    while docker ps -q -f "name=$container_name" 2>/dev/null | grep -q .; do
        if [ $count -ge $max_wait ]; then
            echo -e "${YELLOW}⚠${NC} $container_name 중지 타임아웃"
            return 1
        fi
        sleep 1
        count=$((count + 1))
    done
    return 0
}

# Docker Compose가 완전히 정리될 때까지 대기
wait_for_compose_down() {
    local max_wait=${1:-30}
    local count=0

    while docker ps -q -f "name=oaria-" 2>/dev/null | grep -q .; do
        if [ $count -ge $max_wait ]; then
            echo -e "${YELLOW}⚠${NC} 일부 컨테이너가 아직 실행 중"
            return 1
        fi
        sleep 1
        count=$((count + 1))
    done
    return 0
}

# 현재 실행 모드 감지 (dev/prod/기본)
detect_compose_mode() {
    # docker-compose.dev.yml로 실행된 컨테이너가 있는지 확인
    if docker ps --format '{{.Names}}' 2>/dev/null | grep -q "oaria-service-backend\|oaria-admin-backend"; then
        # 앱 컨테이너가 있으면 dev 또는 prod 모드
        local labels=$(docker inspect oaria-service-backend --format '{{.Config.Labels}}' 2>/dev/null || echo "")
        if echo "$labels" | grep -q "dev"; then
            echo "dev"
        elif echo "$labels" | grep -q "prod"; then
            echo "prod"
        else
            echo "dev"  # 기본값
        fi
    else
        echo "infra"  # 인프라만 실행 중
    fi
}

# ============================================================

print_header() {
    echo -e "\n${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${CYAN}  $1${NC}"
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
}

print_status() {
    local status=$1
    local name=$2
    local port=$3
    local extra=$4

    if [ "$status" = "running" ]; then
        echo -e "  ${GREEN}●${NC} $name ${GREEN}(port $port)${NC} $extra"
    elif [ "$status" = "starting" ]; then
        echo -e "  ${YELLOW}◐${NC} $name ${YELLOW}(port $port)${NC} starting..."
    else
        echo -e "  ${RED}○${NC} $name ${RED}(port $port)${NC} stopped"
    fi
}

check_port() {
    local port=$1
    lsof -i :$port >/dev/null 2>&1
}

wait_for_port() {
    local port=$1
    local name=$2
    local max_wait=${3:-10}  # 기본 10초
    local count=0

    while ! check_port $port && [ $count -lt $max_wait ]; do
        sleep 1
        count=$((count + 1))
    done

    if check_port $port; then
        return 0
    else
        return 1
    fi
}

# Docker 서비스 시작 (인프라만)
start_docker() {
    print_header "Docker Compose 시작 (인프라 + 배치)"

    # Docker 데몬 확인
    if ! check_docker_daemon; then
        return 1
    fi

    cd "$PROJECT_ROOT"

    echo -e "  ${YELLOW}▸${NC} Docker Compose 실행 중..."
    docker compose up -d

    echo -e "  ${YELLOW}▸${NC} 서비스 헬스체크 대기 중..."

    # 인프라 서비스 대기
    local services=("postgres:15432" "redis:16379" "weaviate:18080" "minio:19000")
    for svc in "${services[@]}"; do
        IFS=':' read -r name port <<< "$svc"
        printf "    - %-15s" "$name"
        if wait_for_port $port $name; then
            echo -e "${GREEN}ready${NC}"
        else
            echo -e "${RED}timeout${NC}"
        fi
    done
}

# Docker 프로덕션 모드 시작
start_docker_prod() {
    print_header "Docker Compose 시작 (프로덕션 모드)"

    # Docker 데몬 확인
    if ! check_docker_daemon; then
        return 1
    fi

    cd "$PROJECT_ROOT"

    echo -e "  ${YELLOW}▸${NC} 인프라 + 앱 서비스 빌드 및 실행 중..."
    docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build

    echo -e "  ${YELLOW}▸${NC} 서비스 헬스체크 대기 중..."

    # 인프라 서비스 먼저 대기 (마이그레이션을 위해)
    local infra_services=("postgres:15432" "redis:16379" "weaviate:18080" "minio:19000")
    for svc in "${infra_services[@]}"; do
        IFS=':' read -r name port <<< "$svc"
        printf "    - %-20s" "$name"
        if wait_for_port $port $name 30; then
            echo -e "${GREEN}ready${NC}"
        else
            echo -e "${RED}timeout${NC}"
        fi
    done

    # DB 마이그레이션 실행
    run_migrations

    # 앱 서비스 대기
    local app_services=("service-backend:8000" "service-frontend:3000" "admin-backend:13000" "admin-frontend:13001")
    for svc in "${app_services[@]}"; do
        IFS=':' read -r name port <<< "$svc"
        printf "    - %-20s" "$name"
        if wait_for_port $port $name 30; then
            echo -e "${GREEN}ready${NC}"
        else
            echo -e "${RED}timeout${NC}"
        fi
    done

    echo -e "\n  ${GREEN}✓${NC} 프로덕션 모드 시작 완료"
}

# Docker 프로덕션 모드 중지
stop_docker_prod() {
    print_header "Docker Compose 중지 (프로덕션 모드)"

    # Docker 데몬 확인
    if ! check_docker_daemon; then
        echo -e "  ${YELLOW}⚠${NC} Docker 데몬이 없어 중지 스킵"
        return 0
    fi

    cd "$PROJECT_ROOT"
    docker compose -f docker-compose.yml -f docker-compose.prod.yml down
    echo -e "  ${GREEN}✓${NC} 프로덕션 서비스 중지됨"
}

# Docker 프로덕션 모드 리빌드
rebuild_docker_prod() {
    print_header "Docker Compose 리빌드 (프로덕션 모드)"
    cd "$PROJECT_ROOT"

    echo -e "  ${YELLOW}▸${NC} 기존 컨테이너 중지 및 제거..."
    docker compose -f docker-compose.yml -f docker-compose.prod.yml down

    echo -e "  ${YELLOW}▸${NC} 이미지 리빌드 중 (--no-cache)..."
    docker compose -f docker-compose.yml -f docker-compose.prod.yml build --no-cache

    echo -e "  ${YELLOW}▸${NC} 서비스 시작..."
    start_docker_prod
}

# Docker 개발 모드 시작
start_docker_dev() {
    print_header "Docker Compose 시작 (개발 모드 - Hot Reload)"

    # Docker 데몬 확인
    if ! check_docker_daemon; then
        return 1
    fi

    cd "$PROJECT_ROOT"

    # 1. 인프라 서비스만 먼저 시작 (마이그레이션을 위해)
    echo -e "  ${YELLOW}▸${NC} 인프라 서비스 시작 중..."
    docker compose up -d

    echo -e "  ${YELLOW}▸${NC} 인프라 헬스체크 대기 중..."
    local infra_services=("postgres:15432" "redis:16379" "weaviate:18080" "minio:19000")
    for svc in "${infra_services[@]}"; do
        IFS=':' read -r name port <<< "$svc"
        printf "    - %-20s" "$name"
        if wait_for_port $port $name 30; then
            echo -e "${GREEN}ready${NC}"
        else
            echo -e "${RED}timeout${NC}"
        fi
    done

    # 2. DB 마이그레이션 실행 (앱 서비스 시작 전에!)
    run_migrations

    # 3. 앱 서비스 시작 (마이그레이션 완료 후)
    echo -e "  ${YELLOW}▸${NC} 앱 서비스 빌드 및 시작 중..."
    docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d --build

    echo -e "  ${YELLOW}▸${NC} 앱 서비스 헬스체크 대기 중..."
    local app_services=("service-backend:8000" "service-frontend:3000" "admin-backend:13000" "admin-frontend:13001")
    for svc in "${app_services[@]}"; do
        IFS=':' read -r name port <<< "$svc"
        printf "    - %-20s" "$name"
        if wait_for_port $port $name 30; then
            echo -e "${GREEN}ready${NC}"
        else
            echo -e "${RED}timeout${NC}"
        fi
    done

    echo -e "\n  ${GREEN}✓${NC} 개발 모드 시작 완료 (볼륨 마운트로 Hot Reload 지원)"
}

# Docker 개발 모드 중지
stop_docker_dev() {
    print_header "Docker Compose 중지 (개발 모드)"

    # Docker 데몬 확인
    if ! check_docker_daemon; then
        echo -e "  ${YELLOW}⚠${NC} Docker 데몬이 없어 중지 스킵"
        return 0
    fi

    cd "$PROJECT_ROOT"
    docker compose -f docker-compose.yml -f docker-compose.dev.yml down
    echo -e "  ${GREEN}✓${NC} 개발 서비스 중지됨"
}

# Docker 개발 모드 리빌드
rebuild_docker_dev() {
    print_header "Docker Compose 리빌드 (개발 모드)"
    cd "$PROJECT_ROOT"

    echo -e "  ${YELLOW}▸${NC} 기존 컨테이너 중지 및 제거..."
    docker compose -f docker-compose.yml -f docker-compose.dev.yml down

    echo -e "  ${YELLOW}▸${NC} 이미지 리빌드 중 (--no-cache)..."
    docker compose -f docker-compose.yml -f docker-compose.dev.yml build --no-cache

    echo -e "  ${YELLOW}▸${NC} 서비스 시작..."
    start_docker_dev
}

# Docker 서비스 중지
stop_docker() {
    print_header "Docker Compose 중지"

    # Docker 데몬 확인
    if ! check_docker_daemon; then
        echo -e "  ${YELLOW}⚠${NC} Docker 데몬이 없어 중지 스킵"
        return 0
    fi

    cd "$PROJECT_ROOT"
    docker compose down
    echo -e "  ${GREEN}✓${NC} Docker 서비스 중지됨"
}

# Docker 서비스 재시작 (인프라만)
restart_docker() {
    print_header "Docker Compose 재시작 (인프라)"
    stop_docker

    echo -e "  ${YELLOW}▸${NC} 컨테이너 완전 종료 대기 중..."
    wait_for_compose_down 30
    sleep 3  # 추가 안전 대기

    start_docker
}

# 의존성 패키지 설치
install_dependencies() {
    print_header "의존성 패키지 설치"

    # 1. Service Backend (Python - uv)
    echo -e "  ${YELLOW}▸${NC} Service Backend (uv sync)..."
    cd "$PROJECT_ROOT/backend"
    if uv sync --quiet; then
        echo -e "    ${GREEN}✓${NC} backend 패키지 설치 완료"
    else
        echo -e "    ${RED}✗${NC} backend 패키지 설치 실패"
    fi

    # 2. Service Frontend (Node - npm)
    echo -e "  ${YELLOW}▸${NC} Service Frontend (npm install)..."
    cd "$PROJECT_ROOT/frontend"
    if npm install --silent; then
        echo -e "    ${GREEN}✓${NC} frontend 패키지 설치 완료"
    else
        echo -e "    ${RED}✗${NC} frontend 패키지 설치 실패"
    fi

    # 3. Admin Backend (Node - npm)
    echo -e "  ${YELLOW}▸${NC} Admin Backend (npm install)..."
    cd "$PROJECT_ROOT/admin/backend"
    if npm install --silent; then
        echo -e "    ${GREEN}✓${NC} admin/backend 패키지 설치 완료"
    else
        echo -e "    ${RED}✗${NC} admin/backend 패키지 설치 실패"
    fi

    # 4. Admin Frontend (Node - npm)
    echo -e "  ${YELLOW}▸${NC} Admin Frontend (npm install)..."
    cd "$PROJECT_ROOT/admin/frontend"
    if npm install --silent; then
        echo -e "    ${GREEN}✓${NC} admin/frontend 패키지 설치 완료"
    else
        echo -e "    ${RED}✗${NC} admin/frontend 패키지 설치 실패"
    fi

    # Note: Batch는 Docker로 실행되므로 로컬 패키지 설치 불필요

    echo -e "  ${GREEN}✓${NC} 의존성 설치 완료"
}

# DB 마이그레이션 실행
run_migrations() {
    print_header "DB 마이그레이션 실행"

    # 1. Service Backend (Alembic)
    echo -e "  ${YELLOW}▸${NC} Service Backend 마이그레이션..."
    (cd "$PROJECT_ROOT/backend" && uv run alembic upgrade head) && \
        echo -e "    ${GREEN}✓${NC} Alembic 마이그레이션 완료" || \
        echo -e "    ${RED}✗${NC} Alembic 마이그레이션 실패"

    # 2. Admin Backend (TypeORM)
    echo -e "  ${YELLOW}▸${NC} Admin Backend 마이그레이션..."
    (cd "$PROJECT_ROOT/admin/backend" && npm run migration:run) && \
        echo -e "    ${GREEN}✓${NC} TypeORM 마이그레이션 완료" || \
        echo -e "    ${RED}✗${NC} TypeORM 마이그레이션 실패"

    echo -e "  ${GREEN}✓${NC} 마이그레이션 완료"
}

# Admin Backend 시작
start_admin_backend() {
    print_header "Admin Backend 시작 (NestJS)"

    mkdir -p "$LOG_DIR" "$PID_DIR"

    cd "$PROJECT_ROOT/admin/backend"

    if check_port 13000; then
        echo -e "  ${YELLOW}⚠${NC} 포트 13000이 이미 사용 중입니다"
        return
    fi

    echo -e "  ${YELLOW}▸${NC} npm run start:dev 실행 중..."
    nohup npm run start:dev > "$LOG_DIR/admin-backend.log" 2>&1 &
    echo $! > "$PID_DIR/admin-backend.pid"

    printf "    - Admin Backend "
    if wait_for_port 13000 "admin-backend" 5; then
        echo -e "${GREEN}ready${NC}"
    else
        echo -e "${YELLOW}starting... (log: .dev-logs/admin-backend.log)${NC}"
    fi
}

# Admin Frontend 시작
start_admin_frontend() {
    print_header "Admin Frontend 시작 (Next.js)"

    mkdir -p "$LOG_DIR" "$PID_DIR"

    cd "$PROJECT_ROOT/admin/frontend"

    if check_port 13001; then
        echo -e "  ${YELLOW}⚠${NC} 포트 13001이 이미 사용 중입니다"
        return
    fi

    echo -e "  ${YELLOW}▸${NC} npm run dev 실행 중..."
    nohup npm run dev > "$LOG_DIR/admin-frontend.log" 2>&1 &
    echo $! > "$PID_DIR/admin-frontend.pid"

    printf "    - Admin Frontend "
    if wait_for_port 13001 "admin-frontend" 5; then
        echo -e "${GREEN}ready${NC}"
    else
        echo -e "${YELLOW}starting... (log: .dev-logs/admin-frontend.log)${NC}"
    fi
}

# Service Backend 시작
start_service_backend() {
    print_header "Service Backend 시작 (FastAPI)"

    mkdir -p "$LOG_DIR" "$PID_DIR"

    cd "$PROJECT_ROOT/backend"

    if check_port 8000; then
        echo -e "  ${YELLOW}⚠${NC} 포트 8000이 이미 사용 중입니다"
        return
    fi

    echo -e "  ${YELLOW}▸${NC} uvicorn 실행 중..."
    nohup uv run uvicorn app.main:app --reload --port 8000 > "$LOG_DIR/service-backend.log" 2>&1 &
    echo $! > "$PID_DIR/service-backend.pid"

    printf "    - Service Backend "
    if wait_for_port 8000 "service-backend" 5; then
        echo -e "${GREEN}ready${NC}"
    else
        echo -e "${YELLOW}starting... (log: .dev-logs/service-backend.log)${NC}"
    fi
}

# Service Frontend 시작
start_service_frontend() {
    print_header "Service Frontend 시작 (Next.js)"

    mkdir -p "$LOG_DIR" "$PID_DIR"

    cd "$PROJECT_ROOT/frontend"

    if check_port 3000; then
        echo -e "  ${YELLOW}⚠${NC} 포트 3000이 이미 사용 중입니다"
        return
    fi

    echo -e "  ${YELLOW}▸${NC} npm run dev 실행 중..."
    nohup npm run dev > "$LOG_DIR/service-frontend.log" 2>&1 &
    echo $! > "$PID_DIR/service-frontend.pid"

    printf "    - Service Frontend "
    if wait_for_port 3000 "service-frontend" 5; then
        echo -e "${GREEN}ready${NC}"
    else
        echo -e "${YELLOW}starting... (log: .dev-logs/service-frontend.log)${NC}"
    fi
}

# 개별 서비스 중지 함수
stop_service() {
    local name=$1
    local pid_file="$PID_DIR/$name.pid"
    local port=$2

    if [ -f "$pid_file" ]; then
        local pid=$(cat "$pid_file")
        if kill -0 $pid 2>/dev/null; then
            kill $pid 2>/dev/null || true
            rm -f "$pid_file"
        fi
    fi

    # 포트로도 프로세스 종료 시도 (Docker 프로세스 제외)
    if [ -n "$port" ]; then
        local pids=$(lsof -t -i :$port 2>/dev/null || true)
        if [ -n "$pids" ]; then
            for pid in $pids; do
                # Docker 관련 프로세스는 skip (com.docker, docker-proxy 등)
                local proc_name=$(ps -p $pid -o comm= 2>/dev/null || true)
                if [[ "$proc_name" != *"docker"* ]] && [[ "$proc_name" != "com.docker"* ]]; then
                    kill $pid 2>/dev/null || true
                fi
            done
        fi
    fi
}

# 모든 개발 서버 중지
stop_dev_servers() {
    print_header "개발 서버 중지"

    echo -e "  ${YELLOW}▸${NC} Admin Backend 중지..."
    stop_service "admin-backend" 13000

    echo -e "  ${YELLOW}▸${NC} Admin Frontend 중지..."
    stop_service "admin-frontend" 13001

    echo -e "  ${YELLOW}▸${NC} Service Backend 중지..."
    stop_service "service-backend" 8000

    echo -e "  ${YELLOW}▸${NC} Service Frontend 중지..."
    stop_service "service-frontend" 3000

    rm -rf "$PID_DIR"

    echo -e "  ${GREEN}✓${NC} 개발 서버 중지됨"
}

# Admin 서비스 재시작 (로컬)
restart_admin() {
    print_header "Admin 서비스 재시작"
    echo -e "  ${YELLOW}▸${NC} Admin Backend 중지..."
    stop_service "admin-backend" 13000
    echo -e "  ${YELLOW}▸${NC} Admin Frontend 중지..."
    stop_service "admin-frontend" 13001
    sleep 1
    start_admin_backend
    start_admin_frontend
}

# Service 서비스 재시작 (로컬)
restart_service_local() {
    print_header "Service 서비스 재시작"
    echo -e "  ${YELLOW}▸${NC} Service Backend 중지..."
    stop_service "service-backend" 8000
    echo -e "  ${YELLOW}▸${NC} Service Frontend 중지..."
    stop_service "service-frontend" 3000
    sleep 1
    start_service_backend
    start_service_frontend
}

# 개별 컨테이너 제어
container_control() {
    local container_name=$1
    local action=$2

    # Docker 데몬 확인
    if ! check_docker_daemon; then
        return 1
    fi

    # oaria- 접두사가 없으면 추가
    if [[ ! "$container_name" =~ ^oaria- ]]; then
        container_name="oaria-$container_name"
    fi

    # 유효한 컨테이너 목록
    local valid_containers=(
        "oaria-postgres" "oaria-redis" "oaria-minio" "oaria-weaviate"
        "oaria-celery-backfill" "oaria-celery-embed" "oaria-celery-beat" "oaria-flower"
        "oaria-service-backend" "oaria-service-frontend" "oaria-admin-backend" "oaria-admin-frontend"
    )

    # 컨테이너 이름 유효성 검사
    local is_valid=false
    for valid in "${valid_containers[@]}"; do
        if [ "$container_name" = "$valid" ]; then
            is_valid=true
            break
        fi
    done

    if [ "$is_valid" = false ]; then
        echo -e "${RED}오류: 유효하지 않은 컨테이너 이름입니다: $container_name${NC}"
        echo ""
        echo -e "${YELLOW}사용 가능한 컨테이너:${NC}"
        echo -e "  ${BLUE}[인프라]${NC}"
        echo "    postgres, redis, minio, weaviate"
        echo -e "  ${BLUE}[배치]${NC}"
        echo "    celery-backfill, celery-embed, celery-beat, flower"
        echo -e "  ${BLUE}[앱]${NC}"
        echo "    service-backend, service-frontend, admin-backend, admin-frontend"
        return 1
    fi

    # docker-compose 서비스 이름 추출 (oaria- 제거)
    local service_name="${container_name#oaria-}"

    cd "$PROJECT_ROOT"

    case "$action" in
        start)
            print_header "컨테이너 시작: $container_name"
            docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d "$service_name"
            echo -e "  ${GREEN}✓${NC} $container_name 시작됨"
            ;;
        stop)
            print_header "컨테이너 중지: $container_name"
            docker compose -f docker-compose.yml -f docker-compose.dev.yml stop "$service_name"
            echo -e "  ${GREEN}✓${NC} $container_name 중지됨"
            ;;
        restart)
            print_header "컨테이너 재시작: $container_name"
            docker compose -f docker-compose.yml -f docker-compose.dev.yml restart "$service_name"
            echo -e "  ${GREEN}✓${NC} $container_name 재시작됨"
            ;;
        rebuild)
            print_header "컨테이너 리빌드: $container_name"
            echo -e "  ${YELLOW}▸${NC} 컨테이너 중지..."
            docker compose -f docker-compose.yml -f docker-compose.dev.yml stop "$service_name"
            echo -e "  ${YELLOW}▸${NC} 이미지 리빌드 (--no-cache)..."
            docker compose -f docker-compose.yml -f docker-compose.dev.yml build --no-cache "$service_name"
            echo -e "  ${YELLOW}▸${NC} 컨테이너 시작..."
            docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d "$service_name"
            echo -e "  ${GREEN}✓${NC} $container_name 리빌드 완료"
            ;;
        logs)
            print_header "컨테이너 로그: $container_name"
            docker compose -f docker-compose.yml -f docker-compose.dev.yml logs -f "$service_name"
            ;;
        *)
            echo -e "${RED}오류: 유효하지 않은 액션입니다: $action${NC}"
            echo "사용법: $0 container <name> [start|stop|restart|rebuild|logs]"
            return 1
            ;;
    esac
}

# 상태 확인
show_status() {
    print_header "서비스 상태"

    echo -e "\n${BLUE}[Docker 서비스]${NC}"

    # Docker 데몬 확인
    if ! docker info >/dev/null 2>&1; then
        echo -e "  ${RED}⚠ Docker 데몬이 실행 중이지 않습니다${NC}"
    else
        # Docker 컨테이너 상태
        local containers=("oaria-postgres:15432" "oaria-redis:16379" "oaria-minio:19000" "oaria-weaviate:18080" "oaria-celery-backfill:-" "oaria-celery-embed:-" "oaria-celery-beat:-" "oaria-flower:15555")

        for item in "${containers[@]}"; do
            IFS=':' read -r name port <<< "$item"
            local status=$(docker inspect -f '{{.State.Status}}' $name 2>/dev/null || echo "not found")
            local health=$(docker inspect -f '{{.State.Health.Status}}' $name 2>/dev/null || echo "-")

            if [ "$status" = "running" ]; then
                if [ "$health" = "healthy" ] || [ "$health" = "-" ]; then
                    print_status "running" "$name" "$port" "${GREEN}($health)${NC}"
                else
                    print_status "running" "$name" "$port" "${YELLOW}($health)${NC}"
                fi
            else
                print_status "stopped" "$name" "$port"
            fi
        done
    fi

    echo -e "\n${BLUE}[개발 서버]${NC}"

    # Admin Backend
    if check_port 13000; then
        print_status "running" "Admin Backend" "13000"
    else
        print_status "stopped" "Admin Backend" "13000"
    fi

    # Admin Frontend
    if check_port 13001; then
        print_status "running" "Admin Frontend" "13001"
    else
        print_status "stopped" "Admin Frontend" "13001"
    fi

    # Service Backend
    if check_port 8000; then
        print_status "running" "Service Backend" "8000"
    else
        print_status "stopped" "Service Backend" "8000"
    fi

    # Service Frontend
    if check_port 3000; then
        print_status "running" "Service Frontend" "3000"
    else
        print_status "stopped" "Service Frontend" "3000"
    fi

    echo -e "\n${BLUE}[URL 목록]${NC}"
    echo -e "  • Admin Frontend:   ${CYAN}http://localhost:13001${NC}"
    echo -e "  • Admin Backend:    ${CYAN}http://localhost:13000${NC}"
    echo -e "  • Service Frontend: ${CYAN}http://localhost:3000${NC}"
    echo -e "  • Service Backend:  ${CYAN}http://localhost:8000${NC}"
    echo -e "  • API Docs:         ${CYAN}http://localhost:8000/docs${NC}"
    echo -e "  • Flower:           ${CYAN}http://localhost:15555${NC}"
    echo -e "  • MinIO Console:    ${CYAN}http://localhost:19001${NC}"
}

# 실시간 로그 보기
show_logs() {
    print_header "실시간 로그 모니터링"

    echo -e "${YELLOW}선택하세요:${NC}"
    echo "  1) Docker 전체 로그"
    echo "  2) Admin Backend 로그"
    echo "  3) Admin Frontend 로그"
    echo "  4) Service Backend 로그"
    echo "  5) Service Frontend 로그"
    echo "  6) 모든 개발 서버 로그"
    echo "  q) 종료"
    echo ""
    read -p "선택 (1-6, q): " choice

    case $choice in
        1)
            cd "$PROJECT_ROOT" && docker compose logs -f
            ;;
        2)
            tail -f "$LOG_DIR/admin-backend.log"
            ;;
        3)
            tail -f "$LOG_DIR/admin-frontend.log"
            ;;
        4)
            tail -f "$LOG_DIR/service-backend.log"
            ;;
        5)
            tail -f "$LOG_DIR/service-frontend.log"
            ;;
        6)
            tail -f "$LOG_DIR"/*.log
            ;;
        q)
            return
            ;;
        *)
            echo "잘못된 선택입니다"
            ;;
    esac
}

# 인터랙티브 모니터링 (watch 모드)
monitor() {
    while true; do
        clear
        echo -e "${CYAN}OARIA 서비스 모니터링${NC} (갱신: $(date '+%H:%M:%S')) - Ctrl+C로 종료"
        show_status
        sleep 5
    done
}

# 개발 모드 선택 메뉴
select_dev_mode() {
    echo -e "\n${CYAN}개발 환경 선택${NC}"
    echo ""
    echo "  1) 로컬 모드    - 호스트에서 직접 실행 (npm run dev, uvicorn)"
    echo "  2) Docker 모드  - Docker 컨테이너에서 실행 (Hot Reload 지원)"
    echo "  q) 취소"
    echo ""
    read -p "선택 (1-2, q): " choice

    case $choice in
        1)
            start_all_local
            ;;
        2)
            start_docker_dev
            ;;
        q)
            echo -e "  ${YELLOW}취소됨${NC}"
            return
            ;;
        *)
            echo -e "  ${RED}잘못된 선택입니다${NC}"
            ;;
    esac
}

# 로컬 모드로 모든 서비스 시작
start_all_local() {
    print_header "OARIA 개발 환경 시작 (로컬 모드)"
    echo -e "  시작 시간: $(date '+%Y-%m-%d %H:%M:%S')"

    install_dependencies
    start_docker
    sleep 2
    run_migrations
    start_admin_backend
    start_admin_frontend
    start_service_backend
    start_service_frontend

    echo ""
    show_status
}

# 모든 서비스 시작 (선택 메뉴)
start_all() {
    select_dev_mode
}

# 중지 모드 선택 메뉴
select_stop_mode() {
    echo -e "\n${CYAN}중지할 환경 선택${NC}"
    echo ""
    echo "  1) 로컬 모드    - 로컬 프로세스 + 인프라 Docker 중지"
    echo "  2) Docker 모드  - Docker 컨테이너 전체 중지"
    echo "  3) 전체 중지    - 로컬 + Docker 모두 중지"
    echo "  q) 취소"
    echo ""
    read -p "선택 (1-3, q): " choice

    case $choice in
        1)
            stop_all_local
            ;;
        2)
            stop_docker_dev
            ;;
        3)
            # 로컬 프로세스만 중지 (docker는 stop_docker_dev에서 한 번만 처리)
            stop_dev_servers
            # docker compose down은 한 번만 실행 (중복 실행 시 Docker Desktop crash 발생)
            stop_docker_dev
            ;;
        q)
            echo -e "  ${YELLOW}취소됨${NC}"
            return
            ;;
        *)
            echo -e "  ${RED}잘못된 선택입니다${NC}"
            ;;
    esac
}

# 로컬 모드 중지
stop_all_local() {
    print_header "OARIA 개발 환경 중지 (로컬 모드)"
    stop_dev_servers
    stop_docker
}

# 모든 서비스 중지 (선택 메뉴)
stop_all() {
    select_stop_mode
}

# Help 메시지 출력
show_help() {
    echo ""
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${CYAN}  OARIA 개발 환경 관리 스크립트${NC}"
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
    echo -e "${BLUE}[기본 명령어]${NC} 인터랙티브 메뉴로 로컬/Docker 모드를 선택합니다."
    echo ""
    echo -e "  ${GREEN}$0 start${NC}        개발 환경 시작 (로컬/Docker 선택)"
    echo -e "  ${GREEN}$0 stop${NC}         개발 환경 중지 (로컬/Docker 선택)"
    echo -e "  ${GREEN}$0 restart${NC}      개발 환경 재시작"
    echo -e "  ${GREEN}$0 status${NC}       모든 서비스 상태 확인"
    echo -e "  ${GREEN}$0 logs${NC}         로그 선택 보기"
    echo -e "  ${GREEN}$0 monitor${NC}      실시간 상태 모니터링 (5초마다 갱신)"
    echo ""
    echo -e "${BLUE}[로컬 개발 모드]${NC} 인프라는 Docker, 앱은 호스트에서 직접 실행합니다."
    echo -e "  ${YELLOW}장점:${NC} 빠른 Hot Reload, 디버깅 용이"
    echo ""
    echo -e "  ${GREEN}$0 local start${NC}      인프라 Docker 시작 + 로컬 앱 서버 시작"
    echo -e "  ${GREEN}$0 local stop${NC}       로컬 앱 서버 + 인프라 Docker 중지"
    echo -e "  ${GREEN}$0 local restart${NC}    로컬 모드 전체 재시작"
    echo ""
    echo -e "${BLUE}[Docker 개발 모드]${NC} 모든 서비스를 Docker 컨테이너로 실행합니다."
    echo -e "  ${YELLOW}장점:${NC} 볼륨 마운트로 Hot Reload 지원, 환경 일관성"
    echo ""
    echo -e "  ${GREEN}$0 docker-dev start${NC}     Docker 개발 모드 시작"
    echo -e "  ${GREEN}$0 docker-dev stop${NC}      Docker 개발 모드 중지"
    echo -e "  ${GREEN}$0 docker-dev restart${NC}   Docker 개발 모드 재시작"
    echo -e "  ${GREEN}$0 docker-dev rebuild${NC}   이미지 리빌드 후 시작 (캐시 무시)"
    echo ""
    echo -e "${BLUE}[Docker 프로덕션 모드]${NC} 프로덕션 환경과 동일한 설정으로 실행합니다."
    echo ""
    echo -e "  ${GREEN}$0 prod start${NC}       프로덕션 모드 시작"
    echo -e "  ${GREEN}$0 prod stop${NC}        프로덕션 모드 중지"
    echo -e "  ${GREEN}$0 prod restart${NC}     프로덕션 모드 재시작"
    echo -e "  ${GREEN}$0 prod rebuild${NC}     이미지 리빌드 후 시작 (캐시 무시)"
    echo ""
    echo -e "${BLUE}[인프라 제어]${NC} 데이터베이스, 캐시 등 인프라 서비스만 제어합니다."
    echo ""
    echo -e "  ${GREEN}$0 docker start${NC}     인프라 Docker 시작 (postgres, redis, minio, weaviate)"
    echo -e "  ${GREEN}$0 docker stop${NC}      인프라 Docker 중지"
    echo -e "  ${GREEN}$0 docker restart${NC}   인프라 Docker 재시작"
    echo ""
    echo -e "${BLUE}[로컬 서비스 개별 제어]${NC} 로컬에서 실행 중인 개별 서비스를 제어합니다."
    echo ""
    echo -e "  ${GREEN}$0 admin start${NC}      Admin Backend + Frontend 시작"
    echo -e "  ${GREEN}$0 admin stop${NC}       Admin Backend + Frontend 중지"
    echo -e "  ${GREEN}$0 admin restart${NC}    Admin Backend + Frontend 재시작"
    echo ""
    echo -e "  ${GREEN}$0 service start${NC}    Service Backend + Frontend 시작"
    echo -e "  ${GREEN}$0 service stop${NC}     Service Backend + Frontend 중지"
    echo -e "  ${GREEN}$0 service restart${NC}  Service Backend + Frontend 재시작"
    echo ""
    echo -e "${BLUE}[Docker 컨테이너 개별 제어]${NC} Docker 컨테이너를 개별적으로 제어합니다."
    echo ""
    echo -e "  ${YELLOW}단축 명령어 (기본: restart):${NC}"
    echo -e "  ${GREEN}$0 <name>${NC}                    컨테이너 재시작 (기본값)"
    echo -e "  ${GREEN}$0 <name> start${NC}              컨테이너 시작"
    echo -e "  ${GREEN}$0 <name> stop${NC}               컨테이너 중지"
    echo -e "  ${GREEN}$0 <name> restart${NC}            컨테이너 재시작"
    echo -e "  ${GREEN}$0 <name> rebuild${NC}            이미지 리빌드 후 시작"
    echo -e "  ${GREEN}$0 <name> logs${NC}               컨테이너 로그 보기"
    echo ""
    echo -e "  ${YELLOW}사용 가능한 컨테이너 <name>:${NC}"
    echo -e "    ${BLUE}[인프라]${NC}  postgres, redis, minio, weaviate"
    echo -e "    ${BLUE}[배치]${NC}    celery-backfill, celery-embed, celery-beat, flower"
    echo -e "    ${BLUE}[앱]${NC}      service-backend, service-frontend, admin-backend, admin-frontend"
    echo ""
    echo -e "  ${YELLOW}또는 container 명령어 사용:${NC}"
    echo -e "  ${GREEN}$0 container <name> [start|stop|restart|rebuild|logs]${NC}"
    echo ""
    echo -e "${BLUE}[유틸리티]${NC}"
    echo ""
    echo -e "  ${GREEN}$0 install${NC}      모든 의존성 패키지 설치 (uv sync, npm install)"
    echo -e "  ${GREEN}$0 migrate${NC}      DB 마이그레이션 실행 (Alembic, TypeORM)"
    echo ""
    echo -e "${BLUE}[서비스 URL]${NC}"
    echo ""
    echo -e "  Service Frontend:  ${CYAN}http://localhost:3000${NC}"
    echo -e "  Service Backend:   ${CYAN}http://localhost:8000${NC}"
    echo -e "  API Docs:          ${CYAN}http://localhost:8000/docs${NC}"
    echo -e "  Admin Frontend:    ${CYAN}http://localhost:13001${NC}"
    echo -e "  Admin Backend:     ${CYAN}http://localhost:13000${NC}"
    echo -e "  Flower (Celery):   ${CYAN}http://localhost:15555${NC}"
    echo -e "  MinIO Console:     ${CYAN}http://localhost:19001${NC}"
    echo ""
    echo -e "${BLUE}[예시]${NC}"
    echo ""
    echo -e "  # 처음 개발 시작할 때 (로컬 모드)"
    echo -e "  ${CYAN}$0 local start${NC}"
    echo ""
    echo -e "  # Celery 워커만 재시작 (단축)"
    echo -e "  ${CYAN}$0 celery-backfill${NC}"
    echo -e "  ${CYAN}$0 celery-backfill restart${NC}"
    echo ""
    echo -e "  # 백엔드 컨테이너 리빌드"
    echo -e "  ${CYAN}$0 service-backend rebuild${NC}"
    echo ""
    echo -e "  # Redis 로그 보기"
    echo -e "  ${CYAN}$0 redis logs${NC}"
    echo ""
    echo -e "  # 전체 Docker 개발환경 리빌드"
    echo -e "  ${CYAN}$0 docker-dev rebuild${NC}"
    echo ""
}

# 메인 명령어 처리

# Lock이 필요한 명령인지 확인 (읽기 전용 명령은 Lock 불필요)
NEEDS_LOCK=true
case "${1:-}" in
    status|logs|monitor|help|--help|-h)
        NEEDS_LOCK=false
        ;;
esac

# Lock 획득 (동시 실행 방지)
if [ "$NEEDS_LOCK" = true ]; then
    if ! acquire_lock; then
        exit 1
    fi
fi

case "${1:-}" in
    start)
        start_all
        ;;
    stop)
        stop_all
        ;;
    restart)
        stop_all
        echo -e "  ${YELLOW}▸${NC} 컨테이너 완전 종료 대기 중..."
        wait_for_compose_down 30
        sleep 3
        start_all
        ;;
    status)
        show_status
        ;;
    logs)
        show_logs
        ;;
    monitor)
        monitor
        ;;
    docker)
        case "${2:-}" in
            start) start_docker ;;
            stop) stop_docker ;;
            restart) restart_docker ;;
            *) echo "Usage: $0 docker [start|stop|restart]" ;;
        esac
        ;;
    prod)
        case "${2:-}" in
            start) start_docker_prod ;;
            stop) stop_docker_prod ;;
            restart)
                stop_docker_prod
                echo -e "  ${YELLOW}▸${NC} 컨테이너 완전 종료 대기 중..."
                wait_for_compose_down 30
                sleep 3
                start_docker_prod
                ;;
            rebuild) rebuild_docker_prod ;;
            *) echo "Usage: $0 prod [start|stop|restart|rebuild]" ;;
        esac
        ;;
    docker-dev)
        case "${2:-}" in
            start) start_docker_dev ;;
            stop) stop_docker_dev ;;
            restart)
                stop_docker_dev
                echo -e "  ${YELLOW}▸${NC} 컨테이너 완전 종료 대기 중..."
                wait_for_compose_down 30
                sleep 3
                start_docker_dev
                ;;
            rebuild) rebuild_docker_dev ;;
            *) echo "Usage: $0 docker-dev [start|stop|restart|rebuild]" ;;
        esac
        ;;
    admin)
        case "${2:-}" in
            start)
                start_admin_backend
                start_admin_frontend
                ;;
            stop)
                stop_service "admin-backend" 13000
                stop_service "admin-frontend" 13001
                ;;
            restart) restart_admin ;;
            *) echo "Usage: $0 admin [start|stop|restart]" ;;
        esac
        ;;
    service)
        case "${2:-}" in
            start)
                start_service_backend
                start_service_frontend
                ;;
            stop)
                stop_service "service-backend" 8000
                stop_service "service-frontend" 3000
                ;;
            restart) restart_service_local ;;
            *) echo "Usage: $0 service [start|stop|restart]" ;;
        esac
        ;;
    local)
        case "${2:-}" in
            start) start_all_local ;;
            stop) stop_all_local ;;
            restart)
                stop_all_local
                echo -e "  ${YELLOW}▸${NC} 컨테이너 완전 종료 대기 중..."
                wait_for_compose_down 30
                sleep 3
                start_all_local
                ;;
            *) echo "Usage: $0 local [start|stop|restart]" ;;
        esac
        ;;
    container)
        if [ -z "${2:-}" ] || [ -z "${3:-}" ]; then
            echo -e "${RED}오류: 컨테이너 이름과 액션이 필요합니다${NC}"
            echo ""
            echo "Usage: $0 container <name> [start|stop|restart|rebuild|logs]"
            echo ""
            echo -e "${YELLOW}사용 가능한 컨테이너:${NC}"
            echo -e "  ${BLUE}[인프라]${NC}"
            echo "    postgres, redis, minio, weaviate"
            echo -e "  ${BLUE}[배치]${NC}"
            echo "    celery-backfill, celery-embed, celery-beat, flower"
            echo -e "  ${BLUE}[앱]${NC}"
            echo "    service-backend, service-frontend, admin-backend, admin-frontend"
            exit 1
        fi
        container_control "$2" "$3"
        ;;
    # 개별 컨테이너 단축 명령어 (인프라)
    postgres|redis|minio|weaviate)
        container_control "$1" "${2:-restart}"
        ;;
    # 개별 컨테이너 단축 명령어 (배치)
    celery-backfill|celery-embed|celery-beat|flower)
        container_control "$1" "${2:-restart}"
        ;;
    # 개별 컨테이너 단축 명령어 (앱 - Docker)
    service-backend|service-frontend|admin-backend|admin-frontend)
        container_control "$1" "${2:-restart}"
        ;;
    migrate)
        run_migrations
        ;;
    install)
        install_dependencies
        ;;
    help|--help|-h)
        show_help
        ;;
    *)
        echo -e "${RED}알 수 없는 명령어: $1${NC}"
        echo ""
        echo "도움말: $0 help"
        exit 1
        ;;
esac
