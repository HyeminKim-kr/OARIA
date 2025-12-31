# Batch 테이블 스키마

> **논문 수집 배치 작업 관련 테이블**
>
> **Last Updated**: 2026-01-01
>
> **Owner**: Backend (Alembic)

---

## 개요

Europe PMC에서 논문을 수집하는 배치 작업을 관리하는 테이블 그룹입니다.

> **마이그레이션**: 모든 테이블은 `backend/alembic`에서 관리됩니다.

### 명명 규칙

모든 배치 관련 테이블은 `batch_` 접두사를 사용합니다.

| 테이블 | 설명 |
|--------|------|
| `search_queries` | 검색 쿼리 정의 (무엇을 수집할지) |
| `batch_jobs` | 배치 작업 큐 (수집 작업 상태) |
| `batch_articles` | 개별 논문 수집 상태 |
| `batch_errors` | 아티클 에러 로그 |
| `batch_logs` | 배치 실행 로그 |
| `batch_failed_items` | 실패 항목 추적 |
| `watermarks` | 증분 수집 상태 |

---

## 테이블 관계도

```
┌──────────────────┐
│  search_queries  │
├──────────────────┤
│ id (PK)          │
│ name             │
│ query            │
│ is_active        │
└────────┬─────────┘
         │ 1:N
         ▼
┌──────────────────┐       ┌──────────────────┐
│    batch_jobs    │───────│   batch_logs     │
├──────────────────┤  1:N  ├──────────────────┤
│ id (PK)          │       │ job_id (FK)      │
│ query_id (FK)    │       │ level            │
│ job_type         │       │ message          │
│ status           │       └──────────────────┘
└────────┬─────────┘
         │ 1:N
    ┌────┴────┐
    ▼         ▼
┌──────────────────┐  ┌──────────────────┐
│  batch_articles  │  │   batch_errors   │
├──────────────────┤  ├──────────────────┤
│ job_id (FK)      │  │ job_id (FK)      │
│ pmcid            │  │ pmcid            │
│ status           │  │ error_code       │
└──────────────────┘  └──────────────────┘
```

---

## search_queries (검색 쿼리)

수집할 논문의 검색 조건을 정의합니다.

### 컬럼 정의

| 컬럼 | 타입 | Nullable | 기본값 | 설명 |
|------|------|----------|--------|------|
| **id** | `UUID` | NO | `gen_random_uuid()` | Primary Key |
| **name** | `VARCHAR(100)` | NO | - | 쿼리 이름 |
| **query** | `TEXT` | NO | - | Europe PMC 검색 쿼리 |
| description | `TEXT` | YES | - | 설명 |
| is_active | `BOOLEAN` | YES | `TRUE` | 활성화 여부 |
| priority | `INT` | YES | `10` | 우선순위 (낮을수록 우선) |
| max_results | `INT` | YES | - | 최대 결과 수 (NULL=무제한) |
| year_from | `INT` | YES | - | 시작 연도 |
| year_to | `INT` | YES | - | 종료 연도 |
| open_access_only | `BOOLEAN` | YES | `TRUE` | 오픈액세스만 |
| max_concurrent | `INT` | YES | `35` | 동시 API 요청 수 |
| auto_backfill | `BOOLEAN` | YES | `FALSE` | 자동 백필 실행 |
| total_collected | `INT` | YES | `0` | 수집된 총 논문 수 |
| last_backfill_at | `TIMESTAMPTZ` | YES | - | 마지막 백필 시각 |
| last_incremental_at | `TIMESTAMPTZ` | YES | - | 마지막 증분 수집 시각 |
| created_at | `TIMESTAMPTZ` | YES | `NOW()` | 생성 시각 |
| updated_at | `TIMESTAMPTZ` | YES | `NOW()` | 수정 시각 |
| created_by | `VARCHAR(100)` | YES | - | 생성자 |
| updated_by | `VARCHAR(100)` | YES | - | 수정자 |

### DDL

```sql
CREATE TABLE search_queries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) NOT NULL,
    query TEXT NOT NULL,
    description TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    priority INT DEFAULT 10,
    max_results INT,
    year_from INT,
    year_to INT,
    open_access_only BOOLEAN DEFAULT TRUE,
    max_concurrent INT DEFAULT 35,
    auto_backfill BOOLEAN DEFAULT FALSE,
    total_collected INT DEFAULT 0,
    last_backfill_at TIMESTAMPTZ,
    last_incremental_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    created_by VARCHAR(100),
    updated_by VARCHAR(100)
);

CREATE INDEX idx_search_queries_active ON search_queries(is_active, priority);
```

