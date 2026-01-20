# 임베딩 시스템 (Embedding Systems)

> **Last Updated**: 2026-01-09
> **Schema Owner**: backend (FastAPI/SQLAlchemy), batch (Celery)

---

## 개요

OARIA는 두 개의 독립적인 임베딩 시스템을 운영합니다:

| 시스템 | 테이블 | 용도 | Weaviate 컬렉션 |
|--------|--------|------|-----------------|
| **운영용** | `papers.embedding_status` | 개별 논문 임베딩 (프로덕션) | `PaperChunks` |
| **Lab용** | `sample_embeddings` | 파이프라인 테스트/비교 | `MedicalChunks_sample_*` |

---

## 1. 운영용 임베딩 (papers.embedding_status)

### 목적
- 수집된 모든 논문을 Weaviate에 임베딩
- RAG 검색의 실제 데이터 소스

### 상태 전이

```
NULL (수집됨)
    │
    ▼
pending ──► processing ──► completed
    │           │
    └───────────┴──► failed
```

### 관련 컬럼 (papers 테이블)

| 컬럼 | 타입 | 설명 |
|------|------|------|
| `embedding_status` | VARCHAR(20) | 상태 (NULL, pending, processing, completed, failed) |
| `embedding_chunk_count` | INTEGER | 생성된 청크 수 |
| `embedding_error` | TEXT | 에러 메시지 |
| `embedding_at` | TIMESTAMPTZ | 완료 시각 |

### 상태값

| 값 | 설명 |
|----|------|
| `NULL` | 아직 임베딩 작업이 시작되지 않음 (신규 수집) |
| `pending` | 임베딩 대기 중 |
| `processing` | 임베딩 처리 중 |
| `completed` | 임베딩 완료 |
| `failed` | 임베딩 실패 |

### 처리 흐름

```
1. Admin에서 "임베딩 시작" 클릭
   └─► POST /papers/embedding/batch-retry

2. Backend에서 Job 생성
   └─► Redis에 작업 등록 (JobType.PAPER_EMBED)

3. Job Dispatcher가 폴링
   └─► run_paper_embed_v2.delay() 호출

4. Celery Worker가 처리
   ├─► embedding_status = 'processing'
   ├─► S3에서 fulltext 로드
   ├─► 청킹 + 임베딩
   ├─► Weaviate PaperChunks에 저장
   └─► embedding_status = 'completed' (또는 'failed')
```

---

## 2. Lab용 임베딩 (sample_embeddings)

### 목적
- 다양한 청킹/임베딩 전략 테스트
- A/B 비교를 위한 샘플 임베딩
- RAG Lab에서 파이프라인 성능 비교

### 테이블 스키마

```sql
CREATE TABLE sample_embeddings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    query_id UUID NOT NULL REFERENCES search_queries(id) ON DELETE CASCADE,
    chunker VARCHAR(100) NOT NULL,
    embedder VARCHAR(100) NOT NULL,
    pipeline_key VARCHAR(200) NOT NULL,
    collection_name VARCHAR(200) NOT NULL,
    status VARCHAR(20) DEFAULT 'pending',
    paper_count INTEGER DEFAULT 0,
    chunk_count INTEGER DEFAULT 0,
    error_message TEXT,
    retry_count INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,

    UNIQUE(query_id, pipeline_key)
);

CREATE INDEX idx_sample_embeddings_query_id ON sample_embeddings(query_id);
CREATE INDEX idx_sample_embeddings_status ON sample_embeddings(status);
```

### 컬럼 설명

| 컬럼 | 타입 | 설명 |
|------|------|------|
| `id` | UUID | PK |
| `query_id` | UUID | FK → search_queries.id (샘플 쿼리) |
| `chunker` | VARCHAR(100) | 청킹 전략 (예: semantic_section_700t) |
| `embedder` | VARCHAR(100) | 임베딩 모델 (예: openai_3small) |
| `pipeline_key` | VARCHAR(200) | chunker__embedder 조합 키 |
| `collection_name` | VARCHAR(200) | Weaviate 컬렉션명 |
| `status` | VARCHAR(20) | 상태 |
| `paper_count` | INTEGER | 처리된 논문 수 |
| `chunk_count` | INTEGER | 생성된 청크 수 |
| `error_message` | TEXT | 에러 메시지 |
| `retry_count` | INTEGER | 재시도 횟수 |
| `created_at` | TIMESTAMPTZ | 생성 시각 |
| `started_at` | TIMESTAMPTZ | 시작 시각 |
| `completed_at` | TIMESTAMPTZ | 완료 시각 |

