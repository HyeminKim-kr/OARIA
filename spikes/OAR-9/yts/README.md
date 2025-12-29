# OAR-9: 논문 수집 파이프라인

Europe PMC에서 논문을 수집하여 PostgreSQL + S3에 저장하는 통합 파이프라인

## 구성

```
spikes/OAR-9/yts/
├── docker/
│   ├── docker-compose.yml    # PostgreSQL + MinIO
│   └── init/
│       └── 01-schema.sql     # DB 스키마 초기화
├── src/
│   ├── __init__.py
│   ├── config.py             # 설정 관리
│   ├── models.py             # 데이터 모델
│   ├── europe_pmc_client.py  # API 클라이언트
│   ├── preprocess.py         # 텍스트 전처리
│   ├── parser.py             # XML 파싱
│   ├── storage.py            # DB/S3 저장
│   └── pipeline.py           # 통합 파이프라인
├── demo_app.py               # Streamlit 데모
└── pyproject.toml
```

## 통합된 스파이크

- **OAR-18**: Europe PMC API 연동
- **OAR-19**: 메타데이터 파싱 로직
- **OAR-20**: PostgreSQL 스키마

## 빠른 시작

### 1. 인프라 시작

```bash
cd spikes/OAR-9/yts
docker compose -f docker/docker-compose.yml up -d
```

- PostgreSQL: `localhost:5432`
- MinIO: `localhost:9000` (콘솔: `localhost:9001`)

### 2. 의존성 설치

```bash
uv sync
```

### 3. 데모 실행

```bash
uv run streamlit run demo_app.py
```

## 파이프라인 흐름

```
┌─────────────────────────────────────────────────────────────────┐
│  1. 검색 (Europe PMC Search API)                                │
│     query: "lung cancer" → 논문 목록 (PMID, PMCID)             │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│  2. 수집 (Full Text XML)                                        │
│     PMCID → XML 원본 (병렬 처리, max_concurrent=10)            │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│  3. 파싱                                                         │
│     XML → ParsedPaper (메타데이터, 저자, 섹션, canonical_text) │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                ┌───────────────┴───────────────┐
                │                               │
                ▼                               ▼
┌───────────────────────────┐   ┌───────────────────────────┐
│  4a. PostgreSQL 저장       │   │  4b. S3 저장               │
│  - papers                  │   │  - canonical/{id}/v1.txt  │
│  - paper_authors           │   │  - canonical/{id}/ver.json│
│  - paper_sections          │   │                           │
└───────────────────────────┘   └───────────────────────────┘
```

## 코드 사용 예시

### Python에서 직접 사용

```python
import asyncio
from src.pipeline import Pipeline
from src.config import Config

async def main():
    config = Config.from_env()
    pipeline = Pipeline(config)

    result = await pipeline.run(
        query="lung cancer",
        limit=10,
        max_concurrent=10,
        save_to_db=True,
        save_to_s3=True,
    )

    print(f"성공: {result.success}/{result.total}")
    for paper in result.papers:
        print(f"  - {paper.paper_id}: {paper.title[:50]}...")

asyncio.run(main())
```

### 단일 논문 수집

```python
async def collect_one():
    pipeline = Pipeline()
    paper = await pipeline.collect_single(
        pmcid="PMC12345678",
        save_to_db=True,
        save_to_s3=True,
    )
    if paper:
        print(f"수집 완료: {paper.paper_id}")

asyncio.run(collect_one())
```

## 환경변수

| 변수 | 기본값 | 설명 |
|------|--------|------|
| `DB_HOST` | localhost | PostgreSQL 호스트 |
| `DB_PORT` | 5432 | PostgreSQL 포트 |
| `DB_USER` | oaria | 데이터베이스 사용자 |
| `DB_PASSWORD` | oaria123 | 데이터베이스 비밀번호 |
| `DB_NAME` | oaria | 데이터베이스 이름 |
| `S3_ENDPOINT` | http://localhost:9000 | S3/MinIO 엔드포인트 |
| `S3_ACCESS_KEY` | minioadmin | S3 액세스 키 |
| `S3_SECRET_KEY` | minioadmin | S3 시크릿 키 |
| `S3_BUCKET` | oaria-papers | S3 버킷 이름 |
| `API_MAX_CONCURRENT` | 10 | 동시 API 요청 수 |
| `API_DELAY` | 0.1 | 요청 간 지연 (초) |

## 다음 단계

- **Phase 2**: 어드민 UI (NestJS + NextJS)
  - 검색 쿼리 관리
  - 배치 작업 모니터링

- **Phase 3**: Celery 배치 시스템
  - 초기 적재 (Backfill)
  - 증분 수집 (Incremental)
  - 보정 (Reconciliation)
