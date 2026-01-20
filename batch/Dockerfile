# 암 논문 수집 배치 시스템 (Celery Worker)
# 빌드 컨텍스트: batch/ 디렉토리에서 실행
# docker build -t oaria-batch ./batch

FROM python:3.11-slim

WORKDIR /app

# 시스템 패키지 설치
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# uv 설치
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# 소스코드 및 의존성 파일 복사
COPY pyproject.toml ./
COPY src/ ./src/

# 의존성 설치
RUN uv pip install --system --no-cache .

# 환경 변수 기본값
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# 헬스체크
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD celery -A src.celery_app inspect ping -d celery@$HOSTNAME || exit 1

# 기본 명령어 (워커)
CMD ["celery", "-A", "src.celery_app", "worker", "--loglevel=info"]
