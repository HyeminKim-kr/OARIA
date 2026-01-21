# Chat / RAG 테이블

> **Last Updated**: 2026-01-19
>
> **Owner**: Alembic (Backend)

---

## 개요

챗봇 기능을 위한 대화 관련 테이블입니다.

```
users ──1:N──▶ conversations ──1:N──▶ messages
                     │
                     ├──N:1──▶ papers (논문별 채팅용, nullable)
                     │
                     └──1:N──▶ answer_logs (감사/재현용)
                                    │
                                    └──1:N──▶ feedbacks (사용자 피드백)

admin_users ──1:N──▶ lab_feedbacks (Admin 테스트 피드백)
```

---

## 테이블

### 1. conversations (대화 세션)

| 컬럼 | 타입 | 제약 | 설명 |
|------|------|------|------|
| `id` | UUID | PK | 대화 ID |
| `user_id` | UUID | FK → users.id | 사용자 ID |
| `paper_id` | UUID | FK → papers.id, nullable | 논문 ID (논문별 채팅용) |
| `conversation_type` | VARCHAR(20) | DEFAULT 'global' | global (전체 검색), paper (논문별 채팅) |
| `title` | VARCHAR(200) | nullable | 대화 제목 (자동 생성 또는 사용자 입력) |
| `status` | VARCHAR(20) | DEFAULT 'active' | active, archived, deleted |
| `message_count` | INTEGER | DEFAULT 0 | 메시지 수 (트리거 자동 갱신) |
| `created_at` | TIMESTAMPTZ | DEFAULT NOW() | 생성일 |
| `updated_at` | TIMESTAMPTZ | DEFAULT NOW() | 수정일 |
| `last_message_at` | TIMESTAMPTZ | nullable | 마지막 메시지 시간 (트리거 자동 갱신) |

**conversation_type 값:**
- `global`: 전체 논문 컬렉션 대상 검색 (기존 /ask 페이지)
- `paper`: 특정 논문에 대한 채팅 (논문 상세 페이지)

**인덱스:**
- `idx_conversations_user_id` - 사용자별 대화 목록
- `idx_conversations_paper_id` - 논문별 대화 목록
- `idx_conversations_type` - 타입별 필터링
- `idx_conversations_status` - 상태별 필터링
- `idx_conversations_updated_at` - 정렬

### 2. messages (메시지)

| 컬럼 | 타입 | 제약 | 설명 |
|------|------|------|------|
| `id` | UUID | PK | 메시지 ID |
| `conversation_id` | UUID | FK → conversations.id | 대화 ID |
| `role` | VARCHAR(20) | NOT NULL | user, assistant, system |
| `content` | TEXT | NOT NULL | 메시지 내용 |
| `tokens_used` | INTEGER | nullable | 토큰 사용량 |
| `model` | VARCHAR(50) | nullable | gpt-4, claude-3 등 |
| `latency_ms` | INTEGER | nullable | 응답 시간 (ms) |
| `created_at` | TIMESTAMPTZ | DEFAULT NOW() | 생성일 |

**인덱스:**
- `idx_messages_conversation_id` - 대화 내 메시지 조회
- `idx_messages_created_at` - 시간순 정렬

**정책:**
- messages는 **append-only** (삭제/수정 없음)
- 대화 삭제 시 conversation의 status='deleted'로 soft-delete

### 3. answer_logs (답변 로그 - 감사/재현용)

> AI 답변의 근거(evidence)를 저장하여 나중에 재현 가능하게 함

| 컬럼 | 타입 | 제약 | 설명 |
|------|------|------|------|
| `id` | UUID | PK | 로그 ID |
| `message_id` | UUID | FK → messages.id, ON DELETE SET NULL | 연결된 메시지 |
| `conversation_id` | UUID | FK → conversations.id, ON DELETE SET NULL | 대화 ID |
| `user_id` | UUID | FK → users.id, ON DELETE SET NULL | 사용자 ID |
| `question` | TEXT | NOT NULL | 원본 질문 |
| `answer` | TEXT | NOT NULL | AI 답변 |
| `search_query` | TEXT | nullable | 벡터 검색에 사용된 쿼리 |
| `search_filters` | JSONB | nullable | 검색 필터 (year, section 등) |
| `evidence` | JSONB | NOT NULL | 근거 목록 (아래 구조 참고) |
| `model` | VARCHAR(50) | nullable | 사용된 LLM |
| `prompt_tokens` | INTEGER | nullable | 프롬프트 토큰 |
| `completion_tokens` | INTEGER | nullable | 응답 토큰 |
| `total_tokens` | INTEGER | nullable | 총 토큰 |
| `search_latency_ms` | INTEGER | nullable | 검색 지연 시간 |
| `llm_latency_ms` | INTEGER | nullable | LLM 지연 시간 |
| `total_latency_ms` | INTEGER | nullable | 총 지연 시간 |
| `created_at` | TIMESTAMPTZ | DEFAULT NOW() | 생성일 |

