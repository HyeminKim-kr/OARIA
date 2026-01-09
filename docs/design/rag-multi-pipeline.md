# RAG 멀티 파이프라인 설계

> **작성일**: 2026-01-08
> **상태**: Draft
> **관련**: Lab, 임베딩 관리, Weaviate

---

## 1. 개요

### 1.1 현재 상황

```
논문 수집 → 청킹(고정) → 임베딩(고정) → Weaviate(단일 컬렉션)
                │              │
          semantic 고정   OpenAI 고정
```

- 청킹/임베딩 전략이 **인덱싱 시점에 고정**
- Lab에서 Retriever/Reranker만 비교 가능
- 청킹/임베딩 전략 비교 시 **전체 재인덱싱 필요**

### 1.2 목표

- 청킹/임베딩 전략을 **Lab에서 비교 가능**하게 개선
- 프로덕션 안정성 유지
- 기존 Celery 파이프라인 최소 수정

---

## 2. 설계

### 2.1 핵심 아이디어

**프로덕션과 샘플 분리**

```
┌─────────────────────────────────────────────────────────────┐
│                    수집 쿼리 시스템                          │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  📦 프로덕션 쿼리 (query_type: production)                   │
│  ├── "EGFR lung cancer" → 1,200건                          │
│  └── 자동 임베딩 (Celery, 프로덕션 전략)                     │
│                                                             │
│  🧪 샘플 쿼리 (query_type: sample)                          │
│  ├── "sample: lung cancer 2024" → 100건                    │
│  └── 수동 임베딩 (Admin에서 전략 선택)                       │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 데이터 흐름

```
[프로덕션 흐름] - 기존과 동일
쿼리(production) → 수집(Celery) → 임베딩(Celery) → MedicalChunks_production

[샘플 흐름] - 신규
쿼리(sample) → 수집(Celery) → (대기)
                                ↓
              Admin에서 전략 선택 후 임베딩 실행
                                ↓
              ┌─ MedicalChunks_sample_semantic_openai
              ├─ MedicalChunks_sample_fixed_openai
              └─ MedicalChunks_sample_semantic_bge
```

---

## 3. DB 스키마

### 3.1 search_queries 테이블 수정

```sql
-- 쿼리 타입 추가
ALTER TABLE search_queries
ADD COLUMN query_type VARCHAR(20) DEFAULT 'production';

-- 타입: 'production' | 'sample'
```

### 3.2 sample_embeddings 테이블 (신규)

```sql
CREATE TABLE sample_embeddings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- 샘플 쿼리 참조
    query_id UUID NOT NULL REFERENCES search_queries(id) ON DELETE CASCADE,

    -- 파이프라인 정보
    chunker VARCHAR(100) NOT NULL,       -- "semantic_section_700t"
    embedder VARCHAR(100) NOT NULL,      -- "openai_3small_1536d"
    pipeline_key VARCHAR(200) NOT NULL,  -- "semantic_section_700t__openai_3small_1536d"
    collection_name VARCHAR(200) NOT NULL, -- "MedicalChunks_sample_{pipeline_key}"

    -- 상태
    status VARCHAR(20) NOT NULL DEFAULT 'pending', -- pending, processing, completed, failed
    paper_count INT DEFAULT 0,
    chunk_count INT DEFAULT 0,
    error_message TEXT,

    -- 타임스탬프
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,

    -- 유니크 제약
    UNIQUE(query_id, pipeline_key)
);

-- 인덱스
CREATE INDEX idx_sample_embeddings_query_id ON sample_embeddings(query_id);
CREATE INDEX idx_sample_embeddings_status ON sample_embeddings(status);
```

---

## 4. API 설계

### 4.1 샘플 쿼리 관리 (기존 API 확장)

```
GET    /search-queries?type=sample     # 샘플 쿼리 목록
POST   /search-queries                 # 쿼리 생성 (query_type 필드 추가)
```

### 4.2 샘플 임베딩 관리 (신규)

```
# 샘플 임베딩 목록
GET /sample-embeddings?query_id={id}
Response: {
  items: [
    {
      id: "uuid",
      queryId: "uuid",
      chunker: "semantic_section_700t",
      embedder: "openai_3small_1536d",
      pipelineKey: "semantic_section_700t__openai_3small_1536d",
      collectionName: "MedicalChunks_sample_semantic_openai",
      status: "completed",
      paperCount: 100,
      chunkCount: 2340,
      createdAt: "2026-01-08T10:00:00Z",
      completedAt: "2026-01-08T10:05:00Z"
    }
  ]
}

