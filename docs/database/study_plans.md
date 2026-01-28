# Study Plans 테이블 문서

> **Last Updated**: 2025-01-21
> **Version**: 1.0

---

## 개요

Study Plan Agent가 생성한 실험 설계 계획서를 저장하는 테이블입니다.
가설 입력부터 최종 실험 계획, 검증 결과, 승인 상태까지 전체 파이프라인 결과를 저장합니다.

---

## ERD

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                                study_plans                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│ PK  id                  UUID          gen_random_uuid()                      │
│ FK  user_id             UUID          → users.id (CASCADE)                   │
├─────────────────────────────────────────────────────────────────────────────┤
│     hypothesis_input              TEXT          NOT NULL                     │
│     research_context              TEXT          NULL                         │
│     preferred_experiment_types    VARCHAR(50)[] DEFAULT '{}'                 │
├─────────────────────────────────────────────────────────────────────────────┤
│     hypothesis_structured         JSONB         NULL                         │
│     hypothesis_confidence         FLOAT         NULL                         │
├─────────────────────────────────────────────────────────────────────────────┤
│     test_questions                JSONB         DEFAULT '[]'                 │
│     search_coverage_score         FLOAT         NULL                         │
│     prior_studies_count           INTEGER       DEFAULT 0                    │
├─────────────────────────────────────────────────────────────────────────────┤
│     evidence_packs                JSONB         DEFAULT '[]'                 │
│     experiment_designs            JSONB         DEFAULT '[]'                 │
│     experiment_count              INTEGER       DEFAULT 0                    │
├─────────────────────────────────────────────────────────────────────────────┤
│     quality_score                 FLOAT         NULL                         │
│     revision_count                INTEGER       DEFAULT 0                    │
│     measurements                  JSONB         DEFAULT '[]'                 │
│     feasibility_assessment        JSONB         NULL                         │
├─────────────────────────────────────────────────────────────────────────────┤
│     approval_required             BOOLEAN       DEFAULT FALSE                │
│     approval_status               VARCHAR(20)   DEFAULT 'approved'           │
├─────────────────────────────────────────────────────────────────────────────┤
│     final_plan                    TEXT          NULL                         │
│     executive_summary             TEXT          NULL                         │
│     references                    JSONB         DEFAULT '[]'                 │
├─────────────────────────────────────────────────────────────────────────────┤
│     status                        VARCHAR(20)   DEFAULT 'completed'          │
│     total_duration_ms             INTEGER       NULL                         │
│     error_message                 TEXT          NULL                         │
├─────────────────────────────────────────────────────────────────────────────┤
│     created_at                    TIMESTAMPTZ   DEFAULT NOW()                │
│     updated_at                    TIMESTAMPTZ   DEFAULT NOW() (trigger)      │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 컬럼 정의

### 기본 키 & 외래 키

| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|----------|------|
| `id` | UUID | PK, DEFAULT gen_random_uuid() | Study Plan 고유 ID |
| `user_id` | UUID | FK → users.id, NOT NULL, ON DELETE CASCADE | 생성자 ID |

### 입력 데이터

| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|----------|------|
| `hypothesis_input` | TEXT | NOT NULL | 사용자가 입력한 원본 가설 |
| `research_context` | TEXT | NULL | 연구 맥락/배경 정보 |
| `preferred_experiment_types` | VARCHAR(50)[] | DEFAULT '{}' | 선호 실험 유형 (in_vitro, in_vivo 등) |

### 가설 파싱 결과

| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|----------|------|
| `hypothesis_structured` | JSONB | NULL | 구조화된 가설 정보 |
| `hypothesis_confidence` | FLOAT | NULL | 가설 파싱 신뢰도 (0~1) |

**hypothesis_structured 예시:**
```json
{
  "independent_variable": "MET amplification",
  "dependent_variable": "osimertinib resistance",
  "subject": "EGFR T790M mutation patients",
  "keywords": ["EGFR", "T790M", "osimertinib", "MET", "resistance"]
}
```

### 검증 질문 & 검색 결과

| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|----------|------|
| `test_questions` | JSONB | DEFAULT '[]' | 가설 검증을 위한 질문 목록 |
| `search_coverage_score` | FLOAT | NULL | 검색 커버리지 점수 (0~1) |
| `prior_studies_count` | INTEGER | DEFAULT 0 | 검색된 선행 연구 수 |

**test_questions 예시:**
```json
[
  {
    "category": "mechanism",
    "question": "MET amplification이 osimertinib의 타겟 억제를 어떻게 우회하는가?",
    "priority": 1,
    "decision_rule": "If MET bypass confirmed, proceed to in vivo"
  }
]
```

### Evidence Pack & 실험 설계

| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|----------|------|
| `evidence_packs` | JSONB | DEFAULT '[]' | 검증 질문별 Evidence Pack |
| `experiment_designs` | JSONB | DEFAULT '[]' | 설계된 실험 목록 |
| `experiment_count` | INTEGER | DEFAULT 0 | 총 실험 수 |

**experiment_designs 예시:**
```json
[
  {
    "experiment_id": "exp_001",
    "experiment_type": "in_vitro",
    "title": "Cell viability assay with MET inhibitor combination",
    "test_category": "mechanism",
    "rationale": "Based on prior study PMID:12345678",
    "estimated_timeline": "4 weeks",
    "estimated_cost_level": "medium"
  }
]
```