**evidence 구조:**
```json
[
  {
    "paper_id": "pmid:12345678",
    "chunk_id": "pmid:12345678|results|0",
    "title": "Paper Title",
    "journal": "Nature Medicine",
    "year": 2025,
    "section": "results",
    "snippet": "Osimertinib showed 80%...",
    "offset_start": 12340,
    "offset_end": 13500,
    "text_version": "v1",
    "distance": 0.15
  }
]
```

**인덱스:**
- `idx_answer_logs_user_id` - 사용자별 조회
- `idx_answer_logs_conversation_id` - 대화별 조회
- `idx_answer_logs_created_at` - 시간순 정렬

### 4. lab_feedbacks (Admin 테스트 피드백)

> Admin RAG Lab에서 테스트 시 수집하는 피드백. 품질 개선을 위한 데이터 수집용.

| 컬럼 | 타입 | 제약 | 설명 |
|------|------|------|------|
| `id` | UUID | PK | 피드백 ID |
| `admin_user_id` | UUID | FK → admin_users.id, nullable | 테스트한 관리자 |
| `test_type` | VARCHAR(20) | NOT NULL | search, generate |
| `query` | TEXT | NOT NULL | 테스트 쿼리 |
| `rating` | VARCHAR(10) | NOT NULL | good, bad |
| `comment` | TEXT | nullable | 추가 코멘트 |
| `parameters` | JSONB | NOT NULL | 테스트 파라미터 (limit, alpha, useReranker 등) |
| `result_summary` | JSONB | nullable | 결과 요약 (top score, chunk count 등) |
| `search_latency_ms` | INTEGER | nullable | 검색 지연 시간 |
| `rerank_latency_ms` | INTEGER | nullable | Reranker 지연 시간 |
| `llm_latency_ms` | INTEGER | nullable | LLM 지연 시간 (generate only) |
| `created_at` | TIMESTAMPTZ | DEFAULT NOW() | 생성일 |

**parameters 구조:**
```json
{
  "limit": 10,
  "alpha": 0.7,
  "useReranker": true,
  "minRerankScore": null,
  "rerankerModel": "bge-reranker-v2-m3"
}
```

**result_summary 구조:**
```json
{
  "totalChunks": 10,
  "topScore": 0.85,
  "relevantCount": 7,
  "lowRelevanceCount": 3,
  "model": "gpt-4o-mini",
  "tokensUsed": { "prompt": 1500, "completion": 300 }
}
```

**인덱스:**
- `idx_lab_feedbacks_admin_user_id` - 관리자별 조회
- `idx_lab_feedbacks_test_type` - 테스트 유형별 통계
- `idx_lab_feedbacks_rating` - 평점별 통계
- `idx_lab_feedbacks_created_at` - 시간순 정렬

### 5. lab_test_logs (Admin 테스트 로그)

> Admin RAG Lab에서 수행한 모든 테스트 결과를 자동 저장. 품질 변화 추적 및 분석용.

| 컬럼 | 타입 | 제약 | 설명 |
|------|------|------|------|
| `id` | UUID | PK | 로그 ID |
| `admin_user_id` | UUID | FK → admin_users.id, nullable | 테스트한 관리자 |
| `test_type` | VARCHAR(20) | NOT NULL | search, generate, compare |
| `query` | TEXT | NOT NULL | 테스트 쿼리 |
| `parameters` | JSONB | NOT NULL | 테스트 파라미터 |
| `results` | JSONB | NOT NULL | 전체 검색 결과 (문서 목록, 점수 등) |
| `search_latency_ms` | INTEGER | nullable | 검색 지연 시간 |
| `rerank_latency_ms` | INTEGER | nullable | Reranker 지연 시간 |
| `llm_latency_ms` | INTEGER | nullable | LLM 지연 시간 |
| `total_latency_ms` | INTEGER | nullable | 총 지연 시간 |
| `created_at` | TIMESTAMPTZ | DEFAULT NOW() | 생성일 |

**results 구조 (search):**
```json
{
  "chunks": [
    {
      "paperId": "pmid:12345678",
      "paperTitle": "Paper Title",
      "sectionName": "results",
      "chunkIndex": 0,
      "content": "논문 내용...",
      "score": 0.7000,
      "rerankScore": 0.3203,
      "originalScore": 0.2673
    }
  ],
  "totalChunks": 10
}
```

**results 구조 (generate):**
```json
{
  "answer": "AI 답변 내용...",
  "references": [
    {
      "paperId": "pmid:12345678",
      "title": "Paper Title",
      "section": "results",
      "content": "참조 내용...",
      "score": 0.85
    }
  ],
  "model": "gpt-4o-mini",
  "tokensUsed": { "prompt": 1500, "completion": 300 }
}
```

**results 구조 (compare):**
```json
{
  "withReranker": { "chunks": [...], "totalChunks": 10, "rerankLatencyMs": 5000 },
  "withoutReranker": { "chunks": [...], "totalChunks": 10 }
}
```

