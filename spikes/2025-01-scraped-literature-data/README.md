# 2025-01-scraped-literature-data

PubMed/PMC ETL → SQL/GCS 저장 → Embedding → Qdrant → Evidence RAG 구조를 검증하기 위한 스파이크.

## Background

OARIA Bio 연구 플랫폼의 논문 수집 및 검색 파이프라인을 실험합니다:

- PubMed 메타데이터 + Abstract 수집
- PMC Open Access Full-text 수집
- PubMedBERT 기반 의미 검색
- RAG Evidence 생성

## Goal

- [x] PubMed 메타데이터 SQL 저장 확인
- [ ] Full text GCS/Local 저장 실험
- [ ] Embedding Worker → Qdrant 저장 실험
- [ ] Local/GCP 모드 전환 검증
- [ ] RAG 파이프라인 검증

## Tech Stack

- **Backend**: Python 3.11, FastAPI, SQLAlchemy, httpx
- **Frontend**: Next.js 15, React 19, TypeScript
- **Database**: PostgreSQL 16
- **Vector DB**: Qdrant
- **Embedding**: PubMedBERT (sentence-transformers)
- **Infra**: Docker Compose (local/gcp dual mode)

## How to Run

### Make 사용 (권장)

```bash
# 전체 스택 실행 (Local 모드)
make up

# GCP 모드 실행
make up-gcp

# 백그라운드 실행
make up-d

# 중지
make down

# 로그 보기
make logs

# 전체 삭제 (볼륨 포함)
make clean

# 도움말
make help
```

### 개별 서비스 실행 (개발용)

```bash
make dev-backend   # 백엔드만
make dev-frontend  # 프론트엔드만
```

### 접속 URL

- **Frontend**: <http://localhost:3000>
- **Backend API**: <http://localhost:8000/docs>
- **Qdrant Dashboard**: <http://localhost:6333/dashboard>

---

<details>
<summary>📦 Docker Compose 직접 실행 (Optional)</summary>

```bash
# Local 모드
docker-compose -f docker-compose.yml -f docker-compose.override.local.yml up --build

# 또는 간단히
docker-compose up --build

# GCP 모드
cp .env.example .env  # DATABASE_URL, GCS_BUCKET 등 설정
docker-compose -f docker-compose.yml -f docker-compose.override.gcp.yml up --build

# 개별 실행
cd backend && uv sync && uv run uvicorn src.main:app --reload --port 8000
cd frontend && npm install --legacy-peer-deps && npm run dev
```

</details>

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/health` | 헬스체크 |
| GET | `/api/pubmed/count?term=...` | 검색 건수 조회 |
| POST | `/api/etl/start` | ETL 시작 |
| GET | `/api/etl/status` | ETL 상태 |
| POST | `/api/search/semantic` | 의미 검색 (Qdrant) |
| GET | `/api/papers` | 저장된 논문 목록 |

## Ports

| Service | Port |
|---------|------|
| Backend (FastAPI) | 8000 |
| Frontend (Next.js) | 3000 |
| PostgreSQL | 5432 |
| Qdrant | 6333 |

## Findings

(실험 후 업데이트)

## Decision

⏸︎ 진행 중 - 실험 결과에 따라 backend/, frontend/ 공식 구조에 반영 예정