### 기본 데이터

```sql
INSERT INTO search_queries (name, query, description, priority) VALUES
    ('폐암 면역치료', 'lung cancer immunotherapy', '폐암 면역치료 관련 논문', 1),
    ('유방암 BRCA', 'breast cancer BRCA mutation', 'BRCA 변이 유방암 논문', 2),
    ('대장암 표적치료', 'colorectal cancer targeted therapy', '대장암 표적치료 논문', 3);
```

---

## batch_jobs (배치 작업 큐)

논문 수집 배치 작업의 상태를 관리합니다.

> **이전 이름**: `collection_jobs` → `batch_jobs`로 통일 (2026-01-01)

### 컬럼 정의

| 컬럼 | 타입 | Nullable | 기본값 | 설명 |
|------|------|----------|--------|------|
| **id** | `UUID` | NO | `gen_random_uuid()` | Primary Key |
| **job_type** | `VARCHAR(20)` | NO | - | 작업 유형 |
| query_id | `UUID` | YES | - | FK → search_queries.id |
| priority | `INT` | YES | `10` | 우선순위 |
| **query** | `TEXT` | NO | - | 실제 검색 쿼리 |
| params | `JSONB` | YES | - | 추가 파라미터 |
| api_name | `VARCHAR(50)` | YES | `'europe_pmc'` | API 이름 |
| status | `VARCHAR(20)` | YES | `'pending'` | 작업 상태 |
| checkpoint | `JSONB` | YES | - | 중단 재개용 체크포인트 |
| total_count | `INT` | YES | - | 전체 건수 |
| processed_count | `INT` | YES | `0` | 처리 건수 |
| success_count | `INT` | YES | `0` | 성공 건수 |
| failed_count | `INT` | YES | `0` | 실패 건수 |
| attempt_count | `INT` | YES | `0` | 시도 횟수 |
| max_attempts | `INT` | YES | `5` | 최대 시도 횟수 |
| next_run_at | `TIMESTAMPTZ` | YES | - | 다음 실행 시각 |
| locked_at | `TIMESTAMPTZ` | YES | - | 락 시각 |
| locked_by | `VARCHAR(100)` | YES | - | 락 워커 ID |
| last_error_code | `VARCHAR(20)` | YES | - | 마지막 에러 코드 |
| last_error_message | `TEXT` | YES | - | 마지막 에러 메시지 |
| last_error_at | `TIMESTAMPTZ` | YES | - | 마지막 에러 시각 |
| created_at | `TIMESTAMPTZ` | YES | `NOW()` | 생성 시각 |
| updated_at | `TIMESTAMPTZ` | YES | `NOW()` | 수정 시각 |
| started_at | `TIMESTAMPTZ` | YES | - | 시작 시각 |
| completed_at | `TIMESTAMPTZ` | YES | - | 완료 시각 |
| duration_ms | `INT` | YES | - | 소요 시간 (ms) |

### 상태 값

#### job_type

| 값 | 설명 |
|----|------|
| `backfill` | 전체 수집 (히스토리) |
| `incremental` | 증분 수집 |
| `repair` | 복구 작업 |

#### status

| 값 | 설명 |
|----|------|
| `pending` | 대기 중 |
| `running` | 실행 중 |
| `completed` | 완료 |
| `failed` | 실패 |
| `delayed` | 지연됨 (재시도 대기) |
| `cancelled` | 취소됨 |

### 인덱스

```sql
CREATE INDEX idx_batch_jobs_pending ON batch_jobs (priority, created_at)
    WHERE status IN ('pending', 'delayed');
CREATE INDEX idx_batch_jobs_delayed ON batch_jobs (next_run_at)
    WHERE status = 'delayed';
CREATE INDEX idx_batch_jobs_stale_lock ON batch_jobs (locked_at)
    WHERE status = 'running';
CREATE INDEX idx_batch_jobs_type ON batch_jobs (job_type, status);
CREATE INDEX idx_batch_jobs_query ON batch_jobs (query_id, created_at);
```

---

## batch_articles (개별 논문 상태)

배치 작업 내 개별 논문의 수집 상태를 추적합니다.