**인덱스:**
- `idx_lab_test_logs_admin_user_id` - 관리자별 조회
- `idx_lab_test_logs_test_type` - 테스트 유형별 필터
- `idx_lab_test_logs_query` - 쿼리 검색 (text_pattern_ops)
- `idx_lab_test_logs_created_at` - 시간순 정렬

---

## 트리거

### update_conversation_stats

messages INSERT 시 conversations의 `message_count`, `last_message_at` 자동 갱신

```sql
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

---

## DDL

```sql
-- conversations
CREATE TABLE conversations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    paper_id UUID REFERENCES papers(id) ON DELETE SET NULL,
    conversation_type VARCHAR(20) DEFAULT 'global' NOT NULL,
    title VARCHAR(200),
    status VARCHAR(20) DEFAULT 'active',
    message_count INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    last_message_at TIMESTAMPTZ,

    CONSTRAINT chk_conversation_type CHECK (conversation_type IN ('global', 'paper'))
);

CREATE INDEX idx_conversations_user_id ON conversations(user_id);
CREATE INDEX idx_conversations_paper_id ON conversations(paper_id);
CREATE INDEX idx_conversations_type ON conversations(conversation_type);
CREATE INDEX idx_conversations_status ON conversations(status);
CREATE INDEX idx_conversations_updated_at ON conversations(updated_at);

-- messages
CREATE TABLE messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID REFERENCES conversations(id) ON DELETE CASCADE,
    role VARCHAR(20) NOT NULL,
    content TEXT NOT NULL,
    tokens_used INTEGER,
    model VARCHAR(50),
    latency_ms INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_messages_conversation_id ON messages(conversation_id);
CREATE INDEX idx_messages_created_at ON messages(created_at);

-- answer_logs
CREATE TABLE answer_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    message_id UUID REFERENCES messages(id) ON DELETE SET NULL,
    conversation_id UUID REFERENCES conversations(id) ON DELETE SET NULL,
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    question TEXT NOT NULL,
    answer TEXT NOT NULL,
    search_query TEXT,
    search_filters JSONB,
    evidence JSONB NOT NULL,
    model VARCHAR(50),
    prompt_tokens INTEGER,
    completion_tokens INTEGER,
    total_tokens INTEGER,
    search_latency_ms INTEGER,
    llm_latency_ms INTEGER,
    total_latency_ms INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_answer_logs_user_id ON answer_logs(user_id);
CREATE INDEX idx_answer_logs_conversation_id ON answer_logs(conversation_id);
CREATE INDEX idx_answer_logs_created_at ON answer_logs(created_at);

-- lab_feedbacks (Admin 테스트 피드백)
CREATE TABLE lab_feedbacks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    admin_user_id UUID REFERENCES admin_users(id) ON DELETE SET NULL,
    test_type VARCHAR(20) NOT NULL,
    query TEXT NOT NULL,
    rating VARCHAR(10) NOT NULL,
    comment TEXT,
    parameters JSONB NOT NULL,
    result_summary JSONB,
    search_latency_ms INTEGER,
    rerank_latency_ms INTEGER,
    llm_latency_ms INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW(),

    CONSTRAINT chk_test_type CHECK (test_type IN ('search', 'generate')),
    CONSTRAINT chk_rating CHECK (rating IN ('good', 'bad'))
);

CREATE INDEX idx_lab_feedbacks_admin_user_id ON lab_feedbacks(admin_user_id);
CREATE INDEX idx_lab_feedbacks_test_type ON lab_feedbacks(test_type);
CREATE INDEX idx_lab_feedbacks_rating ON lab_feedbacks(rating);
CREATE INDEX idx_lab_feedbacks_created_at ON lab_feedbacks(created_at);

-- lab_test_logs (Admin 테스트 로그)
CREATE TABLE lab_test_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    admin_user_id UUID REFERENCES admin_users(id) ON DELETE SET NULL,
    test_type VARCHAR(20) NOT NULL,
    query TEXT NOT NULL,
    parameters JSONB NOT NULL,
    results JSONB NOT NULL,
    search_latency_ms INTEGER,
    rerank_latency_ms INTEGER,
    llm_latency_ms INTEGER,
    total_latency_ms INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW(),

    CONSTRAINT chk_lab_test_logs_test_type CHECK (test_type IN ('search', 'generate', 'compare'))
);

CREATE INDEX idx_lab_test_logs_admin_user_id ON lab_test_logs(admin_user_id);
CREATE INDEX idx_lab_test_logs_test_type ON lab_test_logs(test_type);
CREATE INDEX idx_lab_test_logs_query ON lab_test_logs(query text_pattern_ops);
CREATE INDEX idx_lab_test_logs_created_at ON lab_test_logs(created_at);
```

---

## 참고

- [OAR-20 스키마 설계](../../../OAR-20/yts/docs/postgresql-스키마-설계-v2.5.md)
- [users.md](./users.md) - 사용자 테이블
- [papers.md](./papers.md) - 논문 테이블