### 상태 전이

```
pending ──► processing ──► completed
    │           │
    ▼           ▼
 queued      failed
    │           │
    └───────────┴──► (retry) ──► queued
```

### Weaviate 컬렉션 네이밍

```
MedicalChunks_sample_{chunker}_{embedder}

예시:
- MedicalChunks_sample_semantic_section_700t_openai_3small
- MedicalChunks_sample_fixed_char_1000_200_openai_3large
```

---

## 3. 두 시스템의 관계

### 독립성
- 두 시스템은 **완전히 독립적**으로 동작
- sample_embeddings 처리가 papers.embedding_status에 영향 없음
- 각각 별도의 Weaviate 컬렉션 사용

### 데이터 흐름

```
SearchQuery (query_type='sample')
    │
    ├──► BatchJob ──► Papers (수집)
    │                    │
    │                    └──► papers.embedding_status (운영용)
    │                              └──► PaperChunks 컬렉션
    │
    └──► SampleEmbedding (테스트용)
              │
              └──► 선택된 Papers의 복사본
                        └──► MedicalChunks_sample_* 컬렉션
```

### 비교

| 항목 | papers.embedding_status | sample_embeddings |
|------|------------------------|-------------------|
| 범위 | 모든 수집된 논문 | 특정 쿼리로 수집된 논문만 |
| 청킹 전략 | 고정 (semantic_section_700t) | 선택 가능 |
| 임베딩 모델 | 고정 (openai_3small) | 선택 가능 |
| 재시도 | Job Manager V2 | Job Manager V2 |
| 용도 | RAG 프로덕션 | 파이프라인 테스트 |

---

## 4. Job Manager 연동

### JobType 정의

```python
class JobType:
    EMBED = "embed"           # sample_embeddings용
    PAPER_EMBED = "paper"     # papers.embedding_status용
```

### Redis 키 구조

```
# sample_embeddings
job:embed:{embedding_id}:state
job:embed:{embedding_id}:lock
queue:embed:pending

# papers.embedding_status (일괄 배치)
job:paper:{batch_id}:state
job:paper:{batch_id}:lock
queue:paper:pending
```

### Beat 스케줄

| 태스크 | 주기 | 설명 |
|--------|------|------|
| `dispatch_pending_jobs` | 10초 | sample_embeddings 디스패치 |
| `recover_stuck_jobs` | 1분 | sample_embeddings 복구 |
| `sync_jobs_from_db` | 5분 | sample_embeddings DB 동기화 |
| `dispatch_paper_jobs` | 10초 | papers 임베딩 디스패치 |
| `recover_stuck_paper_jobs` | 1분 | papers 임베딩 복구 |
| `sync_papers_from_db` | 5분 | papers DB 동기화 |

---

## 5. 관련 파일

### Backend (FastAPI)
- `backend/app/models/paper.py` - Paper 모델 (embedding_status 컬럼)
- `backend/app/models/batch.py` - SampleEmbedding 모델
- `backend/app/routers/papers.py` - Papers 임베딩 API
- `backend/app/routers/lab.py` - Sample 임베딩 API

### Batch (Celery)
- `batch/src/job_manager.py` - Job 상태 관리
- `batch/src/tasks/embed.py` - 운영용 임베딩 태스크
- `batch/src/tasks/sample_embed.py` - 샘플 임베딩 태스크
- `batch/src/tasks/job_dispatcher.py` - Job 디스패처

### Admin Backend (NestJS)
- `admin/backend/src/entities/paper.entity.ts` - Paper 엔티티
- `admin/backend/src/entities/sample-embedding.entity.ts` - SampleEmbedding 엔티티
- `admin/backend/src/modules/papers/` - Papers 모듈
- `admin/backend/src/modules/sample-embeddings/` - SampleEmbeddings 모듈
