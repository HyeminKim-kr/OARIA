# ==============================================
# Stage 1: Builder
# ==============================================
FROM python:3.11-slim AS builder

WORKDIR /app

# 빌드 의존성 설치
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# uv 설치 (빠른 패키지 매니저)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# 의존성 파일 복사 (캐싱 최적화)
COPY pyproject.toml uv.lock* ./

# 가상환경 생성 및 의존성 설치 (프로덕션 의존성만)
ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy
RUN uv sync --no-dev

# ==============================================
# Stage 2: Runner (Production)
# ==============================================
FROM python:3.11-slim AS runner

WORKDIR /app

# 런타임 의존성만 설치
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# 보안: non-root user 생성
RUN groupadd --system --gid 1001 appgroup && \
    useradd --system --uid 1001 --gid appgroup appuser

# 가상환경 복사 (--link로 효율적인 레이어 처리)
COPY --link --from=builder /app/.venv /app/.venv

# 소스 코드 복사
COPY --chown=appuser:appgroup ./app ./app
COPY --chown=appuser:appgroup ./alembic ./alembic
COPY --chown=appuser:appgroup ./alembic.ini ./

# PATH 설정
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# non-root user로 전환
USER appuser

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