> **이전 이름**: `article_jobs` → `batch_articles`로 통일 (2026-01-01)

### 컬럼 정의

| 컬럼 | 타입 | Nullable | 기본값 | 설명 |
|------|------|----------|--------|------|
| **id** | `UUID` | NO | `gen_random_uuid()` | Primary Key |
| **job_id** | `UUID` | NO | - | FK → batch_jobs.id |
| **pmcid** | `VARCHAR(20)` | NO | - | PubMed Central ID |
| pmid | `VARCHAR(20)` | YES | - | PubMed ID |
| doi | `VARCHAR(100)` | YES | - | DOI |
| metadata | `JSONB` | YES | - | 검색 메타데이터 (pub_types 등) |
| status | `VARCHAR(20)` | YES | `'pending'` | 상태 |
| attempt_count | `INT` | YES | `0` | 시도 횟수 |
| max_attempts | `INT` | YES | `3` | 최대 시도 횟수 |
| next_run_at | `TIMESTAMPTZ` | YES | - | 다음 실행 시각 |
| last_error_code | `VARCHAR(20)` | YES | - | 에러 코드 |
| last_error | `TEXT` | YES | - | 에러 메시지 |
| created_at | `TIMESTAMPTZ` | YES | `NOW()` | 생성 시각 |
| updated_at | `TIMESTAMPTZ` | YES | `NOW()` | 수정 시각 |

### 상태 값

| 값 | 설명 |
|----|------|
| `pending` | 대기 중 |
| `downloading` | XML 다운로드 중 |
| `parsing` | 파싱 중 |
| `saving` | 저장 중 |
| `completed` | 완료 |
| `failed` | 실패 |

### 제약 조건

```sql
UNIQUE(job_id, pmcid)  -- 같은 작업 내 논문 중복 방지
```

---

## batch_errors (에러 로그)

개별 논문 수집 중 발생한 에러를 기록합니다.

> **이전 이름**: `article_errors` → `batch_errors`로 통일 (2026-01-01)

### 컬럼 정의

| 컬럼 | 타입 | Nullable | 기본값 | 설명 |
|------|------|----------|--------|------|
| **id** | `UUID` | NO | `gen_random_uuid()` | Primary Key |
| job_id | `UUID` | YES | - | FK → batch_jobs.id |
| pmcid | `VARCHAR(20)` | YES | - | PMC ID |
| pmid | `VARCHAR(20)` | YES | - | PubMed ID |
| doi | `VARCHAR(100)` | YES | - | DOI |
| **stage** | `VARCHAR(30)` | NO | - | 에러 단계 |
| error_code | `VARCHAR(50)` | YES | - | 에러 코드 |
| **error_message** | `TEXT` | NO | - | 에러 메시지 |
| error_detail | `TEXT` | YES | - | 상세 정보 (stacktrace) |
| raw_response | `TEXT` | YES | - | 원본 응답 (디버깅용) |
| context | `JSONB` | YES | - | 추가 컨텍스트 |
| created_at | `TIMESTAMPTZ` | YES | `NOW()` | 생성 시각 |

### 에러 단계 (stage)

| 값 | 설명 |
|----|------|
| `search` | 검색 API 호출 |
| `download` | XML 다운로드 |
| `parse` | XML 파싱 |
| `save` | DB 저장 |

### 에러 코드 예시

| 코드 | 설명 |
|------|------|
| `HTTP_429` | Rate limit 초과 |
| `HTTP_500` | 서버 에러 |
| `TIMEOUT` | 타임아웃 |
| `PARSE_XML` | XML 파싱 실패 |
| `DB_INSERT` | DB 저장 실패 |

---

## batch_logs (실행 로그)

배치 작업 실행 중 로그를 기록합니다.

> **이전 이름**: `batch_job_logs` → `batch_logs`로 간소화 (2026-01-01)

### 컬럼 정의

| 컬럼 | 타입 | Nullable | 기본값 | 설명 |
|------|------|----------|--------|------|
| **id** | `UUID` | NO | `gen_random_uuid()` | Primary Key |
| job_id | `UUID` | YES | - | FK → batch_jobs.id |
| **level** | `VARCHAR(10)` | NO | - | 로그 레벨 |
| **message** | `TEXT` | NO | - | 로그 메시지 |
| details | `JSONB` | YES | - | 추가 정보 |
| created_at | `TIMESTAMPTZ` | YES | `NOW()` | 생성 시각 |

