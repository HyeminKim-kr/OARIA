# 암 논문 수집 배치 시스템 (Celery Worker)
# 빌드 컨텍스트: spikes/ 폴더에서 실행
# docker build -f yts/batch/Dockerfile -t oaria-batch .

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

# 모든 의존성 설치 (batch + OAR-29 + OAR-31)
RUN uv pip install --system --no-cache \
    # Celery
    "celery[redis]>=5.3.0" \
    "flower>=2.0.0" \
    # HTTP Client
    "httpx>=0.27.0" \
    # Database
    "asyncpg>=0.29.0" \
    "psycopg[binary,pool]>=3.1.0" \
    # S3
    "boto3>=1.34.0" \
    # XML Parsing
    "lxml>=5.0.0" \
    # Data Validation
    "pydantic>=2.5.0" \
    "pydantic-settings>=2.1.0" \
    # Utilities
    "structlog>=24.1.0" \
    "tenacity>=8.2.0" \
    # OAR-29 (Chunker)
    "tiktoken>=0.7.0" \
    # OAR-31 (Vector Store)
    "weaviate-client>=4.9.0" \
    "openai>=1.0.0"

# 소스코드 복사 (빌드 컨텍스트: spikes/)
# batch 소스
COPY yts/batch/src/ ./src/

# OAR-29 (Chunker) 소스
COPY OAR-29/yts/src/ ./spikes/OAR-29/yts/src/

# OAR-31 (Vector Store) 소스
COPY OAR-31/yts/src/ ./spikes/OAR-31/yts/src/

# 환경 변수 기본값
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# 헬스체크
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD celery -A src.celery_app inspect ping -d celery@$HOSTNAME || exit 1

# 기본 명령어 (워커)
CMD ["celery", "-A", "src.celery_app", "worker", "--loglevel=info"]
