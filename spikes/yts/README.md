# OARIA - Cancer Paper Collection & Embedding Service

암 연구 논문 자동 수집, 청킹, 임베딩 및 벡터 검색 시스템

## 아키텍처

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Docker Compose Stack                         │
├─────────────────────────────────────────────────────────────────────┤
│  인프라                                                              │
│  ├── postgres (15432)      - 메타데이터 저장                          │
│  ├── redis (16379)         - Celery 브로커                           │
│  ├── minio (19000/19001)   - 논문 원문 저장 (S3 호환)                  │
│  └── weaviate (18080)      - 벡터 저장소                              │
├─────────────────────────────────────────────────────────────────────┤
│  Celery 워커                                                         │
│  ├── celery-worker-backfill - 논문 수집 워커                          │
│  ├── celery-worker-embed    - 청킹/임베딩 워커                         │
│  ├── celery-beat            - 스케줄러 (매시간 임베딩)                  │
│  └── flower (15555)         - 모니터링 대시보드                        │
├─────────────────────────────────────────────────────────────────────┤
│  Admin                                                               │
│  ├── admin-backend (13000)  - NestJS API                             │
│  └── admin-frontend (13001) - Next.js UI                             │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
              ┌─────────────────────────┐
              │     Europe PMC API      │
              │  (Paper Collection)     │
              └─────────────────────────┘
```

## 빠른 시작

### 옵션 1: Docker Compose (권장)

```bash
# 1. 환경 변수 설정
cp .env.example .env
# .env 파일에서 OPENAI_API_KEY 설정

# 2. 전체 서비스 실행
docker-compose up -d

# 3. 로그 확인
docker-compose logs -f
```

### 옵션 2: 개발 모드 (인프라만 Docker)

```bash
# 1. 인프라만 실행
docker-compose up -d postgres redis minio weaviate minio-init

# 2. 배치 워커 로컬 실행
cd batch
uv run celery -A src.celery_app worker -Q backfill,embed --loglevel=info

# 3. Admin 백엔드 로컬 실행
cd admin/backend
npm install && npm run start:dev

# 4. Admin 프론트엔드 로컬 실행
cd admin/frontend
npm install && npm run dev
```

## 서비스 URL

| 서비스 | URL | 설명 |
|--------|-----|------|
| Admin UI | http://localhost:13001 | 어드민 대시보드 |
| Admin API | http://localhost:13000 | REST API |
| Swagger | http://localhost:13000/api | API 문서 |
| Flower | http://localhost:15555 | Celery 모니터링 |
| MinIO Console | http://localhost:19001 | 오브젝트 스토리지 |
| Weaviate | http://localhost:18080 | 벡터 DB |

## 주요 기능

### 논문 수집 (Backfill)
- Europe PMC API를 통한 암 논문 수집
- Rate Limiting + Circuit Breaker
- Checkpoint 기반 중단점 복구

### 임베딩 파이프라인
- **Chunking**: OAR-29 TextChunker (섹션 + 재귀 청킹)
- **Embedding**: OpenAI text-embedding-3-small
- **Storage**: Weaviate 벡터 DB

### Celery Beat 스케줄

| 태스크 | 스케줄 | 설명 |
|--------|--------|------|
| `embed-hourly` | 매시 정각 | 새 논문 50개씩 임베딩 |
| `reembed-daily` | 매일 03:00 | 실패한 논문 재임베딩 |

### Admin UI
- **Dashboard**: 수집/임베딩 현황 개요
- **Search Queries**: 검색 쿼리 관리 (CRUD)
- **Collection Jobs**: 수집 작업 모니터링
- **Papers**: 수집된 논문 목록 + 임베딩 상태

## 프로젝트 구조

```
yts/
├── docker-compose.yml        # 전체 스택 정의
├── .env.example              # 환경 변수 템플릿
├── infra/                    # DB 초기화 스크립트
│   └── init/
├── batch/                    # Celery 배치 시스템
│   ├── Dockerfile
│   ├── src/
│   │   ├── celery_app.py     # Celery 설정 + Beat 스케줄
│   │   ├── tasks/
│   │   │   ├── backfill.py   # 논문 수집 태스크
│   │   │   └── embed.py      # 임베딩 태스크
│   │   ├── collectors/       # API 클라이언트
│   │   ├── parsers/          # XML 파서
│   │   └── storage/          # DB/S3 저장
│   └── pyproject.toml
├── admin/
│   ├── backend/              # NestJS API
│   │   ├── Dockerfile
│   │   └── src/
│   └── frontend/             # Next.js UI
│       ├── Dockerfile
│       └── src/
└── README.md
```

## 환경 변수

### .env (필수)
```env
OPENAI_API_KEY=sk-your-openai-api-key-here
```

### 기타 환경 변수 (docker-compose에 기본값 설정됨)
- `DATABASE_URL` - PostgreSQL 연결 문자열
- `REDIS_URL` - Redis 연결 문자열
- `S3_ENDPOINT`, `S3_ACCESS_KEY`, `S3_SECRET_KEY` - MinIO 설정
- `WEAVIATE_HOST`, `WEAVIATE_PORT` - Weaviate 설정

## 트러블슈팅

### 임베딩 실패 시
1. Admin UI → Papers → "실패" 필터로 확인
2. 에러 메시지 확인
3. "재시도" 버튼으로 재실행

### Weaviate 연결 오류
```bash
curl http://localhost:18080/v1/.well-known/ready
```

### OpenAI API 오류
`.env` 파일에 `OPENAI_API_KEY`가 올바르게 설정되었는지 확인

## 라이선스

Internal Use Only
