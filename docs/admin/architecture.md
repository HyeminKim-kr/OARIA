# OARIA 시스템 아키텍처

## 개요

OARIA는 암 연구 논문을 자동 수집하고, 청킹/임베딩하여 벡터 검색을 가능하게 하는 시스템입니다.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              사용자 인터페이스                                 │
│  ┌──────────────────────┐    ┌──────────────────────┐                       │
│  │   Admin Frontend     │    │   User Frontend      │                       │
│  │   (Next.js :13001)   │    │   (Next.js :3000)    │                       │
│  └──────────┬───────────┘    └──────────┬───────────┘                       │
│             │                           │                                    │
│             ▼                           ▼                                    │
│  ┌──────────────────────┐    ┌──────────────────────┐                       │
│  │   Admin Backend      │    │   User Backend       │                       │
│  │   (NestJS :13000)    │    │   (FastAPI :8000)    │                       │
│  └──────────┬───────────┘    └──────────────────────┘                       │
└─────────────┼───────────────────────────────────────────────────────────────┘
              │
              │ Redis LPUSH (Celery 메시지 프로토콜)
              ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              Celery Workers (Batch)                          │
│  ┌──────────────────────┐    ┌──────────────────────┐                       │
│  │ celery-worker-backfill│    │ celery-worker-embed  │                       │
│  │   Queue: backfill     │    │   Queue: embed       │                       │
│  │   Concurrency: 2      │    │   Concurrency: 1     │                       │
│  └──────────────────────┘    └──────────────────────┘                       │
│  ┌──────────────────────┐    ┌──────────────────────┐                       │
│  │   celery-beat        │    │   flower :15555      │                       │
│  │   (스케줄러)          │    │   (모니터링 UI)       │                       │
│  └──────────────────────┘    └──────────────────────┘                       │
└─────────────────────────────────────────────────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              인프라 (Docker)                                  │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │  PostgreSQL │  │    Redis    │  │    MinIO    │  │  Weaviate   │         │
│  │   :15432    │  │   :16379    │  │ :19000/9001 │  │   :18080    │         │
│  │  메타데이터  │  │ Celery Broker│  │  S3 Storage │  │  Vector DB  │         │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘         │
└─────────────────────────────────────────────────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              외부 서비스                                      │
│  ┌─────────────────────────┐    ┌─────────────────────────┐                 │
│  │     Europe PMC API      │    │      OpenAI API         │                 │
│  │   (논문 검색 + 전문)     │    │   (text-embedding-3)    │                 │
│  └─────────────────────────┘    └─────────────────────────┘                 │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Admin ↔ Batch 통신 구조

### 통신 방식: Redis를 통한 Celery 메시지 프로토콜

Admin Backend는 Celery Worker와 직접 통신하지 않고, Redis 큐에 Celery 메시지 형식으로 태스크를 전송합니다.

```
┌────────────────┐         ┌────────────────┐         ┌────────────────┐
│ Admin Backend  │  LPUSH  │     Redis      │  BRPOP  │ Celery Worker  │
│   (NestJS)     │ ──────▶ │   Queue: X     │ ◀────── │   (Python)     │
└────────────────┘         └────────────────┘         └────────────────┘
```

### Celery 메시지 형식 (Admin에서 생성)

```typescript
// collection-jobs.service.ts
const message = JSON.stringify({
  body: Buffer.from(JSON.stringify([[queryId], {}, {}])).toString('base64'),
  'content-encoding': 'utf-8',
  'content-type': 'application/json',
  headers: {
    task: 'src.tasks.backfill.run_backfill',  // Python 태스크 경로
    id: taskId,
    lang: 'py',
    root_id: taskId,
    parent_id: null,
    group: null,
  },
  properties: {
    correlation_id: taskId,
    delivery_info: { exchange: '', routing_key: 'backfill' },  // 큐 이름
    priority: 0,
    body_encoding: 'base64',
  },
});

await this.redis.lpush('backfill', message);  // Redis 큐로 전송
```

### 상태 공유: PostgreSQL

태스크 실행 상태는 PostgreSQL의 `collection_jobs` 테이블을 통해 공유됩니다.

```
┌────────────────┐                              ┌────────────────┐
│ Admin Backend  │ ◀───── SELECT/UPDATE ──────▶ │ Celery Worker  │
│                │                              │                │
│  상태 조회/표시  │         PostgreSQL          │  상태 업데이트   │
└────────────────┘      collection_jobs         └────────────────┘
```

---

## 데이터베이스 스키마 (주요 테이블)

