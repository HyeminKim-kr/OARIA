# OARIA Literature System - 완료 보고서

## 구현 완료 ✅

PubMed/PMC ETL → SQL → Embedding → Qdrant → Evidence RAG 전체 파이프라인을 구현했습니다.

위치: `oaria/spikes/2025-01-scraped-literature-data/`

## 프로젝트 구조

```sh
2025-01-scraped-literature-data/
├── README.md                          # 스파이크 문서
├── docker-compose.yml                 # 메인 Compose
├── docker-compose.override.local.yml  # Local 모드
├── docker-compose.override.gcp.yml    # GCP 모드
├── .env.example                       # 환경변수 템플릿
├── notes.md                           # 실험 노트
├── backend/
│   ├── Dockerfile
│   ├── pyproject.toml
│   └── src/
│       ├── main.py              # FastAPI 엔드포인트
│       ├── config.py            # 환경 설정
│       ├── db.py                # SQLAlchemy
│       ├── storage_adapter.py   # Local/GCS 스위치
│       ├── pubmed_client.py     # E-utilities
│       ├── etl_worker.py        # ETL 파이프라인
│       ├── embedding_worker.py  # PubMedBERT
│       ├── qdrant_client.py     # 벡터 DB
│       └── models/              # ORM + Pydantic
└── frontend/
    ├── Dockerfile
    ├── package.json
    ├── next.config.js
    └── src/pages/
        ├── index.tsx          # 검색 UI
        ├── dashboard.tsx      # ETL 대시보드
        └── evidence.tsx       # 의미 검색
```

---

## 핵심 기능

### 1. Dual Mode (Local/GCP)

```sh
## Local 모드 (기본)
docker-compose up --build

## GCP 모드
docker-compose -f docker-compose.yml -f docker-compose.override.gcp.yml up
```

### 2. Backend API

| Endpoint                  | Description    |
|---------------------------|----------------|
| **GET** `/api/health`           | 헬스체크 |
| **GET** `/api/pubmed/count`     | PubMed 검색 건수 조회 |
| **POST** `/api/etl/start`       | ETL 프로세스 시작 |
| **GET** `/api/papers`           | 저장된 논문 목록 조회 |
| **POST** `/api/search/semantic` | 의미 기반 검색 (Semantic Search) |
| **POST** `/api/embedding/process` | 임베딩 처리 실행 |

### 3. Frontend Pages

- 검색 (/): PubMed 검색, ETL 시작, 미리보기
- 대시보드 (/dashboard): 저장된 논문, 임베딩 상태
- Evidence (/evidence): Qdrant 의미 검색

## 실행 방법

```sh
cd oaria/spikes/2025-01-scraped-literature-data

# 1. Docker Compose 실행
docker-compose up --build

# 2. 접속
# - Frontend: http://localhost:3000
# - Backend API: http://localhost:8000/docs
# - Qdrant: http://localhost:6333/dashboard
```
