#!/bin/bash

# ============================================================
# OARIA 개발 환경 시작 및 모니터링 스크립트
# ============================================================
#
# 기본 명령어 (인터랙티브):
#   ./scripts/dev.sh start     - 개발 환경 시작 (로컬/Docker 선택)
#   ./scripts/dev.sh stop      - 개발 환경 중지
#   ./scripts/dev.sh restart   - 재시작
#   ./scripts/dev.sh status    - 상태 확인
#   ./scripts/dev.sh logs      - 로그 보기
#   ./scripts/dev.sh monitor   - 실시간 모니터링
#
# Docker 모드 (직접 실행):
#   ./scripts/dev.sh prod start/stop/restart        - 프로덕션 모드
#   ./scripts/dev.sh docker-dev start/stop/restart  - 개발 모드 (Hot Reload)
#
# 개별 제어 (로컬):
#   ./scripts/dev.sh docker start/stop   - 인프라만 (DB, Redis 등)
#   ./scripts/dev.sh admin start/stop    - Admin 서비스만
#   ./scripts/dev.sh service start/stop  - User 서비스만
#   ./scripts/dev.sh install             - 의존성 설치
#   ./scripts/dev.sh migrate             - DB 마이그레이션
#
# ============================================================

set -e

# 프로젝트 루트 디렉토리
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
LOG_DIR="$PROJECT_ROOT/.dev-logs"

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
    cd "$PROJECT_ROOT"
    docker compose -f docker-compose.yml -f docker-compose.prod.yml down
    echo -e "  ${GREEN}✓${NC} 프로덕션 서비스 중지됨"
}

# Docker 개발 모드 시작
start_docker_dev() {
    print_header "Docker Compose 시작 (개발 모드 - Hot Reload)"

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
    cd "$PROJECT_ROOT"
    docker compose -f docker-compose.yml -f docker-compose.dev.yml down
    echo -e "  ${GREEN}✓${NC} 개발 서비스 중지됨"
}

# Docker 서비스 중지
stop_docker() {
    print_header "Docker Compose 중지"
    cd "$PROJECT_ROOT"
    docker compose down
    echo -e "  ${GREEN}✓${NC} Docker 서비스 중지됨"
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

# 상태 확인
show_status() {
    print_header "서비스 상태"

    echo -e "\n${BLUE}[Docker 서비스]${NC}"

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

# 메인 명령어 처리
case "${1:-}" in
    start)
        start_all
        ;;
    stop)
        stop_all
        ;;
    restart)
        stop_all
        sleep 2
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
            *) echo "Usage: $0 docker [start|stop]" ;;
        esac
        ;;
    prod)
        case "${2:-}" in
            start) start_docker_prod ;;
            stop) stop_docker_prod ;;
            restart)
                stop_docker_prod
                sleep 2
                start_docker_prod
                ;;
            *) echo "Usage: $0 prod [start|stop|restart]" ;;
        esac
        ;;
    docker-dev)
        case "${2:-}" in
            start) start_docker_dev ;;
            stop) stop_docker_dev ;;
            restart)
                stop_docker_dev
                sleep 2
                start_docker_dev
                ;;
            *) echo "Usage: $0 docker-dev [start|stop|restart]" ;;
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
            *) echo "Usage: $0 admin [start|stop]" ;;
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
            *) echo "Usage: $0 service [start|stop]" ;;
        esac
        ;;
    migrate)
        run_migrations
        ;;
    install)
        install_dependencies
        ;;
    *)
        echo -e "${CYAN}OARIA 개발 환경 관리 스크립트${NC}"
        echo ""
        echo -e "${BLUE}기본 명령어 (인터랙티브 선택):${NC}"
        echo "  $0 start        개발 환경 시작 (로컬/Docker 선택)"
        echo "  $0 stop         개발 환경 중지 (로컬/Docker 선택)"
        echo "  $0 restart      개발 환경 재시작"
        echo "  $0 status       서비스 상태 확인"
        echo "  $0 logs         로그 보기"
        echo "  $0 monitor      실시간 모니터링 (5초마다 갱신)"
        echo ""
        echo -e "${BLUE}직접 실행 (선택 없이):${NC}"
        echo "  $0 prod start/stop/restart         프로덕션 모드 (Docker)"
        echo "  $0 docker-dev start/stop/restart   개발 모드 (Docker + Hot Reload)"
        echo ""
        echo -e "${BLUE}개별 제어:${NC}"
        echo "  $0 docker start/stop    인프라만 시작/중지 (DB, Redis 등)"
        echo "  $0 admin start/stop     Admin 서비스만 시작/중지 (로컬)"
        echo "  $0 service start/stop   User 서비스만 시작/중지 (로컬)"
        echo "  $0 install              의존성 패키지 설치"
        echo "  $0 migrate              DB 마이그레이션만 실행"
        ;;
esac
