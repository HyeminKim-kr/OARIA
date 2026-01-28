# 암 논문 수집 배치 시스템 (Celery Worker)
# 빌드 컨텍스트: batch/ 디렉토리에서 실행
# docker build -t oaria-batch ./batch

FROM python:3.11-slim

WORKDIR /app

# 환경 변수 기본값
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# 시스템 패키지 설치
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# uv 설치
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# ============================================================
# 레이어 캐싱 최적화
# - 의존성 파일만 먼저 복사하여 소스 변경 시 재설치 방지
# ============================================================

# 1. 의존성 파일만 먼저 복사
COPY pyproject.toml ./

# 2. CPU 전용 PyTorch 먼저 설치 (CUDA 버전 대비 ~90% 용량 감소)
#    - MacBook Docker 환경에서는 GPU 사용 불가하므로 CPU 버전으로 충분
RUN uv pip install --system \
    torch --index-url https://download.pytorch.org/whl/cpu

# 3. 나머지 의존성 설치
#    - pyproject.toml의 "." 설치를 위해 임시 src 폴더 생성
RUN mkdir -p src && touch src/__init__.py && \
    uv pip install --system . && \
    rm -rf src

# 4. 소스코드 복사 (자주 변경되므로 마지막에)
COPY src/ ./src/

# 헬스체크
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD celery -A src.celery_app inspect ping -d celery@$HOSTNAME || exit 1

# 기본 명령어 (워커)
CMD ["celery", "-A", "src.celery_app", "worker", "--loglevel=info"]
