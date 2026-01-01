# Chat / RAG 테이블

> **Last Updated**: 2026-01-01
>
> **Owner**: Alembic (Backend)

---

## 개요

챗봇 기능을 위한 대화 관련 테이블입니다.

```
users ──1:N──▶ conversations ──1:N──▶ messages
                     │
                     └──1:N──▶ answer_logs (감사/재현용)
```

---

## 테이블

### 1. conversations (대화 세션)

| 컬럼 | 타입 | 제약 | 설명 |
|------|------|------|------|
| `id` | UUID | PK | 대화 ID |
| `user_id` | UUID | FK → users.id | 사용자 ID |
| `title` | VARCHAR(200) | nullable | 대화 제목 (자동 생성 또는 사용자 입력) |
| `status` | VARCHAR(20) | DEFAULT 'active' | active, archived, deleted |
| `message_count` | INTEGER | DEFAULT 0 | 메시지 수 (트리거 자동 갱신) |
| `created_at` | TIMESTAMPTZ | DEFAULT NOW() | 생성일 |
| `updated_at` | TIMESTAMPTZ | DEFAULT NOW() | 수정일 |
| `last_message_at` | TIMESTAMPTZ | nullable | 마지막 메시지 시간 (트리거 자동 갱신) |

**인덱스:**
- `idx_conversations_user_id` - 사용자별 대화 목록
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
    title VARCHAR(200),
    status VARCHAR(20) DEFAULT 'active',
    message_count INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    last_message_at TIMESTAMPTZ
);

CREATE INDEX idx_conversations_user_id ON conversations(user_id);
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
```

---

## 참고

- [OAR-20 스키마 설계](../../../OAR-20/yts/docs/postgresql-스키마-설계-v2.5.md)
- [users.md](./users.md) - 사용자 테이블
- [papers.md](./papers.md) - 논문 테이블
