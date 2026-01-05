# Admin 모니터링 및 제어 설계

> **상태**: 계획 수립
> **작성일**: 2025-12-31
> **관련**: Admin Backend/Frontend, Celery Beat

---

## 1. 현재 상태

### 구현 완료
- Dashboard: 수집/임베딩 통계 조회
- Papers: 개별 논문 임베딩 트리거
- Collection Jobs: 수집 작업 상태 조회/제어

### 미구현 (이 문서 범위)
- Celery Beat 스케줄 모니터링/제어
- 임베딩 Job 이력 관리

### 현재 모니터링 방법
```
┌─────────────────┐     ┌─────────────────┐
│  Admin Frontend │     │     Flower      │
│   (Dashboard)   │     │   (:15555)      │
│                 │     │                 │
│  - 수집 통계     │     │  - Task 상태    │
│  - 임베딩 통계   │     │  - Worker 상태  │
│  - Job 목록     │     │  - Beat 스케줄  │
└─────────────────┘     └─────────────────┘
        ↓                       ↓
    PostgreSQL              Celery/Redis
```

**문제점**: Flower는 개발용 도구, Admin에 통합 필요

---

## 2. 목표 구조

### 2.1 통합 모니터링 대시보드

```
┌─────────────────────────────────────────────────────────────┐
│                    Admin Dashboard                           │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐          │
│  │   수집 현황  │  │  임베딩 현황 │  │  스케줄 현황 │          │
│  │  Collection │  │  Embedding  │  │   Schedule  │          │
│  └─────────────┘  └─────────────┘  └─────────────┘          │
│                                                              │
│  ┌─────────────────────────────────────────────────────────┐│
│  │                    실시간 Job 현황                        ││
│  │  Running: 2  │  Pending: 5  │  Failed: 1  │  Today: 120  ││
│  └─────────────────────────────────────────────────────────┘│
│                                                              │
│  ┌─────────────────────────────────────────────────────────┐│
│  │                    Beat 스케줄 제어                       ││
│  │  embed-hourly    │ 매시 정각 │ Active  │ [Pause] [Run]  ││
│  │  reembed-daily   │ 매일 03시 │ Active  │ [Pause] [Run]  ││
│  └─────────────────────────────────────────────────────────┘│
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 주요 기능

| 기능 | 설명 | 우선순위 |
|------|------|----------|
| 스케줄 조회 | Beat 스케줄 목록 및 상태 | P0 |
| 스케줄 제어 | 일시정지/재개 | P1 |
| 수동 트리거 | 스케줄 즉시 실행 | P0 |
| Job 이력 | 임베딩 Job 이력 조회 | P1 |
| 실시간 현황 | 현재 실행 중인 태스크 | P2 |

---

## 3. 데이터 모델

### 3.1 embedding_jobs 테이블 (신규)

현재 `papers.embedding_status`로만 관리 → 별도 Job 테이블로 이력 관리

```sql
CREATE TABLE embedding_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Job 식별
    job_type VARCHAR(50) NOT NULL,  -- 'embed', 'reembed', 'embed_single'
    trigger_type VARCHAR(50) NOT NULL,  -- 'manual', 'schedule', 'chain'

    -- 범위
    query_id UUID REFERENCES search_queries(id),
    paper_id UUID REFERENCES papers(id),  -- embed_single인 경우

    -- 상태
    status VARCHAR(50) NOT NULL DEFAULT 'pending',
    -- pending → running → completed/failed/partial

    -- 진행률
    total_count INTEGER DEFAULT 0,
    processed_count INTEGER DEFAULT 0,
    success_count INTEGER DEFAULT 0,
    failed_count INTEGER DEFAULT 0,

    -- 시간
    created_at TIMESTAMPTZ DEFAULT NOW(),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,

    -- 메타
    celery_task_id VARCHAR(255),
    error_message TEXT,

    CONSTRAINT valid_status CHECK (
        status IN ('pending', 'running', 'completed', 'failed', 'partial', 'cancelled')
    )
);

CREATE INDEX idx_embedding_jobs_status ON embedding_jobs(status);
CREATE INDEX idx_embedding_jobs_created ON embedding_jobs(created_at DESC);
```

### 3.2 schedule_configs 테이블 (선택)

Beat 스케줄 제어를 위한 설정 테이블 (DB 기반 스케줄 제어 시)

```sql
CREATE TABLE schedule_configs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    schedule_name VARCHAR(100) UNIQUE NOT NULL,
    task_name VARCHAR(255) NOT NULL,

    -- 스케줄
    cron_expression VARCHAR(100),  -- '0 * * * *' (매시 정각)

    -- 제어
    is_enabled BOOLEAN DEFAULT true,

    -- 메타
    last_run_at TIMESTAMPTZ,
    next_run_at TIMESTAMPTZ,

    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

---

## 4. API 설계

### 4.1 Embedding Jobs

