# 초기 적재 (Backfill) 배치 설계

> OAR-21: 배치 크롤러 스케줄러 구현

## 1. 개요

과거 전체 데이터를 한 번 채우는 배치 작업.

| 항목 | 내용 |
|------|------|
| 목적 | 과거 전체 데이터 수집 |
| 트리거 | 수동 실행, 새 검색 쿼리 추가 시 |
| 데이터량 | 대량 (1,000건 ~ 100,000건) |
| 특징 | 트래픽 크고 오래 걸림, rate limit에 민감 |
| 운영 | 낮은 우선순위, throttle 강하게, 체크포인트 필수 |

## 2. 결정 사항

### 2.1 검색 쿼리 관리

**결정: DB + 어드민**

- 처음부터 DB 기반으로 구현 (설정 파일 단계 생략)
- NestJS + NextJS 어드민에서 관리
- 배포 없이 쿼리 추가/수정/활성화 가능

### 2.2 기술 스택

| 구성요소 | 기술 |
|----------|------|
| 어드민 Backend | NestJS |
| 어드민 Frontend | NextJS |
| 배치 워커 | Python (기존 OAR-19 코드 활용) |
| DB | PostgreSQL |

## 3. 데이터베이스 스키마

### 3.1 search_queries (검색 쿼리 관리)

```sql
CREATE TABLE search_queries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- 쿼리 정보
    name VARCHAR(100) NOT NULL,
    query TEXT NOT NULL,
    description TEXT,

    -- 수집 설정
    is_active BOOLEAN DEFAULT true,
    priority INT DEFAULT 10,
    max_results INT,
    year_from INT,
    year_to INT,
    open_access_only BOOLEAN DEFAULT true,

    -- 통계 (집계용)
    total_collected INT DEFAULT 0,
    last_backfill_at TIMESTAMPTZ,

    -- 타임스탬프
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    created_by VARCHAR(100),
    updated_by VARCHAR(100)
);
```

### 3.2 batch_jobs (배치 작업 상태)

```sql
CREATE TABLE batch_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- 작업 식별
    job_type VARCHAR(20) NOT NULL,        -- backfill, incremental, repair
    query_id UUID REFERENCES search_queries(id),

    -- 우선순위 및 스케줄
    priority INT DEFAULT 10,
    scheduled_at TIMESTAMPTZ,

    -- 상태
    status VARCHAR(20) DEFAULT 'pending',  -- pending, queued, running, completed, failed, cancelled

    -- 진행률
    total_count INT,
    processed_count INT DEFAULT 0,
    success_count INT DEFAULT 0,
    failed_count INT DEFAULT 0,

    -- 체크포인트 (중단 재개)
    checkpoint JSONB,

    -- 워커 정보
    worker_id VARCHAR(100),
    locked_at TIMESTAMPTZ,

    -- 에러 정보
    last_error TEXT,
    error_count INT DEFAULT 0,

    -- 실행 시간
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    duration_ms INT,

    -- 타임스탬프
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_batch_jobs_status ON batch_jobs (status, priority, created_at);
CREATE INDEX idx_batch_jobs_type ON batch_jobs (job_type, status);
CREATE INDEX idx_batch_jobs_query ON batch_jobs (query_id, created_at);
```

### 3.3 batch_job_logs (배치 실행 로그)

```sql
CREATE TABLE batch_job_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id UUID REFERENCES batch_jobs(id) ON DELETE CASCADE,

    -- 로그 정보
    level VARCHAR(10) NOT NULL,            -- info, warn, error
    message TEXT NOT NULL,
    details JSONB,

    -- 타임스탬프
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_job_logs_job ON batch_job_logs (job_id, created_at);
CREATE INDEX idx_job_logs_level ON batch_job_logs (level, created_at);
```

### 3.4 batch_failed_items (실패 항목 추적)

```sql
CREATE TABLE batch_failed_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id UUID REFERENCES batch_jobs(id),

    -- 실패 항목 정보
    item_type VARCHAR(20) NOT NULL,        -- paper, query_page
    item_id VARCHAR(100),                  -- pmcid, doi 등

    -- 에러 정보
    error_code VARCHAR(20),                -- 429, 500, TIMEOUT, PARSE_ERROR
    error_message TEXT,

    -- 재시도
    retry_count INT DEFAULT 0,
    max_retries INT DEFAULT 3,
    next_retry_at TIMESTAMPTZ,

    -- 상태
    status VARCHAR(20) DEFAULT 'pending',  -- pending, retrying, resolved, abandoned
    resolved_at TIMESTAMPTZ,

    -- 타임스탬프
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_failed_items_status ON batch_failed_items (status, next_retry_at);
CREATE INDEX idx_failed_items_job ON batch_failed_items (job_id);
```

