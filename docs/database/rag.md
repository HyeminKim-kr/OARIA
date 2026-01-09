# RAG 테이블

> **Last Updated**: 2026-01-08

---

## 개요

RAG(Retrieval-Augmented Generation) 파이프라인의 전략 설정을 저장하는 테이블.
Admin에서 설정하고, User Backend가 서버 시작 시 로드하여 사용.

---

## rag_settings 테이블

### 컬럼 정의

| 컬럼명 | 타입 | NULL | 기본값 | 설명 |
|--------|------|------|--------|------|
| `id` | UUID | NO | gen_random_uuid() | PK |
| `name` | VARCHAR(50) | NO | - | 설정 이름 (unique) |
| `description` | TEXT | YES | NULL | 설정 설명 |
| `chunker` | VARCHAR(50) | NO | 'semantic' | 청킹 전략 |
| `embedder` | VARCHAR(50) | NO | 'openai' | 임베딩 모델 |
| `retriever` | VARCHAR(50) | NO | 'hybrid' | 검색 전략 |
| `reranker` | VARCHAR(50) | YES | NULL | 리랭킹 모델 (NULL=미사용) |
| `parameters` | JSONB | YES | NULL | 추가 파라미터 |
| `is_active` | BOOLEAN | NO | false | 활성 설정 여부 |
| `created_at` | TIMESTAMP | NO | CURRENT_TIMESTAMP | 생성일시 |
| `updated_at` | TIMESTAMP | NO | CURRENT_TIMESTAMP | 수정일시 |

### 제약 조건

- `name`은 UNIQUE
- `is_active=true`인 레코드는 1개만 존재해야 함 (트리거 또는 애플리케이션 레벨에서 관리)

### parameters JSONB 구조

```json
{
  "limit": 10,
  "alpha": 0.7,
  "min_rerank_score": 0.3,
  "temperature": 0.7
}
```

### DDL

```sql
CREATE TABLE rag_settings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(50) NOT NULL UNIQUE,
    description TEXT,
    chunker VARCHAR(50) NOT NULL DEFAULT 'semantic',
    embedder VARCHAR(50) NOT NULL DEFAULT 'openai',
    retriever VARCHAR(50) NOT NULL DEFAULT 'hybrid',
    reranker VARCHAR(50),
    parameters JSONB,
    is_active BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 기본 설정 삽입
INSERT INTO rag_settings (name, description, is_active, parameters)
VALUES (
    'default',
    '기본 RAG 설정',
    true,
    '{"limit": 10, "alpha": 0.7}'::jsonb
);

-- 인덱스
CREATE INDEX idx_rag_settings_is_active ON rag_settings(is_active) WHERE is_active = true;
```

---

## 사용 흐름

```
1. Admin UI에서 설정 수정
   └─► Admin Backend API 호출
   └─► rag_settings 테이블 업데이트

2. User Backend 서버 시작/재시작
   └─► is_active=true인 설정 조회
   └─► RAG 전략 객체 초기화
   └─► 메모리에 캐시

3. RAG 요청 처리
   └─► 메모리의 설정 사용 (DB 조회 없음)
```

---

## 예시 데이터

| name | chunker | embedder | retriever | reranker | is_active |
|------|---------|----------|-----------|----------|-----------|
| default | semantic | openai | hybrid | bge | true |
| high-precision | semantic | openai | hybrid | cohere | false |
| fast | fixed_size | openai | dense | NULL | false |

---

## 관련 코드

- **Admin Backend Entity**: `admin/backend/src/entities/rag-settings.entity.ts`
- **Admin Backend Module**: `admin/backend/src/modules/rag-settings/`
- **User Backend Config**: `backend/app/core/rag_config.py`
- **RAG Registry**: `backend/app/rag/registry.py`

---

## rag_strategies 테이블

> 사용 가능한 RAG 전략 정보를 저장. 서버 시작 시 코드에서 DB로 자동 동기화됨.