### 로그 레벨

| 값 | 설명 |
|----|------|
| `info` | 정보 |
| `warn` | 경고 |
| `error` | 에러 |

---

## batch_failed_items (실패 항목)

실패한 항목을 추적하고 재시도를 관리합니다.

### 컬럼 정의

| 컬럼 | 타입 | Nullable | 기본값 | 설명 |
|------|------|----------|--------|------|
| **id** | `UUID` | NO | `gen_random_uuid()` | Primary Key |
| job_id | `UUID` | YES | - | FK → batch_jobs.id |
| **item_type** | `VARCHAR(20)` | NO | - | 항목 유형 |
| item_id | `VARCHAR(100)` | YES | - | 항목 ID |
| error_code | `VARCHAR(20)` | YES | - | 에러 코드 |
| error_message | `TEXT` | YES | - | 에러 메시지 |
| retry_count | `INT` | YES | `0` | 재시도 횟수 |
| max_retries | `INT` | YES | `3` | 최대 재시도 |
| next_retry_at | `TIMESTAMPTZ` | YES | - | 다음 재시도 시각 |
| status | `VARCHAR(20)` | YES | `'pending'` | 상태 |
| resolved_at | `TIMESTAMPTZ` | YES | - | 해결 시각 |
| created_at | `TIMESTAMPTZ` | YES | `NOW()` | 생성 시각 |

---

## watermarks (증분 수집 상태)

증분 수집의 마지막 실행 시점을 추적합니다.

### 컬럼 정의

| 컬럼 | 타입 | Nullable | 기본값 | 설명 |
|------|------|----------|--------|------|
| **id** | `VARCHAR(100)` | NO | - | Primary Key (예: `incremental:europe_pmc:query_id`) |
| **last_completed_at** | `TIMESTAMPTZ` | NO | - | 마지막 완료 시각 |
| overlap_days | `INT` | YES | `2` | 안전 윈도우 (일) |
| last_query | `TEXT` | YES | - | 마지막 쿼리 |
| last_result_count | `INT` | YES | - | 마지막 결과 수 |
| created_at | `TIMESTAMPTZ` | YES | `NOW()` | 생성 시각 |
| updated_at | `TIMESTAMPTZ` | YES | `NOW()` | 수정 시각 |

---

## 테이블 이름 변경 이력

> **2026-01-01**: 명명 규칙 통일 (`batch_*` 접두사)

| 이전 이름 | 새 이름 | 이유 |
|----------|--------|------|
| `collection_jobs` | `batch_jobs` | 업계 표준 용어, 범용성 |
| `article_jobs` | `batch_articles` | `batch_*` 통일 |
| `article_errors` | `batch_errors` | `batch_*` 통일 |
| `batch_job_logs` | `batch_logs` | 간소화 |

---

## 쿼리 예시

### 대기 중인 작업 조회 (우선순위순)

```sql
SELECT *
FROM batch_jobs
WHERE status IN ('pending', 'delayed')
  AND (next_run_at IS NULL OR next_run_at <= NOW())
ORDER BY priority, created_at
LIMIT 10;
```

### 실행 중인 작업의 진행률

```sql
SELECT
    id,
    job_type,
    query,
    status,
    processed_count,
    total_count,
    ROUND(processed_count::numeric / NULLIF(total_count, 0) * 100, 2) as progress_pct
FROM batch_jobs
WHERE status = 'running';
```

### 특정 작업의 에러 목록

```sql
SELECT pmcid, stage, error_code, error_message, created_at
FROM batch_errors
WHERE job_id = 'xxx-xxx-xxx'
ORDER BY created_at DESC;
```

### 검색 쿼리별 수집 현황

```sql
SELECT
    sq.name,
    sq.query,
    sq.total_collected,
    COUNT(DISTINCT bj.id) as job_count,
    MAX(bj.completed_at) as last_job_at
FROM search_queries sq
LEFT JOIN batch_jobs bj ON sq.id = bj.query_id
WHERE sq.is_active = TRUE
GROUP BY sq.id
ORDER BY sq.priority;
```

---

## 관련 문서

- [README.md](./README.md) - 데이터베이스 개요
- [papers.md](./papers.md) - 수집된 논문 테이블
- Batch Worker: `spikes/yts/batch/`