## 4. 어드민 UI

### 4.1 대시보드

```
┌─────────────────────────────────────────────────────────────────┐
│  배치 대시보드                                                    │
├─────────────────────────────────────────────────────────────────┤
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐           │
│  │ Running  │ │ Pending  │ │ Failed   │ │ Today    │           │
│  │    2     │ │    5     │ │    1     │ │  1,234   │           │
│  │  jobs    │ │  jobs    │ │  jobs    │ │ collected│           │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘           │
├─────────────────────────────────────────────────────────────────┤
│  실행 중인 작업                                                   │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │ [Backfill] lung cancer immunotherapy                      │  │
│  │ ████████████░░░░░░░░ 60% (600/1000)  ETA: 5분             │  │
│  │ Worker: worker-01  Started: 10:30                        │  │
│  └───────────────────────────────────────────────────────────┘  │
├─────────────────────────────────────────────────────────────────┤
│  검색 쿼리 관리                            [+ 쿼리 추가]          │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │ 이름          쿼리                상태    수집    마지막     ││
│  ├─────────────────────────────────────────────────────────────┤│
│  │ 폐암 면역     lung cancer...     ● 활성  1,234   2시간 전   ││
│  │ 유방암 BRCA   breast cancer...   ● 활성    892   1일 전     ││
│  │ 췌장암        pancreatic...      ○ 비활성  0     -          ││
│  └─────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────┘
```

### 4.2 어드민 기능

| 기능 | 설명 |
|------|------|
| 쿼리 목록 조회 | 상태, 수집 건수, 마지막 실행 시간 표시 |
| 쿼리 추가 | 이름, 쿼리, 연도 범위, 우선순위 설정 |
| 쿼리 수정 | 설정 변경 |
| 활성화/비활성화 | ON/OFF 토글 |
| 수동 실행 | 특정 쿼리 즉시 실행 |
| 진행 상태 확인 | 현재 수집 중인 쿼리 상태 |
| 로그 조회 | 배치 실행 로그 확인 |
| 실패 항목 관리 | 재시도, 포기 처리 |

## 5. 체크포인트 설계

### 5.1 핵심 원칙

| 단계 | 체크포인트 방식 | 이유 |
|------|----------------|------|
| **Search** | 페이지/커서 단위 | 페이지 재처리 비용 낮음, 중복은 downstream 흡수 |
| **Collect/Parse/Save** | 개별 논문(ID) 단위 | 한 건이 무겁고 비쌈, 페이지 재처리는 손해 |

> ⚠️ "체크포인트 JSON에 completed_pmcids 배열" 방식은 **100만 건에 부적합**
> - 배열 거대화 → 메모리/쓰기 비용 증가 → 재시작 로드/머지 비용 증가

### 5.2 Search 체크포인트 (batch_jobs.checkpoint)

```json
{
  "phase": "search",
  "query": "OPEN_ACCESS:Y AND lung cancer",
  "page_size": 1000,
  "cursor": "AoJ9...",           // 또는 current_page
  "total_results": 50000,
  "last_completed_at": "2025-12-29T03:00:00Z"
}
```

**저장 주기:** 매 페이지 완료 시

### 5.3 개별 논문 상태 관리 (article_jobs 테이블)

Search 결과로 나온 ID는 즉시 `article_jobs`에 upsert.
체크포인트 JSON에 개별 ID 저장하지 않음.

```sql
CREATE TABLE article_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    batch_job_id UUID REFERENCES batch_jobs(id),

    -- 논문 식별
    pmcid VARCHAR(20) NOT NULL,
    pmid VARCHAR(20),
    doi VARCHAR(100),

    -- 상태
    status VARCHAR(20) DEFAULT 'pending',
    -- pending → downloading → parsing → saving → completed / failed

    -- 재시도
    attempt_count INT DEFAULT 0,
    max_attempts INT DEFAULT 3,
    next_run_at TIMESTAMPTZ,

    -- 에러
    last_error_code VARCHAR(20),
    last_error TEXT,

    -- 타임스탬프
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE(batch_job_id, pmcid)
);

CREATE INDEX idx_article_jobs_status ON article_jobs (batch_job_id, status);
CREATE INDEX idx_article_jobs_retry ON article_jobs (status, next_run_at)
    WHERE status IN ('pending', 'failed');
```

### 5.4 상태 전이