### 관계도

```
search_queries                 collection_jobs              papers
┌─────────────────┐           ┌─────────────────┐          ┌─────────────────┐
│ id (PK)         │◀──────────│ query_id (FK)   │          │ id (PK)         │
│ name            │     1:N   │ id (PK)         │          │ paper_id        │
│ query           │           │ job_type        │          │ pmcid           │
│ is_active       │           │ status          │          │ title           │
│ max_results     │           │ total_count     │          │ embedding_status│
│ year_from/to    │           │ success_count   │          │ embedding_at    │
│ max_concurrent  │           │ checkpoint      │          └────────┬────────┘
│ total_collected │           └────────┬────────┘                   │
└─────────────────┘                    │ 1:N                        │ 1:N
                                       ▼                            ▼
                              ┌─────────────────┐          ┌─────────────────┐
                              │  article_jobs   │          │  paper_sections │
                              │ batch_job_id(FK)│          │  paper_id (FK)  │
                              │ pmcid           │          │  section_name   │
                              │ status          │          │  offset_start   │
                              └─────────────────┘          └─────────────────┘
                                                                    │
                                                                    │
                                                           ┌────────▼────────┐
                                                           │  paper_authors  │
                                                           │  paper_id (FK)  │
                                                           │  author_name    │
                                                           └─────────────────┘
```

### 주요 테이블

| 테이블 | 설명 |
|--------|------|
| `search_queries` | 검색 쿼리 정의 (예: "cancer AND therapy") |
| `collection_jobs` | 수집 작업 (Backfill Job) 상태 관리 |
| `article_jobs` | 개별 논문 수집 상태 (체크포인트용) |
| `papers` | 수집된 논문 메타데이터 + 임베딩 상태 |
| `paper_sections` | 논문 섹션 정보 (offset 추적) |
| `paper_authors` | 논문 저자 정보 |
| `article_errors` | 수집 중 발생한 에러 로그 |

### 상태 정의

**JobStatus (collection_jobs)**
```
pending → running → completed
                  → failed
                  → partial (일부만 성공)
                  → cancelled
                  → retried
```

**EmbeddingStatus (papers)**
```
NULL (미시작) → pending → processing → completed
                                     → failed
```

---

## Celery 태스크 목록

### Queue: `backfill`

| 태스크 | 설명 | 트리거 |
|--------|------|--------|
| `run_backfill(query_id)` | 검색 쿼리 기반 논문 수집 | Admin UI: "수집 시작" 버튼 |
| `run_backfill_resume(query_id, job_id)` | 실패/partial 작업 재개 | Admin UI: "재개" 버튼 |

### Queue: `embed`

| 태스크 | 설명 | 트리거 |
|--------|------|--------|
| `run_embed(query_id, limit)` | 논문 청킹 + 임베딩 | Admin UI 또는 Beat 스케줄 |
| `run_embed_paper(paper_id)` | 단일 논문 임베딩 | Admin UI: 개별 논문 "임베딩" 버튼 |
| `run_reembed(query_id, limit)` | 실패한 논문 재임베딩 | Admin UI 또는 Beat 스케줄 |

### Celery Beat 스케줄

```python
beat_schedule = {
    # 매시간 새 논문 임베딩 (최대 50개)
    "embed-hourly": {
        "task": "src.tasks.embed.run_embed",
        "schedule": crontab(minute=0),
        "args": [None, 50],
    },
    # 매일 새벽 3시 실패한 논문 재임베딩
    "reembed-daily": {
        "task": "src.tasks.embed.run_reembed",
        "schedule": crontab(hour=3, minute=0),
        "args": [None, None],
    },
}
```

---

## Admin API 엔드포인트

### Collection Jobs (수집 작업)

| Method | Endpoint | 설명 |
|--------|----------|------|
| GET | `/collection-jobs` | 작업 목록 조회 |
| GET | `/collection-jobs/:id` | 작업 상세 조회 |
| POST | `/collection-jobs/trigger/:queryId` | 수집 시작 |
| POST | `/collection-jobs/:id/cancel` | 작업 취소 |
| POST | `/collection-jobs/:id/retry` | 작업 재시도 |
| POST | `/collection-jobs/:id/resume` | 작업 재개 |

### Papers (논문)

| Method | Endpoint | 설명 |
|--------|----------|------|
| GET | `/papers` | 논문 목록 (필터/검색) |
| GET | `/papers/stats` | 수집/임베딩 통계 |
| GET | `/papers/:id` | 논문 상세 |
| GET | `/papers/:id/fulltext` | 원문 조회 (S3) |
| POST | `/papers/embed/all` | 전체 임베딩 시작 |
| POST | `/papers/embed/:paperId` | 단일 논문 임베딩 |
| POST | `/papers/reembed` | 실패 논문 재임베딩 |

