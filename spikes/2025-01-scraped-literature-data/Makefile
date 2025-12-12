# OARIA Literature - Makefile
# Docker Compose 명령어를 간편하게 실행

.PHONY: help up down build logs clean dev-backend dev-frontend

# 기본 명령어
help:
	@echo "🔬 OARIA Literature - 사용 가능한 명령어"
	@echo ""
	@echo "  make up         - 전체 스택 실행 (Local 모드)"
	@echo "  make up-gcp     - 전체 스택 실행 (GCP 모드)"
	@echo "  make down       - 전체 스택 중지"
	@echo "  make build      - 이미지 빌드"
	@echo "  make logs       - 로그 보기"
	@echo "  make clean      - 볼륨 포함 전체 삭제"
	@echo "  make prune      - Docker dangling 이미지/볼륨 정리"
	@echo "  make deep-clean - Docker 전체 정리 (⚠️ 주의)"
	@echo ""
	@echo "  make dev-backend  - 백엔드만 개발 모드 실행"
	@echo "  make dev-frontend - 프론트엔드만 개발 모드 실행"
	@echo ""

# Local 모드 실행
up:
	docker-compose -f docker-compose.yml -f docker-compose.override.local.yml up --build

# GCP 모드 실행
up-gcp:
	docker-compose -f docker-compose.yml -f docker-compose.override.gcp.yml up --build

# 백그라운드 실행
up-d:
	docker-compose -f docker-compose.yml -f docker-compose.override.local.yml up --build -d

# 중지
down:
	docker-compose down

# 빌드만
build:
	docker-compose build

# 로그 보기
logs:
	docker-compose logs -f

# 특정 서비스 로그
logs-backend:
	docker-compose logs -f backend

logs-frontend:
	docker-compose logs -f frontend

# 전체 삭제 (볼륨 포함)
clean:
	docker-compose down -v --rmi local

# Docker 정리 (dangling 이미지만)
prune:
	docker image prune -f
	docker volume prune -f

# Docker 전체 정리 (주의: 모든 미사용 리소스 삭제)
deep-clean:
	docker-compose down -v --rmi all
	docker system prune -a --volumes -f

# 개발 모드 - 백엔드만
dev-backend:
	cd backend && uv sync && uv run uvicorn src.main:app --reload --port 8000

# 개발 모드 - 프론트엔드만
dev-frontend:
	cd frontend && npm install --legacy-peer-deps && npm run dev

# =============================================================================
# Database Management
# =============================================================================

# DB 초기화 (테이블 생성)
db-init:
	curl -X POST http://localhost:8000/api/db/init

# DB 리셋 (⚠️ 모든 데이터 삭제)
db-reset:
	curl -X POST "http://localhost:8000/api/db/reset?confirm=yes"

# DB 통계 조회
db-stats:
	curl http://localhost:8000/api/db/stats | python3 -m json.tool