### Critique & 측정 항목

| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|----------|------|
| `quality_score` | FLOAT | NULL | Critic 평가 품질 점수 (0~1) |
| `revision_count` | INTEGER | DEFAULT 0 | 자기검증 수정 횟수 |
| `measurements` | JSONB | DEFAULT '[]' | 식별된 측정 항목 |
| `feasibility_assessment` | JSONB | NULL | 실현가능성 평가 |

### 승인 게이트

| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|----------|------|
| `approval_required` | BOOLEAN | DEFAULT FALSE | 승인 필요 여부 |
| `approval_status` | VARCHAR(20) | DEFAULT 'approved' | 승인 상태 (pending, approved, rejected) |

### 최종 결과

| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|----------|------|
| `final_plan` | TEXT | NULL | 최종 실험 계획서 (마크다운) |
| `executive_summary` | TEXT | NULL | 경영진 요약 |
| `references` | JSONB | DEFAULT '[]' | 참조 문헌 목록 |

### 메타데이터

| 컬럼 | 타입 | 제약조건 | 설명 |
|------|------|----------|------|
| `status` | VARCHAR(20) | DEFAULT 'completed' | 처리 상태 (completed, error) |
| `total_duration_ms` | INTEGER | NULL | 총 처리 시간 (ms) |
| `error_message` | TEXT | NULL | 오류 발생 시 메시지 |
| `created_at` | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | 생성 시각 |
| `updated_at` | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | 수정 시각 (트리거) |

---

## 인덱스

| 인덱스명 | 컬럼 | 타입 | 용도 |
|----------|------|------|------|
| `idx_study_plans_user_id` | user_id | BTREE | 사용자별 조회 |
| `idx_study_plans_status` | status | BTREE | 상태별 필터링 |
| `idx_study_plans_created_at` | created_at | BTREE | 최신순 정렬 |

---

## DDL

```sql
-- study_plans 테이블 생성
CREATE TABLE study_plans (
    -- Primary Key
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Foreign Key
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,

    -- 입력
    hypothesis_input TEXT NOT NULL,
    research_context TEXT,
    preferred_experiment_types VARCHAR(50)[] NOT NULL DEFAULT '{}',

    -- 파싱된 가설
    hypothesis_structured JSONB,
    hypothesis_confidence FLOAT,

    -- 검증 질문
    test_questions JSONB NOT NULL DEFAULT '[]',

    -- 검색 결과
    search_coverage_score FLOAT,
    prior_studies_count INTEGER NOT NULL DEFAULT 0,

    -- Evidence Pack
    evidence_packs JSONB NOT NULL DEFAULT '[]',

    -- 실험 설계
    experiment_designs JSONB NOT NULL DEFAULT '[]',
    experiment_count INTEGER NOT NULL DEFAULT 0,

    -- Critique
    quality_score FLOAT,
    revision_count INTEGER NOT NULL DEFAULT 0,

    -- 측정 항목
    measurements JSONB NOT NULL DEFAULT '[]',

    -- 실현가능성
    feasibility_assessment JSONB,

    -- 승인 게이트
    approval_required BOOLEAN NOT NULL DEFAULT FALSE,
    approval_status VARCHAR(20) NOT NULL DEFAULT 'approved',

    -- 최종 결과
    final_plan TEXT,
    executive_summary TEXT,
    references JSONB NOT NULL DEFAULT '[]',

    -- 메타데이터
    status VARCHAR(20) NOT NULL DEFAULT 'completed',
    total_duration_ms INTEGER,
    error_message TEXT,

    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 인덱스
CREATE INDEX idx_study_plans_user_id ON study_plans(user_id);
CREATE INDEX idx_study_plans_status ON study_plans(status);
CREATE INDEX idx_study_plans_created_at ON study_plans(created_at);

-- updated_at 자동 갱신 트리거
CREATE OR REPLACE FUNCTION update_study_plans_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER trigger_update_study_plans_updated_at
    BEFORE UPDATE ON study_plans
    FOR EACH ROW
    EXECUTE FUNCTION update_study_plans_updated_at();
```

---

## 마이그레이션

- **파일**: `backend/alembic/versions/009_add_study_plans.py`
- **Revision ID**: `009_add_study_plans`
- **Revises**: `a5e42c02caf8_add_paper_summaries_table`

---

## API 엔드포인트

| Method | Endpoint | 설명 |
|--------|----------|------|
| POST | `/study-plan/generate` | Study Plan 생성 (SSE 스트리밍) |
| POST | `/study-plan/generate-sync` | Study Plan 생성 (동기) |
| POST | `/study-plan/save` | Study Plan 저장 |
| GET | `/study-plan/history` | 히스토리 목록 (페이지네이션) |
| GET | `/study-plan/{plan_id}` | 상세 조회 |
| DELETE | `/study-plan/{plan_id}` | 삭제 |

---

## 참고

- **모델 파일**: `backend/app/models/study_plan.py`
- **스키마 파일**: `backend/app/schemas/study_plan.py`
- **라우터 파일**: `backend/app/routers/study_plan.py`
- **설계 문서**: `docs/backend/study-plan-agent.md`