# 샘플 임베딩 생성 (비동기)
POST /sample-embeddings
Body: {
  queryId: "uuid",
  chunker: "semantic_section_700t",
  embedder: "openai_3small_1536d"
}
Response: {
  id: "uuid",
  taskId: "celery-task-id",
  status: "pending"
}

# 샘플 임베딩 삭제 (Weaviate 컬렉션도 삭제)
DELETE /sample-embeddings/{id}

# 샘플 임베딩 상태 조회
GET /sample-embeddings/{id}
```

### 4.3 Lab 검색 API 확장

```
# 기존
POST /lab/search
Body: {
  query: "EGFR mutation",
  retriever: "hybrid_alpha70",
  reranker: "bge_reranker_v2m3"
}

# 확장 - 샘플 데이터 소스 지정 가능
POST /lab/search
Body: {
  query: "EGFR mutation",

  # 데이터 소스 (선택)
  dataSource: {
    type: "sample",                    # "production" | "sample"
    sampleEmbeddingId: "uuid"          # sample인 경우 필수
  },

  retriever: "hybrid_alpha70",
  reranker: "bge_reranker_v2m3"
}
```

---

## 5. Weaviate 컬렉션 구조

### 5.1 컬렉션 네이밍

```
프로덕션:
  MedicalChunks_production

샘플:
  MedicalChunks_sample_{chunker}_{embedder}

예시:
  MedicalChunks_sample_semantic_section_700t__openai_3small_1536d
  MedicalChunks_sample_fixed_char_1000_200__openai_3small_1536d
```

### 5.2 컬렉션 스키마 (동일)

```python
{
    "class": "MedicalChunks_sample_xxx",
    "vectorizer": "none",  # 직접 벡터 제공
    "properties": [
        {"name": "content", "dataType": ["text"]},
        {"name": "paperId", "dataType": ["text"]},
        {"name": "title", "dataType": ["text"]},
        {"name": "section", "dataType": ["text"]},
        {"name": "chunkIndex", "dataType": ["int"]},
        {"name": "year", "dataType": ["int"]},
    ]
}
```

---

## 6. Celery 태스크

### 6.1 샘플 임베딩 태스크 (신규)

```python
# batch/app/tasks/sample_embedding_tasks.py

@celery.task(bind=True)
def create_sample_embedding(self, sample_embedding_id: str):
    """샘플 쿼리의 논문들을 지정된 전략으로 임베딩"""

    # 1. sample_embedding 정보 조회
    sample_emb = get_sample_embedding(sample_embedding_id)
    update_status(sample_embedding_id, "processing")

    # 2. 해당 쿼리의 논문들 조회
    papers = get_papers_by_query(sample_emb.query_id)

    # 3. Chunker, Embedder 인스턴스 생성
    chunker = get_chunker(sample_emb.chunker)
    embedder = get_embedder(sample_emb.embedder)

    # 4. Weaviate 컬렉션 생성 (없으면)
    ensure_collection(sample_emb.collection_name, embedder.dimension)

    # 5. 논문별 처리
    total_chunks = 0
    for paper in papers:
        # 청킹
        chunks = chunker.chunk(paper.fulltext)

        # 임베딩
        vectors = embedder.embed_batch([c.content for c in chunks])

        # Weaviate 저장
        weaviate_service.insert_chunks(
            collection_name=sample_emb.collection_name,
            chunks=chunks,
            vectors=vectors,
            paper=paper
        )
        total_chunks += len(chunks)

    # 6. 완료 처리
    update_status(
        sample_embedding_id,
        "completed",
        paper_count=len(papers),
        chunk_count=total_chunks
    )