```
┌─────────┐    ┌─────────────┐    ┌─────────┐    ┌────────┐    ┌───────────┐
│ pending │───►│ downloading │───►│ parsing │───►│ saving │───►│ completed │
└─────────┘    └─────────────┘    └─────────┘    └────────┘    └───────────┘
     │               │                 │              │
     │               ▼                 ▼              ▼
     │         ┌──────────┐      ┌──────────┐   ┌──────────┐
     └────────►│  failed  │◄─────│  failed  │◄──│  failed  │
               └──────────┘      └──────────┘   └──────────┘
                    │
                    ▼ (retry)
               ┌─────────┐
               │ pending │
               └─────────┘
```

### 5.5 저장 주기 정리

| 대상 | 저장 주기 | 비고 |
|------|----------|------|
| Search 체크포인트 | 매 페이지 | 빠르고, 재처리 비용 낮음 |
| 개별 논문 상태 | 상태 전이마다 | 복구/중단재개 용이 |
| 데이터 저장 (papers) | N건 배치 커밋 | 100~500건 단위 권장 |

### 5.6 재개 로직

```python
async def resume_backfill(job_id: str):
    job = await get_batch_job(job_id)

    # 1. Search 체크포인트에서 커서 복원
    cursor = job.checkpoint.get("cursor")

    # 2. 남은 페이지 검색 계속
    if cursor:
        await continue_search(job, cursor)

    # 3. pending/failed 상태인 article_jobs 처리
    pending_articles = await get_pending_articles(job_id)
    await process_articles(pending_articles)
```

## 6. 실행 방식

### 6.1 결정: Celery + Beat

**이유:**
- 핵심 로직이 Python (수집, 파싱, 저장)
- 어드민(NestJS)은 트리거만 담당
- BullMQ는 Node.js 워커 → Python 호출 복잡도 증가

### 6.2 아키텍처

```
┌─────────────────────────────────────────────────────────────┐
│  NextJS (어드민 UI)                                          │
│    └── 쿼리 관리, 배치 상태 조회, 수동 실행 버튼             │
└───────────────────────────┬─────────────────────────────────┘
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  NestJS API                                                  │
│    └── batch_jobs 테이블에 작업 생성 (status: pending)       │
└───────────────────────────┬─────────────────────────────────┘
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  PostgreSQL                                                  │
│    └── batch_jobs, article_jobs                              │
└───────────────────────────┬─────────────────────────────────┘
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  Redis                                                       │
│    └── Celery 메시지 브로커                                  │
└───────────────────────────┬─────────────────────────────────┘
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  Celery Worker (Python)                                      │
│    └── 기존 OAR-19 코드로 수집/파싱/저장                     │
│    └── article_jobs 상태 업데이트                            │
└─────────────────────────────────────────────────────────────┘
                            ▲
┌─────────────────────────────────────────────────────────────┐
│  Celery Beat                                                 │
│    └── 증분 수집: 매일 03:00                                 │
│    └── 보정 배치: 매주 일요일 02:00                          │
└─────────────────────────────────────────────────────────────┘
```

### 6.3 NestJS → Celery 연동

NestJS에서 Celery 작업 트리거 방법:

**옵션 A: Redis에 직접 메시지 발행**
```typescript
// NestJS
import Redis from 'ioredis';

async triggerBackfill(queryId: string) {
  const redis = new Redis();
  await redis.lpush('celery', JSON.stringify({
    task: 'batch.backfill',
    args: [queryId],
  }));
}
```

**옵션 B: Python API 서버 (FastAPI) 추가**
```
NestJS → FastAPI → Celery.send_task()
```

**권장: 옵션 A** (추가 서비스 없이 Redis만으로)

### 6.4 Celery 태스크 구조

```python
# batch/tasks.py
from celery import Celery

app = Celery('batch', broker='redis://localhost:6379/0')

@app.task(bind=True)
def backfill(self, query_id: str):
    """초기 적재 배치"""
    job = create_batch_job(query_id, job_type='backfill')
    try:
        run_backfill(job)
    except Exception as e:
        update_job_status(job.id, 'failed', error=str(e))
        raise

@app.task
def incremental():
    """증분 수집 배치 (매일)"""
    ...

@app.task
def repair():
    """보정 배치 (주 1회)"""
    ...
```

### 6.5 Celery Beat 스케줄

```python
# celery_config.py
from celery.schedules import crontab

app.conf.beat_schedule = {
    'incremental-daily': {
        'task': 'batch.incremental',
        'schedule': crontab(hour=3, minute=0),  # 매일 03:00
    },
    'repair-weekly': {
        'task': 'batch.repair',
        'schedule': crontab(hour=2, minute=0, day_of_week=0),  # 일요일 02:00
    },
}
```