| Method | Endpoint | 설명 |
|--------|----------|------|
| GET | `/embedding-jobs` | Job 목록 (필터/페이징) |
| GET | `/embedding-jobs/:id` | Job 상세 |
| GET | `/embedding-jobs/stats` | 통계 (오늘/이번주/전체) |
| POST | `/embedding-jobs/trigger` | 임베딩 Job 생성 |
| POST | `/embedding-jobs/:id/cancel` | Job 취소 |

**GET /embedding-jobs 응답 예시:**
```json
{
  "data": [
    {
      "id": "uuid",
      "job_type": "embed",
      "trigger_type": "schedule",
      "status": "completed",
      "total_count": 50,
      "success_count": 48,
      "failed_count": 2,
      "created_at": "2025-12-31T10:00:00Z",
      "completed_at": "2025-12-31T10:05:30Z"
    }
  ],
  "pagination": { "total": 120, "page": 1, "limit": 20 }
}
```

### 4.2 Schedule Control

| Method | Endpoint | 설명 |
|--------|----------|------|
| GET | `/schedules` | 스케줄 목록 |
| GET | `/schedules/:name` | 스케줄 상세 |
| POST | `/schedules/:name/pause` | 일시정지 |
| POST | `/schedules/:name/resume` | 재개 |
| POST | `/schedules/:name/run` | 즉시 실행 |

**GET /schedules 응답 예시:**
```json
{
  "data": [
    {
      "name": "embed-hourly",
      "task": "src.tasks.embed.run_embed",
      "schedule": "0 * * * *",
      "is_enabled": true,
      "last_run_at": "2025-12-31T10:00:00Z",
      "next_run_at": "2025-12-31T11:00:00Z"
    },
    {
      "name": "reembed-daily",
      "task": "src.tasks.embed.run_reembed",
      "schedule": "0 3 * * *",
      "is_enabled": true,
      "last_run_at": "2025-12-31T03:00:00Z",
      "next_run_at": "2026-01-01T03:00:00Z"
    }
  ]
}
```

---

## 5. 구현 계획

### Phase 1: embedding_jobs 테이블 + 기본 API (P0)

**Backend 작업:**
- [ ] `embedding_jobs` 테이블 마이그레이션
- [ ] `EmbeddingJobsService` 구현
- [ ] `EmbeddingJobsController` 구현
- [ ] 기존 임베딩 트리거 시 Job 레코드 생성

**Batch 작업:**
- [ ] `run_embed` 태스크에서 Job 상태 업데이트
- [ ] 시작 시: `status = 'running'`, `started_at = NOW()`
- [ ] 완료 시: `status = 'completed'`, counts 업데이트

**Frontend 작업:**
- [ ] Embedding Jobs 목록 페이지
- [ ] Job 상세 모달

### Phase 2: 스케줄 조회 + 수동 트리거 (P0)

**Backend 작업:**
- [ ] `/schedules` 엔드포인트 (정적 목록 반환)
- [ ] `/schedules/:name/run` 수동 트리거

**Frontend 작업:**
- [ ] Dashboard에 스케줄 카드 추가
- [ ] "Run Now" 버튼

### Phase 3: 스케줄 제어 (P1)

**선택지:**
1. **Redis 기반**: Celery Beat의 `RedBeatSchedulerEntry` 활용
2. **DB 기반**: `schedule_configs` 테이블 + Custom Scheduler
3. **File 기반**: `celerybeat-schedule` 파일 직접 수정

**권장: Redis 기반 (RedBeat)**
```python
# Celery 설정
app.conf.beat_scheduler = 'redbeat.RedBeatScheduler'
app.conf.redbeat_redis_url = 'redis://localhost:6379/0'
```

- [ ] RedBeat 설치 및 설정
- [ ] 스케줄 pause/resume API 구현
- [ ] Frontend 제어 UI

### Phase 4: 실시간 현황 (P2)

- [ ] WebSocket 또는 Polling 기반 실시간 업데이트
- [ ] 현재 실행 중인 태스크 목록 (Celery Inspect)

---

## 6. 체크리스트

### Phase 1 (MVP)
- [ ] DB 마이그레이션: `embedding_jobs`
- [ ] Admin Backend: EmbeddingJobs CRUD
- [ ] Batch: embed 태스크에서 Job 상태 업데이트
- [ ] Admin Frontend: Jobs 목록/상세

### Phase 2
- [ ] Admin Backend: `/schedules` 엔드포인트
- [ ] Admin Backend: `/schedules/:name/run` 수동 트리거
- [ ] Admin Frontend: 스케줄 카드 + Run Now

### Phase 3
- [ ] Batch: RedBeat 설정
- [ ] Admin Backend: pause/resume API
- [ ] Admin Frontend: 스케줄 제어 UI

---

## 7. 참고

### 관련 파일
- `admin/backend/src/modules/papers/` - 기존 임베딩 트리거
- `batch/src/tasks/embed.py` - 임베딩 태스크
- `batch/src/celery_app.py` - Beat 스케줄 정의

### 관련 문서
- `docs/admin/architecture.md` - 전체 아키텍처
- `docs/admin/embedding-pipeline.md` - 체이닝 설계
- `docs/database/batch.md` - Batch 테이블 스키마