### 컬럼 정의

| 컬럼명 | 타입 | NULL | 기본값 | 설명 |
|--------|------|------|--------|------|
| `id` | UUID | NO | gen_random_uuid() | PK |
| `category` | VARCHAR(50) | NO | - | 전략 카테고리 (chunker, embedder, retriever, reranker) |
| `name` | VARCHAR(100) | NO | - | 전략 이름 (예: semantic_section_700t) |
| `description` | TEXT | YES | NULL | 전략 설명 (docstring에서 추출) |
| `config` | JSONB | YES | '{}' | 기본 설정값 |
| `location` | VARCHAR(20) | NO | - | 실행 위치 ('backend' 또는 'batch') |
| `is_active` | BOOLEAN | NO | true | 활성 여부 (false면 UI에서 선택 불가) |
| `created_at` | TIMESTAMPTZ | NO | NOW() | 생성일시 |
| `updated_at` | TIMESTAMPTZ | NO | NOW() | 수정일시 |

### 제약 조건

- `(category, name)` UNIQUE - 같은 카테고리 내 이름 중복 불가

### DDL

```sql
CREATE TABLE rag_strategies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    category VARCHAR(50) NOT NULL,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    config JSONB DEFAULT '{}',
    location VARCHAR(20) NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_rag_strategies_category_name UNIQUE(category, name)
);

-- 인덱스
CREATE INDEX idx_rag_strategies_category ON rag_strategies(category);
CREATE INDEX idx_rag_strategies_active ON rag_strategies(is_active) WHERE is_active = true;

-- updated_at 자동 갱신 트리거
CREATE OR REPLACE FUNCTION update_rag_strategies_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_rag_strategies_updated_at
    BEFORE UPDATE ON rag_strategies
    FOR EACH ROW
    EXECUTE FUNCTION update_rag_strategies_updated_at();
```

---

## rag_strategies vs rag_settings

| 테이블 | 역할 | 예시 |
|--------|------|------|
| `rag_strategies` | 사용 가능한 전략 목록 | "semantic_section_700t란 이런 청커다" |
| `rag_settings` | 파이프라인 설정 | "default 파이프라인은 semantic 청커를 사용한다" |

### 관계
```
rag_settings.chunker  → rag_strategies.name (WHERE category='chunker')
rag_settings.embedder → rag_strategies.name (WHERE category='embedder')
rag_settings.retriever → rag_strategies.name (WHERE category='retriever')
rag_settings.reranker → rag_strategies.name (WHERE category='reranker')
```

---

## 동기화 흐름

```
1. 코드에 전략 정의
   ├── Backend: @register_retriever, @register_reranker
   └── Batch: BATCH_STRATEGIES 정적 정의

2. 서버 시작 (User Backend)
   └── lifespan 이벤트
       └── sync_rag_strategies() 호출
           ├── 코드의 전략 목록 수집
           ├── DB에 UPSERT (있으면 update, 없으면 insert)
           └── 코드에 없는 전략 → is_active=false

3. Admin에서 전략 조회
   └── GET /lab/strategies
       └── rag_strategies 테이블에서 조회

4. 전략 변경 시
   └── 코드 수정 → 서버 재시작 → 자동 동기화
```

---

## 예시 데이터

| category | name | location | is_active |
|----------|------|----------|-----------|
| chunker | fixed_char_1000_200 | batch | true |
| chunker | semantic_section_700t | batch | true |
| embedder | openai_3small | batch | true |
| embedder | openai_3large | batch | true |
| retriever | hybrid_bm25_vector | backend | true |
| reranker | bge_reranker_v2_m3 | backend | true |
| reranker | none | backend | true |

---

## 관련 코드 (rag_strategies)

- **User Backend Sync**: `backend/app/core/rag_sync.py`
- **Batch 전략 정의**: `backend/app/rag/batch_strategies.py`
- **Backend 전략 Registry**: `backend/app/rag/registry.py`
