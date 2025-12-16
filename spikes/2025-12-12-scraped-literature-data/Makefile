# OARIA Literature - Makefile
# Docker Compose 명령어를 간편하게 실행
#
# 이미지 태깅 전략:
# - oaria-lit-backend:latest, oaria-lit-frontend:latest 사용
# - 빌드 시 자동으로 <none> 이미지 정리
# - make clean-images로 수동 정리 가능

.PHONY: help up down build logs clean dev-backend dev-frontend

# 기본 명령어
help:
	@echo "🔬 OARIA Literature - 사용 가능한 명령어"
	@echo ""
	@echo "📦 Docker 실행:"
	@echo "  make up         - 전체 스택 실행 (빌드 + 정리)"
	@echo "  make up-d       - 백그라운드 실행"
	@echo "  make down       - 스택 중지"
	@echo "  make restart    - 재시작 (down + up)"
	@echo "  make rebuild    - 완전 재빌드 (down + clean + up)"
	@echo ""
	@echo "🔧 빌드 & 정리:"
	@echo "  make build      - 이미지 빌드만"
	@echo "  make clean-images - <none> 이미지 정리"
	@echo "  make clean      - 볼륨 포함 전체 삭제"
	@echo "  make deep-clean - Docker 전체 정리 (⚠️ 주의)"
	@echo ""
	@echo "📋 로그:"
	@echo "  make logs       - 전체 로그"
	@echo "  make logs-b     - 백엔드 로그"
	@echo "  make logs-f     - 프론트엔드 로그"
	@echo ""
	@echo "💻 개발 모드:"
	@echo "  make dev-backend  - 백엔드만 로컬 실행"
	@echo "  make dev-frontend - 프론트엔드만 로컬 실행"
	@echo ""

# =============================================================================
# Docker 실행/중지
# =============================================================================

# 전체 스택 실행 (빌드 후 <none> 이미지 자동 정리)
up:
	@echo "🚀 OARIA Literature 시작 중..."
	docker-compose up --build --remove-orphans
	@$(MAKE) clean-images --silent

# 백그라운드 실행
up-d:
	@echo "🚀 OARIA Literature 백그라운드 시작..."
	docker-compose up --build --remove-orphans -d
	@$(MAKE) clean-images --silent
	@echo "✅ 실행 완료! http://localhost:3000"

# 중지
down:
	@echo "🛑 OARIA Literature 중지 중..."
	docker-compose down
	@$(MAKE) clean-images --silent

# 재시작 (빠른 재시작, 백그라운드)
restart:
	@$(MAKE) down
	@$(MAKE) up-d

# 완전 재빌드 (볼륨 삭제 + 클린 빌드)
# clean에서 down -v를 포함하므로 down 별도 호출 불필요
rebuild:
	@echo "🔄 완전 재빌드 시작 (clean + up)..."
	@$(MAKE) clean
	@$(MAKE) up

# =============================================================================
# 빌드 & 정리
# =============================================================================

# 이미지 빌드만
build:
	docker-compose build

# <none> 태그 이미지만 정리 (안전함)
clean-images:
	@echo "🧹 <none> 이미지 정리 중..."
	@docker images -f "dangling=true" -q | xargs -r docker rmi 2>/dev/null || true
	@echo "✅ 정리 완료"

# 전체 삭제 (볼륨 포함)
clean:
	docker-compose down -v --rmi local
	@$(MAKE) clean-images

# Docker 전체 정리 (⚠️ 주의: 모든 미사용 리소스 삭제)
deep-clean:
	docker-compose down -v --rmi all
	docker system prune -a --volumes -f

# =============================================================================
# 로그
# =============================================================================

logs:
	docker-compose logs -f

logs-b:
	docker-compose logs -f backend

logs-f:
	docker-compose logs -f frontend

# =============================================================================
# 개발 모드
# =============================================================================

dev-backend:
	cd backend && uv sync && uv run uvicorn src.main:app --reload --port 8000

dev-frontend:
	cd frontend && npm install --legacy-peer-deps && npm run dev

# =============================================================================
# Database Management
# =============================================================================

db-init:
	curl -X POST http://localhost:8000/api/db/init

db-reset:
	curl -X POST "http://localhost:8000/api/db/reset?confirm=yes"

db-stats:
	@curl -s http://localhost:8000/api/db/stats | python3 -m json.tool

# =============================================================================
# 상태 확인
# =============================================================================

# Docker 이미지 목록
images:
	@echo "📦 OARIA 관련 Docker 이미지:"
	@docker images | grep -E "oaria|2025-01-scraped" || echo "  (없음)"
	@echo ""
	@echo "⚠️ <none> 이미지:"
	@docker images -f "dangling=true" | head -10 || echo "  (없음)"

# 컨테이너 상태
status:
	@echo "📊 컨테이너 상태:"
	@docker-compose ps