### Search Queries (검색 쿼리)

| Method | Endpoint | 설명 |
|--------|----------|------|
| GET | `/search-queries` | 쿼리 목록 |
| POST | `/search-queries` | 쿼리 생성 |
| PUT | `/search-queries/:id` | 쿼리 수정 |
| DELETE | `/search-queries/:id` | 쿼리 삭제 |

---

## 데이터 흐름

### 1. 논문 수집 (Backfill)

```
1. Admin UI에서 "수집 시작" 클릭
   └─▶ POST /collection-jobs/trigger/:queryId

2. Admin Backend
   └─▶ Redis LPUSH (Celery 메시지)
   └─▶ Queue: backfill

3. celery-worker-backfill
   ├─▶ Phase 1: Europe PMC 검색 → article_jobs에 등록
   └─▶ Phase 2: 개별 논문 다운로드/파싱/저장
       ├─▶ XML 다운로드 (Europe PMC)
       ├─▶ 파싱 (섹션 추출)
       ├─▶ S3 저장 (raw.xml, fulltext.txt)
       └─▶ PostgreSQL 저장 (papers, paper_sections, paper_authors)

4. 진행률 업데이트
   └─▶ collection_jobs.processed_count, success_count 업데이트
```

### 2. 임베딩

```
1. 트리거 (2가지 방식)
   ├─▶ Admin UI "임베딩 시작" → Redis LPUSH
   └─▶ Celery Beat (매시 정각) → run_embed

2. celery-worker-embed
   ├─▶ papers 조회 (embedding_status IS NULL)
   ├─▶ S3에서 fulltext.txt 읽기
   ├─▶ OAR-29 TextChunker로 청킹
   ├─▶ OpenAI API로 임베딩 생성
   └─▶ Weaviate에 청크 저장

3. 상태 업데이트
   └─▶ papers.embedding_status = 'completed'
   └─▶ papers.embedding_chunk_count = N
```

---

## 포트 매핑 (로컬 개발용)

모든 인프라 포트는 10000번대로 설정하여 충돌 방지.

| 서비스 | 내부 포트 | 외부 포트 | 설명 |
|--------|-----------|-----------|------|
| PostgreSQL | 5432 | **15432** | 메타데이터 DB |
| Redis | 6379 | **16379** | Celery Broker |
| MinIO API | 9000 | **19000** | S3 호환 스토리지 |
| MinIO Console | 9001 | **19001** | MinIO 웹 UI |
| Weaviate | 8080 | **18080** | 벡터 DB |
| Weaviate gRPC | 50051 | 50051 | gRPC (변경 없음) |
| Flower | 5555 | **15555** | Celery 모니터링 |
| Admin Backend | 3000 | **13000** | NestJS API |
| Admin Frontend | 3000 | **13001** | Next.js UI |

---

## 현재 상태 및 TODO

### 구현 완료

- [x] 논문 수집 (Backfill) - Admin에서 직접 제어
- [x] 임베딩 파이프라인 - Celery Beat 자동 스케줄링
- [x] Admin Dashboard - 수집/임베딩 현황 조회
- [x] 개별 논문 임베딩 트리거
- [x] 실패 논문 재임베딩

### TODO

- [ ] Admin에서 Celery Beat 스케줄 모니터링/제어
  - 현재 스케줄 확인
  - 스케줄 일시정지/재개
  - 수동 트리거
- [ ] 임베딩 Job 상태 테이블 (embedding_jobs)
  - 현재는 papers.embedding_status로만 관리
  - 별도 Job 테이블로 이력 관리 필요
- [ ] User Frontend RAG 검색 통합

---

## 참고: OAR 스파이크 의존성

이 시스템은 다른 스파이크의 코드를 동적으로 임포트합니다:

| 스파이크 | 사용 위치 | 기능 |
|----------|-----------|------|
| OAR-29 | `batch/src/tasks/embed.py` | TextChunker (섹션 기반 청킹) |
| OAR-31 | `batch/src/tasks/embed.py` | EmbeddingClient, WeaviateClient |

```python
# embed.py에서 동적 임포트
OAR_29_PATH = SPIKES_ROOT / "OAR-29" / "yts"
OAR_31_PATH = SPIKES_ROOT / "OAR-31" / "yts"
```