## 7. 워커 구성

### 7.1 큐 분리 전략

배치 유형별로 Celery 큐를 분리하여 독립적으로 운영:

| 배치 | 큐 이름 | 워커 수 | concurrency | 동시 처리 | 이유 |
|------|---------|--------|-------------|----------|------|
| **초기 적재** | `backfill` | 3 | 35 | 105 | 빠르게 밀어넣기, 낮은 우선순위 |
| **증분 수집** | `incremental` | 1~2 | 10 | 10~20 | 안정적으로, 높은 우선순위 |
| **보정** | `repair` | 1 | 5 | 5 | 천천히, 낮은 빈도 |

### 7.2 태스크 큐 지정

```python
# batch/tasks.py

@app.task(queue='backfill')
def backfill(query_id: str):
    """초기 적재 배치"""
    ...

@app.task(queue='incremental')
def incremental():
    """증분 수집 배치 (매일)"""
    ...

@app.task(queue='repair')
def repair():
    """보정 배치 (주 1회)"""
    ...
```

### 7.3 워커 실행 명령

```bash
# 초기 적재 워커 (3개)
celery -A batch worker -Q backfill --concurrency=35 -n backfill1@%h
celery -A batch worker -Q backfill --concurrency=35 -n backfill2@%h
celery -A batch worker -Q backfill --concurrency=35 -n backfill3@%h

# 증분 수집 워커 (1개)
celery -A batch worker -Q incremental --concurrency=10 -n incremental1@%h

# 보정 워커 (1개)
celery -A batch worker -Q repair --concurrency=5 -n repair1@%h

# Beat 스케줄러
celery -A batch beat
```

### 7.4 Docker Compose 예시

```yaml
services:
  # 초기 적재 워커
  worker-backfill:
    image: batch-worker
    command: celery -A batch worker -Q backfill --concurrency=35
    deploy:
      replicas: 3

  # 증분 수집 워커
  worker-incremental:
    image: batch-worker
    command: celery -A batch worker -Q incremental --concurrency=10
    deploy:
      replicas: 1

  # 보정 워커
  worker-repair:
    image: batch-worker
    command: celery -A batch worker -Q repair --concurrency=5
    deploy:
      replicas: 1

  # 스케줄러
  beat:
    image: batch-worker
    command: celery -A batch beat
```

## 8. 수집 범위

### 8.1 기본값

| 설정 | 기본값 | 설명 |
|------|--------|------|
| `year_from` | NULL | 전체 (쿼리에서 제한 가능) |
| `year_to` | NULL | 전체 |
| `open_access_only` | **true** | OA만 수집 |
| `max_results` | NULL | 무제한 |

### 8.2 OA만 수집하는 이유

- fulltext XML 수집이 목적 → OA 아니면 못 가져옴
- 유료 논문은 메타데이터만 가능 → 복잡도 증가
- 나중에 필요하면 확장 가능

### 8.3 쿼리 예시

```python
# Europe PMC 검색 쿼리 생성
def build_query(search_query: SearchQuery) -> str:
    query = search_query.query

    # OA 필터 (항상)
    query += " AND OPEN_ACCESS:Y"

    # 연도 필터 (옵션)
    if search_query.year_from or search_query.year_to:
        year_from = search_query.year_from or 1900
        year_to = search_query.year_to or 2099
        query += f" AND FIRST_PDATE:[{year_from} TO {year_to}]"

    return query
```

## 9. 향후 계획

### 9.1 증분 수집 (Incremental) - 미설계

| 항목 | 예정 |
|------|------|
| 목적 | 신규 논문 + 업데이트 반영 |
| 주기 | 매일 1회 (03:00) |
| 워터마크 | 날짜 기반 (`FIRST_PDATE`) |
| 안전 윈도우 | -2일 overlap |

### 9.2 보정 (Reconciliation) - 미설계

| 항목 | 예정 |
|------|------|
| 목적 | DOI→PMID 매핑, 누락 복구 |
| 주기 | 주 1회 (일요일 02:00) |
| 대상 | 실패 항목, DOI-only 레코드 |

> 상세 설계는 초기 적재 구현 후 진행

## 10. 참고

- [api-collection-limitations.md](./api-collection-limitations.md) - API 수집 한계점 및 병렬 처리
- [OAR-22 batch-architecture-design_v2.md](../../OAR-22/yts/docs/batch-architecture-design_v2.md) - 배치 아키텍처 전체 설계
