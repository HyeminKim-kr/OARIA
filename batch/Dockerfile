# ==============================================
# 암 논문 수집 배치 시스템 (Celery Worker)
# ==============================================
# 빌드: docker build -t oaria-batch ./batch
#
# CPU 전용 PyTorch 사용 (pyproject.toml의 tool.uv.sources 설정)
# - CUDA 버전 대비 ~90% 용량 감소 (2GB+ → ~200MB)
# - GCP Cloud Run은 GPU 미지원이므로 CPU 버전으로 충분

# ==============================================
# Stage 1: Builder
# ==============================================
FROM python:3.11-slim AS builder

WORKDIR /app

# 빌드 의존성 설치
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# uv 설치
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# 의존성 파일 복사 (캐싱 최적화)
COPY pyproject.toml ./

# 가상환경 생성 및 의존성 설치
# - tool.uv.sources 설정에 따라 CPU 전용 PyTorch 설치
ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy
RUN mkdir -p src && touch src/__init__.py && \
    uv sync --no-dev && \
    rm -rf src

# 소스코드 복사
COPY src/ ./src/

# ==============================================
# Stage 2: Runner (Production)
# ==============================================
FROM python:3.11-slim AS runner

WORKDIR /app

# 런타임 의존성만 설치
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# 보안: non-root user 생성
RUN groupadd --system --gid 1001 appgroup && \
    useradd --system --uid 1001 --gid appgroup appuser

# 가상환경 및 소스코드 복사
COPY --from=builder /app/.venv /app/.venv
COPY --from=builder --chown=appuser:appgroup /app/src ./src

# PATH 설정
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# non-root user로 전환
USER appuser

# 헬스체크
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD celery -A src.celery_app inspect ping -d celery@$HOSTNAME || exit 1

# 기본 명령어 (워커)
CMD ["celery", "-A", "src.celery_app", "worker", "--loglevel=info"]
