# PostgreSQL + S3 스키마 설계

> **OAR-20**: 암 챗봇 서비스 DB 스키마 설계
>
> 결정: PostgreSQL (메타데이터/서비스) + S3 (대용량 텍스트)
>
<<<<<<<< HEAD:spikes/OAR-20/yts/docs/postgresql-스키마-설계-v2.4.md
> **버전**: v2.4 (2025-12-27)
========
> **버전**: v2.5 (2025-12-28)
>>>>>>>> 9513467 ( git commit -m "feat(OAR-20): PostgreSQL 스키마 v2.5 - 배치 수집 테이블 추가):spikes/OAR-20/yts/docs/postgresql-스키마-설계-v2.5.md
>
> 작성일: 2025-12-19

## 변경 이력

| 버전 | 날짜 | 변경 내용 |
|------|------|----------|
<<<<<<<< HEAD:spikes/OAR-20/yts/docs/postgresql-스키마-설계-v2.4.md
========
| v2.5 | 2025-12-28 | **배치 수집 테이블 추가**: `collection_jobs`, `watermarks` - 작업 큐 및 증분 수집 상태 관리 (OAR-22 배치 아키텍처 연계) |
>>>>>>>> 9513467 ( git commit -m "feat(OAR-20): PostgreSQL 스키마 v2.5 - 배치 수집 테이블 추가):spikes/OAR-20/yts/docs/postgresql-스키마-설계-v2.5.md
| v2.4 | 2025-12-27 | **변경 추적 컬럼 추가**: `raw_xml_hash`, `parser_version` - 원본 변경 vs 파서 변경 구분용 (OAR-19 피드백 반영) |
| v2.3 | 2025-12-22 | shallow 컬럼 GENERATED로 변경 (DB 보장), evidence 파싱 SQL에 text_version 추가 |
| v2.2 | 2025-12-22 | offset 정의 명확화 (char index), 재현 버전 우선순위 명시, GIN 인덱스 → shallow 컬럼 전환 |
| v2.1 | 2025-12-22 | canonical_key → canonical_prefix (이중관리 방지), 순수 텍스트 저장 (헤더 분리), pg_trgm 인덱스 추가, append-only 정책 명시 |
| v2 | 2025-12-22 | S3 포인터 통일 (bucket+key), evidence snippet 통일, 파티셔닝 FK 전략 추가 |
| v1 | 2025-12-19 | 초안 작성 |

---

## 아키텍처 개요

```
┌─────────────────────────────────────────────────────────────────┐
│                        암 챗봇 서비스                            │
└─────────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
        ▼                     ▼                     ▼
┌─────────────┐       ┌─────────────┐       ┌─────────────┐
│  Weaviate   │       │ PostgreSQL  │       │     S3      │
│ (Vector DB) │       │   (RDB)     │       │  (Storage)  │
├─────────────┤       ├─────────────┤       ├─────────────┤
│ PaperChunk  │       │ papers      │       │ canonical/  │
│ - 청크+벡터 │       │ users       │       │  {id}/v1.txt│
│ - 검색용    │       │ conversations│      │             │
│             │       │ messages    │       │ 대용량 원문 │
│             │       │ answer_logs │       │             │
└─────────────┘       └─────────────┘       └─────────────┘
     검색                 서비스               저장
```

---

## 설계 원칙

| 원칙 | 설명 |
|------|------|
| **PostgreSQL** | 메타데이터, 관계형 데이터, 트랜잭션 필요한 것 |
| **S3** | 대용량 텍스트 (canonical_text), 비용 효율 |
| **Weaviate** | 벡터 검색, 청크 저장 (별도 문서) |

---

## 테이블 설계

### 1. papers (논문 메타데이터)

```sql
CREATE TABLE papers (
    -- 식별자
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    paper_id VARCHAR(100) UNIQUE NOT NULL,  -- pmid:12345678 형식
    pmcid VARCHAR(20),
    pmid VARCHAR(20),
    doi VARCHAR(200),

    -- 메타데이터
    title TEXT NOT NULL,
    abstract TEXT,
    journal VARCHAR(500),
    year INTEGER,
    keywords TEXT[],              -- TEXT[] + GIN (단순 문자열 배열)

    -- 원문 관리 (S3 저장 구조 참고)
    canonical_bucket VARCHAR(100) DEFAULT 'oaria-papers',
    canonical_prefix TEXT,        -- canonical/pmid_12345678/ (버전 없이 prefix만)
    canonical_text_version VARCHAR(50) DEFAULT 'v1',  -- v1, v2, ...
    canonical_text_hash VARCHAR(64),  -- SHA256 (canonical_text 기준), 변경 감지용
    canonical_text_length INTEGER,
    -- 💡 실제 key는 코드에서 조합: f"{canonical_prefix}{canonical_text_version}.txt"
    --    → 버전 변경 시 canonical_text_version만 업데이트하면 됨 (이중관리 방지)

    -- 변경 추적 (v2.4 추가)
    -- 💡 목적: canonical_text_hash 변경 시 "원본 변경" vs "파서 변경" 구분
    raw_xml_hash VARCHAR(64),         -- SHA256 (원본 XML bytes 기준)
    parser_version VARCHAR(20) DEFAULT '1.0.0',  -- 파싱 로직 버전
    -- 변경 감지 로직:
    --   - raw_xml_hash 변경 → 업스트림 원본 변경 (Europe PMC에서 수정됨)
    --   - raw_xml_hash 동일 + parser_version 변경 → 파서 재처리 (우리 코드 변경)

    -- 수집 정보
    source VARCHAR(50) DEFAULT 'europe_pmc',
    source_url TEXT,
    is_open_access BOOLEAN DEFAULT TRUE,

    -- 처리 상태
    status VARCHAR(20) DEFAULT 'collected',  -- collected, chunked, indexed
    chunked_at TIMESTAMPTZ,
    indexed_at TIMESTAMPTZ,

    -- 타임스탬프
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 인덱스
-- paper_id는 UNIQUE 제약조건으로 자동 인덱스 생성됨

-- 외부 ID: NULL 허용하되, 값이 있으면 유니크 (중복 방지)
CREATE UNIQUE INDEX idx_papers_pmcid_unique ON papers(pmcid) WHERE pmcid IS NOT NULL;
CREATE UNIQUE INDEX idx_papers_pmid_unique ON papers(pmid) WHERE pmid IS NOT NULL;
CREATE UNIQUE INDEX idx_papers_doi_unique ON papers(doi) WHERE doi IS NOT NULL;

-- 필터링용
CREATE INDEX idx_papers_year ON papers(year);
CREATE INDEX idx_papers_status ON papers(status);
CREATE INDEX idx_papers_created_at ON papers(created_at);
CREATE INDEX idx_papers_keywords ON papers USING GIN(keywords);
```

### 2. paper_authors (저자 - 정규화)

> 저자 순서, 교신저자 여부 등 학술 논문 특성 반영

```sql
CREATE TABLE paper_authors (
    paper_id UUID REFERENCES papers(id) ON DELETE CASCADE,
    author_order SMALLINT NOT NULL,       -- 1, 2, 3... (저자 순서)
    author_name TEXT NOT NULL,
    is_corresponding BOOLEAN DEFAULT FALSE,  -- 교신저자 여부
    orcid VARCHAR(50),                    -- ORCID (선택)
    affiliation TEXT,                     -- 소속 (선택)
    PRIMARY KEY (paper_id, author_order)
);

-- 저자 이름 검색용 (정확 매칭)
CREATE INDEX idx_paper_authors_name ON paper_authors(author_name);

-- 저자 이름 부분 검색용 (ILIKE '%...%' 지원)
-- ⚠️ pg_trgm 확장 필요: CREATE EXTENSION pg_trgm;
CREATE INDEX idx_paper_authors_name_trgm ON paper_authors
    USING GIN (author_name gin_trgm_ops);

-- 교신저자만 필터링
CREATE INDEX idx_paper_authors_corresponding ON paper_authors(paper_id)
    WHERE is_corresponding = TRUE;
```

**쿼리 예시:**

```sql
-- 특정 저자의 모든 논문 조회 (pg_trgm 인덱스 활용)
SELECT p.*
FROM papers p
JOIN paper_authors pa ON p.id = pa.paper_id
WHERE pa.author_name ILIKE '%Kim%';  -- GIN(trgm)으로 효율적 검색

-- 논문의 저자 목록 (순서대로)
SELECT author_name, is_corresponding, orcid
FROM paper_authors
WHERE paper_id = $1
ORDER BY author_order;

-- 1저자 논문만 조회
SELECT p.*
FROM papers p
JOIN paper_authors pa ON p.id = pa.paper_id
WHERE pa.author_name = 'Kim J'
  AND pa.author_order = 1;
```

### 3. users (사용자)

```sql
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- 인증
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255),           -- NULL이면 OAuth 전용
    oauth_provider VARCHAR(50),           -- google, github 등
    oauth_id VARCHAR(255),

    -- 프로필
    name VARCHAR(100),
    role VARCHAR(20) DEFAULT 'user',      -- user, researcher, admin
    organization VARCHAR(200),

    -- 설정
    preferences JSONB DEFAULT '{}',       -- UI 설정, 알림 등

    -- 상태
    is_active BOOLEAN DEFAULT TRUE,
    last_login_at TIMESTAMPTZ,

    -- 타임스탬프
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- email은 UNIQUE 제약조건으로 자동 인덱스 생성됨
CREATE UNIQUE INDEX idx_users_oauth ON users(oauth_provider, oauth_id)
    WHERE oauth_provider IS NOT NULL;
```

### 4. conversations (대화 세션)

```sql
CREATE TABLE conversations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,

    -- 대화 정보
    title VARCHAR(200),                   -- 자동 생성 또는 사용자 입력
    summary TEXT,                         -- 대화 요약 (선택)

    -- 상태
    status VARCHAR(20) DEFAULT 'active',  -- active, archived, deleted
    message_count INTEGER DEFAULT 0,      -- ⚠️ 트리거로 자동 갱신 (아래 참고)

    -- 타임스탬프
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    last_message_at TIMESTAMPTZ           -- ⚠️ 트리거로 자동 갱신 (아래 참고)
);

CREATE INDEX idx_conversations_user_id ON conversations(user_id);
CREATE INDEX idx_conversations_status ON conversations(status);
CREATE INDEX idx_conversations_updated_at ON conversations(updated_at);
```

**message_count / last_message_at 갱신 전략: 트리거 자동화**

> ⚠️ **정책: messages는 append-only** (삭제/수정 없음)
> - 대화 이력은 감사/재현 목적으로 불변 유지
> - 삭제 필요 시 conversation 전체를 soft-delete (status='deleted')

```sql
-- messages INSERT 시 conversations 자동 갱신
CREATE OR REPLACE FUNCTION update_conversation_stats()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        UPDATE conversations
        SET message_count = message_count + 1,
            last_message_at = NEW.created_at,
            updated_at = NOW()
        WHERE id = NEW.conversation_id;
        RETURN NEW;
    ELSIF TG_OP = 'DELETE' THEN
        -- 예외 케이스 (마이그레이션 등)
        UPDATE conversations
        SET message_count = GREATEST(0, message_count - 1),
            updated_at = NOW()
        WHERE id = OLD.conversation_id;
        RETURN OLD;
    END IF;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_update_conversation_stats
    AFTER INSERT OR DELETE ON messages
    FOR EACH ROW
    EXECUTE FUNCTION update_conversation_stats();
```

> **선택 이유**: 애플리케이션 갱신은 누락 위험 → 트리거로 일관성 보장
> **DELETE 트리거**: 정상 운영에서는 사용 안 함, 마이그레이션/정리 시 안전망

### 5. messages (메시지)

```sql
CREATE TABLE messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID REFERENCES conversations(id) ON DELETE CASCADE,

    -- 메시지 내용
    role VARCHAR(20) NOT NULL,            -- user, assistant, system
    content TEXT NOT NULL,

    -- 메타데이터
    tokens_used INTEGER,                  -- 토큰 사용량
    model VARCHAR(50),                    -- gpt-4, claude-3 등
    latency_ms INTEGER,                   -- 응답 시간

    -- 타임스탬프
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_messages_conversation_id ON messages(conversation_id);
CREATE INDEX idx_messages_created_at ON messages(created_at);
```

### 6. answer_logs (답변 로그 - 감사/재현용)

```sql
CREATE TABLE answer_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    message_id UUID REFERENCES messages(id) ON DELETE SET NULL,
    conversation_id UUID REFERENCES conversations(id) ON DELETE SET NULL,
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,

    -- 질문/답변
    question TEXT NOT NULL,
    answer TEXT NOT NULL,

    -- 검색 정보
    search_query TEXT,                    -- 벡터 검색에 사용된 쿼리
    search_filters JSONB,                 -- year >= 2020, section = 'results' 등

    -- 근거 (재현용 핵심!)
    evidence JSONB NOT NULL,
    /*
    evidence 구조:
    [
        {
            "paper_id": "pmid:12345678",
            "chunk_id": "pmid:12345678|results|0",
            "snippet": "Osimertinib showed 80%...",  -- ⚠️ 300~800자 스니펫만 저장!
            "offset_start": 12340,
            "offset_end": 13500,
            "text_version": "v1",  -- papers.canonical_text_version과 동일 형식
            "distance": 0.15,
            "section": "results"
        },
        ...
    ]

    💡 원문 재현: S3에서 canonical_text[offset_start:offset_end] 조회
       snippet은 UI 미리보기용, 정확한 원문은 항상 S3+offset으로 재구성
    */

    -- 얕은 컬럼 (목록 조회용, GIN 대체)
    -- 💡 GENERATED 컬럼: evidence JSONB에서 자동 추출 (DB가 보장, 누락 불가)
    first_paper_id VARCHAR(100) GENERATED ALWAYS AS (evidence->0->>'paper_id') STORED,
    evidence_count SMALLINT GENERATED ALWAYS AS (jsonb_array_length(evidence)::smallint) STORED,

    -- LLM 정보
    model VARCHAR(50),
    prompt_tokens INTEGER,
    completion_tokens INTEGER,
    total_tokens INTEGER,

    -- 성능
    search_latency_ms INTEGER,
    llm_latency_ms INTEGER,
    total_latency_ms INTEGER,

    -- 타임스탬프 (불변)
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_answer_logs_user_id ON answer_logs(user_id);
CREATE INDEX idx_answer_logs_conversation_id ON answer_logs(conversation_id);
CREATE INDEX idx_answer_logs_created_at ON answer_logs(created_at);

-- 얕은 컬럼 인덱스 (GIN 대체 - 목록 화면용)
CREATE INDEX idx_answer_logs_first_paper ON answer_logs(first_paper_id);

-- ⚠️ GIN 인덱스는 '운영하면서 정말 필요해질 때' 추가
-- CREATE INDEX idx_answer_logs_evidence ON answer_logs USING GIN(evidence);
```

### 7. feedbacks (피드백)

```sql
CREATE TABLE feedbacks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    answer_log_id UUID REFERENCES answer_logs(id) ON DELETE CASCADE,
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,

    -- 평가
    rating INTEGER CHECK (rating >= 1 AND rating <= 5),  -- 1-5점
    is_helpful BOOLEAN,                   -- 도움됨/안됨
    feedback_type VARCHAR(50),            -- accuracy, relevance, clarity 등

    -- 상세 피드백
    comment TEXT,
    selected_evidence JSONB,              -- 유용했던 근거 선택

    -- 타임스탬프
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_feedbacks_answer_log_id ON feedbacks(answer_log_id);
CREATE INDEX idx_feedbacks_user_id ON feedbacks(user_id);
CREATE INDEX idx_feedbacks_rating ON feedbacks(rating);
```

### 8. collection_jobs (수집 작업 큐) - v2.5 추가

> 배치 수집 작업 관리 (OAR-22 배치 아키텍처 연계)
>
> **목적**: 초기 적재(A), 증분 수집(B), 보정(C) 작업의 상태/우선순위/재시도 관리

```sql
CREATE TABLE collection_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- 기본 정보
    job_type VARCHAR(20) NOT NULL,        -- backfill, incremental, repair
    priority INT DEFAULT 10,               -- 낮을수록 우선 (1=최우선)
    query TEXT NOT NULL,                   -- 검색 쿼리
    params JSONB,                          -- 추가 파라미터
    api_name VARCHAR(50) DEFAULT 'europe_pmc',  -- API별 limiter 연결

    -- 상태 관리
    status VARCHAR(20) DEFAULT 'pending',  -- pending, running, completed, failed, delayed
    checkpoint JSONB,                      -- 체크포인트 (중단 재개용)

    -- 재시도 관리
    attempt_count INT DEFAULT 0,           -- 현재까지 시도 횟수
    max_attempts INT DEFAULT 5,            -- 최대 재시도 횟수
    next_run_at TIMESTAMPTZ,               -- 429/백오프 후 재실행 시각 (delay queue)

    -- 워커 락 (동시 처리 방지)
    locked_at TIMESTAMPTZ,                 -- 워커가 집어간 시각
    locked_by VARCHAR(100),                -- 워커 ID

    -- 에러 추적
    last_error_code VARCHAR(10),           -- 429, 500, TIMEOUT 등
    last_error_message TEXT,
    last_error_at TIMESTAMPTZ,

    -- 타임스탬프
    created_at TIMESTAMPTZ DEFAULT NOW(),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ
);

-- 인덱스 1: 우선순위 순으로 pending/delayed 작업 조회 (SKIP LOCKED 패턴)
CREATE INDEX idx_jobs_pending ON collection_jobs (priority, created_at)
    WHERE status IN ('pending', 'delayed') AND (next_run_at IS NULL OR next_run_at <= NOW());

-- 인덱스 2: delayed 작업 중 실행 가능한 것
CREATE INDEX idx_jobs_delayed ON collection_jobs (next_run_at)
    WHERE status = 'delayed' AND next_run_at IS NOT NULL;

-- 인덱스 3: 오래된 락 감지 (좀비 워커)
CREATE INDEX idx_jobs_stale_lock ON collection_jobs (locked_at)
    WHERE status = 'running';

-- 인덱스 4: 작업 유형별 조회
CREATE INDEX idx_jobs_type ON collection_jobs (job_type, status);
```

**워커의 작업 획득 (SKIP LOCKED 패턴):**

```sql
UPDATE collection_jobs
SET status = 'running',
    locked_at = NOW(),
    locked_by = $1  -- worker_id
WHERE id = (
    SELECT id FROM collection_jobs
    WHERE status IN ('pending', 'delayed')
      AND (next_run_at IS NULL OR next_run_at <= NOW())
    ORDER BY priority, COALESCE(next_run_at, created_at), created_at
    LIMIT 1
    FOR UPDATE SKIP LOCKED
)
RETURNING *;
```

### 9. watermarks (증분 수집 상태) - v2.5 추가

> 증분 수집의 마지막 완료 시점 추적
>
> **목적**: 다음 증분 수집 시 from_date 계산, 안전 윈도우(overlap) 적용

```sql
CREATE TABLE watermarks (
    id VARCHAR(100) PRIMARY KEY,           -- 'incremental:europe_pmc:breast_cancer'

    -- 상태
    last_completed_at TIMESTAMPTZ NOT NULL,  -- 마지막 성공 완료 시각
    overlap_days INT DEFAULT 2,              -- 안전 윈도우 (일)

    -- 메타데이터
    last_query TEXT,                         -- 마지막 실행한 쿼리
    last_result_count INT,                   -- 마지막 수집 건수

    -- 타임스탬프
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

**사용 예시:**

```python
@dataclass
class IncrementalState:
    """증분 수집 상태"""
    last_completed_at: datetime
    overlap_days: int = 2

    @property
    def from_date(self) -> datetime:
        """시작 날짜 (overlap 적용)"""
        return self.last_completed_at - timedelta(days=self.overlap_days)

# 워터마크 조회
state = await db.fetchrow("""
    SELECT last_completed_at, overlap_days
    FROM watermarks WHERE id = $1
""", 'incremental:europe_pmc')

# 성공 완료 시에만 워터마크 업데이트
await db.execute("""
    INSERT INTO watermarks (id, last_completed_at, last_query, last_result_count)
    VALUES ($1, NOW(), $2, $3)
    ON CONFLICT (id) DO UPDATE SET
        last_completed_at = EXCLUDED.last_completed_at,
        last_query = EXCLUDED.last_query,
        last_result_count = EXCLUDED.last_result_count,
        updated_at = NOW()
""", watermark_id, query, count)
```

---

## S3 저장 구조

### 버킷 구조

```
s3://oaria-papers/
├── canonical/
│   ├── pmid_12345678/
│   │   ├── v1.txt                    # canonical text v1
│   │   ├── v2.txt                    # canonical text v2 (있으면)
│   │   └── metadata.json             # 버전 메타데이터
│   ├── pmid_12345679/
│   │   └── v1.txt
│   └── ...
│
├── raw/                              # 원본 데이터 (백업)
│   ├── europe_pmc/
│   │   ├── PMC12345678.xml
│   │   └── ...
│   └── ...
│
└── exports/                          # 내보내기용
    └── ...
```

### canonical text 파일 형식

> ⚠️ **순수 텍스트만 저장** (헤더 없음) - offset 계산의 일관성 보장

```
# s3://oaria-papers/canonical/pmid_12345678/v1.txt
# → 순수 텍스트만 (offset 0부터 바로 본문)

Background: Immune checkpoint inhibitors have revolutionized cancer treatment.
In this study, we investigated the efficacy of...
(전체 원문 텍스트)
```

```json
// s3://oaria-papers/canonical/pmid_12345678/metadata.json
// → 메타데이터는 별도 파일로 분리
{
    "paper_id": "pmid:12345678",
    "versions": {
        "v1": {
            "created_at": "2024-01-15T10:30:00Z",
            "hash": "sha256:abc123...",
            "length": 45678,
            "sections": ["abstract", "introduction", "methods", "results", "discussion"]
        }
    }
}
```

**offset 규칙 (char index 기준):**

> ⚠️ **byte offset 아님!** UTF-8 디코딩 후 Python str의 character index

- `offset_start`, `offset_end`는 **디코딩된 텍스트(str)** 기준 char index
- `text[offset_start:offset_end]`로 바로 추출 가능 (Python 슬라이싱)
- UTF-8 멀티바이트 문자(한글, 그리스문자 등)에서도 안전
- ⚠️ **chunking도 동일 canonical(vN) 기준으로 수행** → offset 일관성 보장

```python
# 올바른 사용법
text = get_canonical_text(bucket, prefix, version)  # str (UTF-8 decoded)
snippet = text[offset_start:offset_end]  # char index로 슬라이싱

# ❌ 잘못된 사용법 (byte offset과 혼동)
# bytes_data[offset_start:offset_end].decode()  # 멀티바이트 깨질 수 있음
```

### S3 접근 패턴

```python
import boto3
from typing import Tuple

s3 = boto3.client('s3')
DEFAULT_BUCKET = 'oaria-papers'

def build_canonical_prefix(paper_id: str) -> str:
    """papers.canonical_prefix 생성 (버전 없이)"""
    # pmid:12345678 → pmid_12345678
    safe_id = paper_id.replace(':', '_')
    return f"canonical/{safe_id}/"

def build_canonical_key(prefix: str, version: str) -> str:
    """prefix + version으로 실제 S3 key 조합 (이중관리 방지)"""
    return f"{prefix}{version}.txt"

def get_canonical_text(bucket: str, prefix: str, version: str) -> str:
    """S3에서 canonical text 조회"""
    key = build_canonical_key(prefix, version)
    response = s3.get_object(Bucket=bucket, Key=key)
    return response['Body'].read().decode('utf-8')

def save_canonical_text(
    paper_id: str,
    text: str,
    version: str = 'v1',
    bucket: str = DEFAULT_BUCKET
) -> Tuple[str, str, str]:
    """S3에 canonical text 저장 → (bucket, prefix, version) 반환"""
    prefix = build_canonical_prefix(paper_id)
    key = build_canonical_key(prefix, version)
    s3.put_object(
        Bucket=bucket,
        Key=key,
        Body=text.encode('utf-8'),
        ContentType='text/plain; charset=utf-8'
    )
    return (bucket, prefix, version)

# 사용 예시
bucket, prefix, version = save_canonical_text("pmid:12345678", full_text, "v1")
# → papers 테이블에 canonical_bucket, canonical_prefix, canonical_text_version 저장
# → 버전 업그레이드 시: canonical_text_version만 'v2'로 변경
```

---

## ER 다이어그램

```
┌─────────────┐       ┌─────────────────┐       ┌─────────────┐
│   users     │       │  conversations  │       │  messages   │
├─────────────┤       ├─────────────────┤       ├─────────────┤
│ id (PK)     │──┐    │ id (PK)         │──┐    │ id (PK)     │
│ email       │  │    │ user_id (FK)    │  │    │ conv_id(FK) │
│ name        │  │    │ title           │  │    │ role        │
│ role        │  └───▶│ status          │  └───▶│ content     │
│ ...         │       │ ...             │       │ ...         │
└─────────────┘       └─────────────────┘       └─────────────┘
      │                       │
      │                       │
      ▼                       ▼
┌─────────────────────────────────────────┐
│              answer_logs                │
├─────────────────────────────────────────┤
│ id (PK)                                 │
│ message_id (FK)                         │
│ conversation_id (FK)                    │
│ user_id (FK)                            │
│ question                                │
│ answer                                  │
│ evidence (JSONB) ◄── 근거 (재현용 핵심)  │
│ ...                                     │
└─────────────────────────────────────────┘
      │
      ▼
┌─────────────┐       ┌─────────────┐       ┌─────────────────┐
│  feedbacks  │       │   papers    │       │  paper_authors  │
├─────────────┤       ├─────────────┤       ├─────────────────┤
│ id (PK)     │       │ id (PK)     │◄──────│ paper_id (FK)   │
│ answer_log  │       │ paper_id    │       │ author_order    │
│ rating      │       │ title       │       │ author_name     │
│ comment     │       │ keywords[]  │       │ is_corresponding│
│ ...         │       │ canonical_  │       │ orcid           │
└─────────────┘       │ prefix+ver  │──▶ S3 │ affiliation     │
                      └─────────────┘       └─────────────────┘
                            ▲
                            │
                      answer_logs.evidence 참조

┌───────────────────────────────────────────────────────────────┐
│                   배치 수집 시스템 (v2.5)                        │
├───────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌─────────────────┐              ┌─────────────────┐         │
│  │ collection_jobs │              │   watermarks    │         │
│  ├─────────────────┤              ├─────────────────┤         │
│  │ id (PK)         │              │ id (PK)         │         │
│  │ job_type        │              │ last_completed  │         │
│  │ priority        │              │ overlap_days    │         │
│  │ status          │──────────────│ (증분 수집 상태) │         │
│  │ checkpoint      │              └─────────────────┘         │
│  │ attempt_count   │                      │                   │
│  │ next_run_at     │                      ▼                   │
│  │ (작업 큐)        │              ┌─────────────┐             │
│  └─────────────────┘              │   papers    │             │
│          │                        │ (수집 대상)  │             │
│          └───────────────────────▶└─────────────┘             │
│                                                               │
└───────────────────────────────────────────────────────────────┘
```

---

## 데이터 흐름

### 1. 논문 수집 → 저장

```
Europe PMC API
      │
      ▼
┌─────────────────────────────────────┐
│ 1. 메타데이터 파싱                   │
│ 2. canonical text 생성 (정규화)     │
│ 3. SHA256 해시 계산                 │
└─────────────────────────────────────┘
      │
      ├──────────────────────────────┐
      │                              │
      ▼                              ▼
┌─────────────┐              ┌─────────────┐
│ PostgreSQL  │              │     S3      │
│ papers 저장 │              │ canonical/  │
│ - 메타데이터│              │ 원문 저장   │
│ - bucket/   │              │             │
│   prefix/ver│              │             │
└─────────────┘              └─────────────┘
```

### 2. 질문 → 답변

```
사용자 질문
      │
      ▼
┌─────────────────────────────────────┐
│ 1. 질문 임베딩                       │
│ 2. Weaviate 벡터 검색               │
│    → 관련 청크 반환 (offset 포함)    │
└─────────────────────────────────────┘
      │
      ▼
┌─────────────────────────────────────┐
│ 3. LLM 답변 생성                     │
│    - 청크를 컨텍스트로 제공          │
│    - 답변 + 근거 생성                │
└─────────────────────────────────────┘
      │
      ├──────────────────────────────┐
      │                              │
      ▼                              ▼
┌─────────────┐              ┌─────────────┐
│ messages    │              │ answer_logs │
│ 저장        │              │ 저장        │
│             │              │ (근거 포함) │
└─────────────┘              └─────────────┘
```

### 3. 근거 재현 (하이라이트)

```
"이 근거 원문 보여줘"
      │
      ▼
┌─────────────────────────────────────┐
│ answer_logs.evidence 조회            │
│ → paper_id, offset_start, offset_end │
│ → text_version (⭐ 재현의 기준!)     │
└─────────────────────────────────────┘
      │
      ▼
┌─────────────────────────────────────┐
│ papers 조회                          │
│ → canonical_bucket, canonical_prefix│
└─────────────────────────────────────┘
      │
      ▼
┌─────────────────────────────────────┐
│ 버전 결정 (중요!)                    │
│ version = evidence.text_version     │
│           ?? papers.canonical_text_ │
│              version (fallback)     │
└─────────────────────────────────────┘
      │
      ▼
┌─────────────────────────────────────┐
│ S3에서 canonical text 조회           │
│ → get_canonical_text(bucket,        │
│     prefix, version)                │
│ → text[offset_start:offset_end]     │
│ → 해당 구간 하이라이트               │
└─────────────────────────────────────┘
```

**재현(reproduce) 버전 우선순위:**
1. `evidence.text_version` → 답변 생성 시 사용한 버전 (정확한 재현)
2. `papers.canonical_text_version` → fallback (evidence에 없을 때만)

> ⚠️ 재현 정확성이 중요하면 항상 `evidence.text_version` 사용.
> `papers.canonical_text_version`은 "최신 보기" 용도로만 활용.

---

## 마이그레이션 (Alembic)

### 초기 마이그레이션

```python
# alembic/versions/001_initial.py

def upgrade():
    # papers (먼저 생성)
    op.create_table('papers', ...)

    # paper_authors (papers FK 참조)
    op.create_table('paper_authors', ...)

    # users
    op.create_table('users', ...)

    # conversations
    op.create_table('conversations', ...)

    # messages
    op.create_table('messages', ...)

    # answer_logs
    op.create_table('answer_logs', ...)

    # feedbacks
    op.create_table('feedbacks', ...)

def downgrade():
    op.drop_table('feedbacks')
    op.drop_table('answer_logs')
    op.drop_table('messages')
    op.drop_table('conversations')
    op.drop_table('users')
    op.drop_table('paper_authors')  # papers 전에 삭제
    op.drop_table('papers')
```

---

## 쿼리 예시

### 최근 대화 목록

```sql
SELECT
    c.id,
    c.title,
    c.message_count,
    c.last_message_at,
    m.content as last_message
FROM conversations c
LEFT JOIN LATERAL (
    SELECT content
    FROM messages
    WHERE conversation_id = c.id
    ORDER BY created_at DESC
    LIMIT 1
) m ON true
WHERE c.user_id = $1
  AND c.status = 'active'
ORDER BY c.last_message_at DESC
LIMIT 20;
```

### 답변의 근거 논문 조회

```sql
-- 간단 버전: 첫 번째 근거만 (목록 화면용)
SELECT
    al.id,
    al.question,
    al.answer,
    al.created_at,
    p.title as first_paper_title
FROM answer_logs al
LEFT JOIN papers p ON p.paper_id = (al.evidence->0->>'paper_id')
WHERE al.id = $1;

-- 전체 근거 조회: 모든 evidence를 papers와 JOIN (상세 화면용)
SELECT
    al.id,
    al.question,
    al.answer,
    al.created_at,
    e.ordinal,
    e.paper_id,
    e.chunk_id,
    e.snippet,
    e.offset_start,
    e.offset_end,
    e.section,
    e.distance,
    p.title as paper_title,
    p.canonical_bucket,
    p.canonical_prefix,
    p.canonical_text_version
FROM answer_logs al
CROSS JOIN LATERAL jsonb_array_elements(al.evidence)
    WITH ORDINALITY AS e_raw(elem, ordinal)
CROSS JOIN LATERAL (
    SELECT
        elem->>'paper_id' as paper_id,
        elem->>'chunk_id' as chunk_id,
        elem->>'snippet' as snippet,
        (elem->>'offset_start')::int as offset_start,
        (elem->>'offset_end')::int as offset_end,
        elem->>'text_version' as text_version,  -- ⭐ 재현 버전 (우선)
        elem->>'section' as section,
        (elem->>'distance')::float as distance
    FROM (SELECT e_raw.elem) sub
) e
LEFT JOIN papers p ON p.paper_id = e.paper_id
WHERE al.id = $1
ORDER BY e.ordinal;
```

### 피드백 통계

```sql
SELECT
    DATE_TRUNC('day', f.created_at) as date,
    COUNT(*) as total_feedbacks,
    AVG(f.rating) as avg_rating,
    COUNT(*) FILTER (WHERE f.is_helpful = true) as helpful_count,
    COUNT(*) FILTER (WHERE f.is_helpful = false) as not_helpful_count
FROM feedbacks f
WHERE f.created_at >= NOW() - INTERVAL '30 days'
GROUP BY DATE_TRUNC('day', f.created_at)
ORDER BY date DESC;
```

---

## 인덱스 전략

| 테이블 | 인덱스 | 용도 |
|--------|--------|------|
| `papers` | `paper_id` (UNIQUE 자동) | PK 조회 |
| `papers` | `pmcid`, `pmid`, `doi` (Partial UNIQUE) | 외부 ID 중복 방지 |
| `papers` | `year`, `status` | 필터링 |
| `papers` | `keywords` (GIN) | 키워드 배열 검색 |
| `paper_authors` | `author_name` | 저자 이름 검색 |
| `paper_authors` | `is_corresponding` (Partial) | 교신저자 필터 |
| `conversations` | `user_id`, `status` | 사용자별 대화 목록 |
| `messages` | `conversation_id` | 대화 내 메시지 조회 |
| `answer_logs` | `first_paper_id` | 목록 화면용 (GIN 대체) |
| `answer_logs` | `created_at` | 시계열 조회 |
| `collection_jobs` | `priority, created_at` (Partial) | SKIP LOCKED 작업 획득 |
| `collection_jobs` | `next_run_at` (Partial) | delayed 작업 조회 |
| `collection_jobs` | `locked_at` (Partial) | 좀비 워커 감지 |
| `collection_jobs` | `job_type, status` | 작업 유형별 조회 |

---

## 파티셔닝 전략 (Scale-up 로드맵)

> `messages`, `answer_logs`는 **증가만 하는 시계열 데이터** → 파티셔닝 필수

### 현재 (MVP)

파티셔닝 없이 단일 테이블로 시작. 수백만 건까지는 인덱스로 충분.

```
⚠️ MVP 스키마와 파티션 스키마는 별개!
   - MVP: 위 테이블 설계 섹션 그대로 사용 (FK 포함)
   - Phase 1+: 아래 파티션 스키마로 마이그레이션 (FK 전략 변경 필요)
```

### Phase 1: 월 단위 파티셔닝 (100만 건+)

**⚠️ FK 전략 변경 필요 (중요!)**

파티션 테이블은 PK에 파티션 키 포함이 필수 → 기존 FK 설계와 충돌 발생:
- `answer_logs.message_id → messages(id)` FK가 깨짐
- `feedbacks.answer_log_id → answer_logs(id)` FK도 동일

**권장: Approach A - Soft Link (FK 제거)**

```sql
-- messages 파티셔닝 (FK 제거, 복합 PK)
CREATE TABLE messages (
    id UUID NOT NULL DEFAULT gen_random_uuid(),
    conversation_id UUID NOT NULL,  -- FK 제거, 애플리케이션에서 검증
    role VARCHAR(20) NOT NULL,
    content TEXT NOT NULL,
    tokens_used INTEGER,
    model VARCHAR(50),
    latency_ms INTEGER,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    PRIMARY KEY (id, created_at)  -- 파티션 키 포함 필수
) PARTITION BY RANGE (created_at);

-- id만으로 조회 가능하게
CREATE UNIQUE INDEX idx_messages_id ON messages(id);

-- 월별 파티션 생성
CREATE TABLE messages_2025_01 PARTITION OF messages
    FOR VALUES FROM ('2025-01-01') TO ('2025-02-01');
-- ...

-- answer_logs도 동일 (FK 제거, 독립 로그화)
CREATE TABLE answer_logs (
    id UUID NOT NULL DEFAULT gen_random_uuid(),
    message_id UUID,              -- FK 제거 → soft link (nullable)
    conversation_id UUID,         -- FK 제거 → soft link
    user_id UUID,                 -- FK 제거 → soft link
    question TEXT NOT NULL,
    answer TEXT NOT NULL,
    evidence JSONB NOT NULL,
    -- ... 나머지 컬럼
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    PRIMARY KEY (id, created_at)
) PARTITION BY RANGE (created_at);
```

**Approach A 선택 이유:**
- `answer_logs`는 "감사/재현용 불변 로그" → 독립성이 중요
- FK로 과하게 묶으면 운영 마이그레이션 난이도만 상승
- 대부분 프로덕션 로그 테이블은 soft link 방식 채택

**대안: Approach B - 복합 FK (비권장)**

```sql
-- 복합 PK 참조 (운영 복잡도↑)
answer_logs.message_id UUID,
answer_logs.message_created_at TIMESTAMPTZ,
FOREIGN KEY (message_id, message_created_at) REFERENCES messages(id, created_at)
```
→ 쿼리마다 created_at을 함께 넘겨야 해서 실용성 낮음

### Phase 2: pg_partman 자동화 (1000만 건+)

```sql
-- pg_partman 확장 설치
CREATE EXTENSION pg_partman;

-- 자동 파티션 관리 설정
SELECT partman.create_parent(
    p_parent_table := 'public.messages',
    p_control := 'created_at',
    p_type := 'native',
    p_interval := 'monthly',
    p_premake := 3  -- 3개월 미리 생성
);

-- 오래된 파티션 자동 보관
UPDATE partman.part_config
SET retention = '12 months',
    retention_keep_table = true  -- DROP 대신 DETACH
WHERE parent_table = 'public.messages';
```

### 파티셔닝 적용 시점 기준

| 지표 | 임계값 | 액션 |
|------|--------|------|
| 테이블 크기 | > 10GB | 파티셔닝 검토 |
| 일일 INSERT | > 10만 건 | Phase 1 적용 |
| 총 레코드 | > 1000만 건 | Phase 2 (pg_partman) |

### 주의사항

- 파티션 키(`created_at`)는 PK에 포함되어야 함
- FK 참조하는 테이블(`feedbacks → answer_logs`)은 함께 마이그레이션
- 파티션 전환 시 다운타임 최소화: `pg_dump` → 새 테이블 → `RENAME`

---

## 백업 전략

### PostgreSQL

```bash
# 일일 백업
pg_dump -Fc oaria_db > backup_$(date +%Y%m%d).dump

# S3에 업로드
aws s3 cp backup_$(date +%Y%m%d).dump s3://oaria-backups/postgresql/
```

### S3

```yaml
# S3 버전 관리 활성화
aws s3api put-bucket-versioning \
  --bucket oaria-papers \
  --versioning-configuration Status=Enabled

# 수명 주기 정책 (90일 후 Glacier)
```

---

## 다음 단계

- [ ] Alembic 마이그레이션 스크립트 작성
- [ ] SQLAlchemy 모델 정의
- [ ] S3 클라이언트 유틸리티 작성
- [ ] 테스트 데이터 생성

---

## 참고

- [PostgreSQL JSONB](https://www.postgresql.org/docs/current/datatype-json.html)
- [AWS S3 Best Practices](https://docs.aws.amazon.com/AmazonS3/latest/userguide/optimizing-performance.html)
- [Alembic Tutorial](https://alembic.sqlalchemy.org/en/latest/tutorial.html)