```

### 6.2 기존 프로덕션 태스크 (수정 없음)

```python
# 기존 embed_paper 태스크는 그대로 유지
# query_type이 'production'인 쿼리의 논문만 처리
```

---

## 7. Admin UI

### 7.1 쿼리 관리 페이지 수정

```
┌─────────────────────────────────────────────────────────────┐
│  🔍 수집 쿼리 관리                                           │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  타입 필터: [전체 ▼] [프로덕션] [샘플]                        │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ 🏭 EGFR lung cancer                    production   │   │
│  │    수집: 1,200건 | 임베딩: 완료                      │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ 🧪 sample: lung cancer 2024              sample     │   │
│  │    수집: 100건 | 임베딩: 3개 전략                    │   │
│  │    [임베딩 관리]                                     │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  [+ 새 쿼리 추가]                                           │
└─────────────────────────────────────────────────────────────┘
```

### 7.2 임베딩 관리 페이지 (신규)

```
┌─────────────────────────────────────────────────────────────┐
│  📊 임베딩 관리                                              │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━   │
│  🏭 프로덕션 임베딩                                          │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━   │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ 컬렉션: MedicalChunks_production                    │   │
│  │ 전략: semantic_section_700t + openai_3small_1536d   │   │
│  │                                                     │   │
│  │ 📈 통계                                             │   │
│  │ ├── 논문: 45,230건                                  │   │
│  │ ├── 청크: 892,104개                                 │   │
│  │ └── 크기: 약 2.3GB                                  │   │
│  │                                                     │   │
│  │ 상태: 🟢 Active                                     │   │
│  │ 마지막 업데이트: 2026-01-08 10:30                   │   │
│  │                                                     │   │
│  │ [상세 보기] [전략 변경 (재인덱싱)]                   │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━   │
│  🧪 샘플 임베딩                                              │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━   │
│                                                             │
│  샘플 쿼리: [sample: lung cancer 2024 ▼]                   │
│  수집된 논문: 100건                                         │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ semantic_section_700t + openai_3small_1536d         │   │
│  │ 상태: ✅ 완료 | 청크: 2,340개                        │   │
│  │ [Lab에서 테스트] [삭제]                              │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ fixed_char_1000_200 + openai_3small_1536d           │   │
│  │ 상태: ✅ 완료 | 청크: 1,890개                        │   │
│  │ [Lab에서 테스트] [삭제]                              │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ semantic_section_700t + bge_m3_1024d                │   │
│  │ 상태: 🟡 진행중 (67%)                               │   │
│  │ [취소]                                              │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  [+ 새 전략으로 임베딩]                                     │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ 새 임베딩 생성                                      │   │
│  │                                                     │   │
│  │ Chunker:  [sliding_window_500_100 ▼]               │   │
│  │ Embedder: [openai_3small_1536d ▼]                  │   │
│  │                                                     │   │
│  │ [생성]                                              │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 7.3 Lab 페이지 수정

```
┌─────────────────────────────────────────────────────────────┐
│  🔬 RAG Lab                                                 │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  데이터 소스:                                                │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ [🔘 프로덕션 (45,230 논문)]                          │   │
│  │ [⚪ 샘플: lung cancer 2024 (100 논문)]              │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  ─────────────────────────────────────────────────────────  │
│  (샘플 선택 시)                                              │
│                                                             │
│  임베딩 전략:                                                │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ [▼ semantic + openai (2,340 청크)]                  │   │
│  │    fixed + openai (1,890 청크)                      │   │
│  │    semantic + bge (빌드중 67%)                      │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  Retriever: [hybrid_alpha70 ▼]                             │
│  Reranker:  [bge_reranker_v2m3 ▼]                          │
│                                                             │
│  ─────────────────────────────────────────────────────────  │
│                                                             │
│  [검색 테스트] [답변 생성 테스트] [A/B 비교]                 │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 8. 구현 순서

### Phase 1: 기반 작업
1. DB 스키마 설계 & 마이그레이션
   - search_queries.query_type 추가
   - sample_embeddings 테이블 생성
2. 엔티티/모델 추가
   - TypeORM: SampleEmbedding 엔티티
   - SQLAlchemy: SampleEmbedding 모델

### Phase 2: 백엔드 API
1. 샘플 임베딩 CRUD API
2. Weaviate 멀티 컬렉션 지원
3. Celery 샘플 임베딩 태스크

### Phase 3: Admin UI
1. 쿼리 관리 - 타입 필터 추가
2. 임베딩 관리 페이지 신규 개발
3. Lab - 데이터 소스 선택 기능

### Phase 4: 통합 & 테스트
1. E2E 테스트
2. 성능 테스트
3. 문서화

---

## 9. 고려사항

### 9.1 저장 공간
- 샘플 100건 × 전략 5개 = 500개 임베딩 세트
- 프로덕션 대비 미미한 수준

### 9.2 삭제 정책
- 샘플 임베딩 삭제 시 Weaviate 컬렉션도 함께 삭제
- 샘플 쿼리 삭제 시 관련 임베딩 모두 삭제 (CASCADE)

### 9.3 동시성
- 같은 샘플 쿼리에 대해 여러 임베딩 동시 생성 가능
- Celery 태스크로 백그라운드 처리

### 9.4 프로덕션 전환
- 샘플에서 검증된 전략을 프로덕션에 적용 시
- 프로덕션 전략 변경 → 전체 재인덱싱 필요
- 별도 기능으로 구현 (이 문서 범위 외)

---

## 10. 참고

### 관련 문서
- `backend/app/rag/README.md` - RAG 전략 네이밍 규칙
- `docs/database/papers.md` - papers 테이블 스키마

### 관련 코드
- `backend/app/services/weaviate_service.py`
- `batch/app/tasks/embedding_tasks.py`
- `admin/frontend/src/app/lab/`
