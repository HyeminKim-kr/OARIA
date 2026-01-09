# Job Management System 설계

> **Last Updated**: 2026-01-08
> **Status**: Draft

---

## 1. 현재 구조의 문제점

### 1.1 Fire-and-Forget 방식

```
현재:
Admin → API → DB Insert → Celery.delay() → [끝]
                                    ↓
                            워커 재시작 시 작업 손실
```

- Celery 태스크가 한 번 호출되면 추적 불가
- 워커가 죽으면 진행 중인 작업 손실
- "processing" 상태에서 stuck되면 수동 개입 필요
- 재시작 메커니즘 없음

### 1.2 상태 관리 부재

- DB에만 상태 저장 (느림, 폴링 필요)
- 작업 진행률 실시간 확인 불가
- 중복 실행 방지 메커니즘 없음

---

## 2. 새로운 아키텍처

### 2.1 상태 머신

```
┌─────────┐    create    ┌─────────┐    enqueue   ┌─────────┐
│ PENDING │─────────────→│ QUEUED  │─────────────→│PROCESSING│
└─────────┘              └─────────┘              └────┬─────┘
                              ↑                        │
                              │         ┌─────────────┴─────────────┐
                              │         ↓                           ↓
                         (retry)   ┌─────────┐              ┌─────────┐
                              └────│ FAILED  │              │COMPLETED│
                                   └─────────┘              └─────────┘
```

**상태 정의:**

| 상태 | 설명 | 전이 가능 상태 |
|------|------|---------------|
| `pending` | 생성됨, 아직 큐에 안 들어감 | queued |
| `queued` | Redis 큐에 들어감, 대기 중 | processing |
| `processing` | 워커가 처리 중 | completed, failed |
| `completed` | 성공적으로 완료 | - |
| `failed` | 실패 (재시도 가능) | queued (retry) |

### 2.2 Redis 활용

```
Redis
├── job:embed:{id}:state     # 작업 상태 (Hash)
│   ├── status: "processing"
│   ├── progress: 15
│   ├── total: 35
│   ├── worker_id: "celery@xxx"
│   ├── started_at: "2026-01-08T..."
│   └── heartbeat: "2026-01-08T..."  # 워커 생존 확인용
│
├── job:embed:{id}:lock      # 분산 락 (중복 실행 방지)
│
└── queue:embed:pending      # 대기 중인 작업 ID 리스트
```

### 2.3 작업 흐름

```
1. 작업 생성 (Admin API)
   ├── DB: sample_embeddings INSERT (status=pending)
   ├── Redis: job:embed:{id}:state HSET
   └── Redis: queue:embed:pending RPUSH {id}

2. Celery Beat (10초마다)
   ├── queue:embed:pending에서 작업 ID 확인
   ├── 각 ID에 대해 락 획득 시도
   └── 락 획득 성공 시 Celery 태스크 dispatch

3. Celery Worker
   ├── 락 확인 (이미 다른 워커가 처리 중이면 스킵)
   ├── 상태 업데이트 (processing)
   ├── Heartbeat 주기적 갱신 (30초마다)
   ├── 진행률 Redis에 실시간 업데이트
   └── 완료/실패 시 DB + Redis 동기화

4. Stuck 작업 감지 (Celery Beat, 1분마다)
   ├── processing 상태인데 heartbeat가 2분 이상 된 작업 감지
   ├── 해당 작업을 failed로 전환
   └── 재시도 횟수 < 3이면 자동 재큐잉
```

---

## 3. 구현 상세

### 3.1 Redis Job State Manager

```python
# batch/src/job_manager.py

class JobStateManager:
    """Redis 기반 작업 상태 관리"""

    HEARTBEAT_INTERVAL = 30  # 초
    HEARTBEAT_TIMEOUT = 120  # 초 (이 시간 지나면 stuck으로 간주)
    MAX_RETRIES = 3

    def __init__(self, redis_client):
        self.redis = redis_client

    def create_job(self, job_id: str, job_type: str, metadata: dict) -> None:
        """작업 생성 및 큐에 추가"""
        key = f"job:{job_type}:{job_id}:state"
        self.redis.hset(key, mapping={
            "status": "queued",
            "progress": 0,
            "total": 0,
            "retry_count": 0,
            "created_at": datetime.now(UTC).isoformat(),
            **metadata,
        })
        self.redis.rpush(f"queue:{job_type}:pending", job_id)

    def acquire_lock(self, job_id: str, job_type: str, worker_id: str) -> bool:
        """분산 락 획득 (NX = 없을 때만 설정)"""
        lock_key = f"job:{job_type}:{job_id}:lock"
        return self.redis.set(lock_key, worker_id, nx=True, ex=300)

    def update_progress(self, job_id: str, job_type: str, progress: int, total: int) -> None:
        """진행률 업데이트 + Heartbeat 갱신"""
        key = f"job:{job_type}:{job_id}:state"
        self.redis.hset(key, mapping={
            "progress": progress,
            "total": total,
            "heartbeat": datetime.now(UTC).isoformat(),
        })

    def complete_job(self, job_id: str, job_type: str, result: dict) -> None:
        """작업 완료 처리"""
        key = f"job:{job_type}:{job_id}:state"
        self.redis.hset(key, mapping={
            "status": "completed",
            "completed_at": datetime.now(UTC).isoformat(),
            **result,
        })
        self.redis.delete(f"job:{job_type}:{job_id}:lock")

    def fail_job(self, job_id: str, job_type: str, error: str) -> None:
        """작업 실패 처리"""
        key = f"job:{job_type}:{job_id}:state"
        state = self.redis.hgetall(key)
        retry_count = int(state.get("retry_count", 0))

        self.redis.hset(key, mapping={
            "status": "failed",
            "error": error,
            "retry_count": retry_count + 1,
            "failed_at": datetime.now(UTC).isoformat(),
        })
        self.redis.delete(f"job:{job_type}:{job_id}:lock")

    def get_stuck_jobs(self, job_type: str) -> list[str]:
        """Stuck 작업 감지 (heartbeat 타임아웃)"""
        # processing 상태이면서 heartbeat가 오래된 작업 찾기
        ...

    def retry_job(self, job_id: str, job_type: str) -> bool:
        """작업 재시도 (실패 또는 stuck 상태에서)"""
        key = f"job:{job_type}:{job_id}:state"
        state = self.redis.hgetall(key)

        if int(state.get("retry_count", 0)) >= self.MAX_RETRIES:
            return False

        self.redis.hset(key, "status", "queued")
        self.redis.rpush(f"queue:{job_type}:pending", job_id)
        return True
```

### 3.2 Celery Beat 스케줄

```python
# batch/src/celery_app.py

app.conf.beat_schedule = {
    # 대기 중인 작업 dispatch (10초마다)
    "dispatch-pending-jobs": {
        "task": "src.tasks.job_dispatcher.dispatch_pending_jobs",
        "schedule": 10.0,
    },
    # Stuck 작업 감지 및 복구 (1분마다)
    "recover-stuck-jobs": {
        "task": "src.tasks.job_dispatcher.recover_stuck_jobs",
        "schedule": 60.0,
    },
}
```

### 3.3 Job Dispatcher Task

```python
# batch/src/tasks/job_dispatcher.py

@app.task
def dispatch_pending_jobs():
    """대기 중인 작업을 워커에게 할당"""
    manager = get_job_manager()

    # embed 큐 처리
    while True:
        job_id = manager.redis.lpop("queue:embed:pending")
        if not job_id:
            break

        # 락 획득 시도
        if manager.acquire_lock(job_id, "embed", get_worker_id()):
            # 실제 작업 태스크 호출
            run_sample_embed.delay(job_id)

@app.task
def recover_stuck_jobs():
    """Stuck 작업 감지 및 복구"""
    manager = get_job_manager()

    stuck_jobs = manager.get_stuck_jobs("embed")
    for job_id in stuck_jobs:
        logger.warning("stuck_job_detected", job_id=job_id)
        manager.fail_job(job_id, "embed", "Worker timeout (stuck)")

        # 자동 재시도
        if manager.retry_job(job_id, "embed"):
            logger.info("job_auto_retried", job_id=job_id)
```

---

## 4. Admin API 변경

### 4.1 새 엔드포인트

```
# 작업 재시도
POST /sample-embeddings/{id}/retry
→ JobStateManager.retry_job()
→ 200 OK or 400 (max retries exceeded)

# 작업 취소
POST /sample-embeddings/{id}/cancel
→ status를 cancelled로 변경
→ 락 해제

# 실시간 상태 조회 (Redis에서)
GET /sample-embeddings/{id}/status
→ Redis에서 직접 조회 (빠름)
→ { status, progress, total, heartbeat, ... }
```

### 4.2 기존 API 수정

```
# 작업 생성 시
POST /sample-embeddings
→ DB INSERT
→ JobStateManager.create_job()  # Redis에도 등록
```

---

## 5. Admin UI 변경

### 5.1 작업 카드 개선

```
┌─────────────────────────────────────────────────────────────┐
│ fixed_char_1000_200 + openai_3small          [Processing]  │
│                                                             │
│ Progress: ████████████░░░░░░░░ 15/35 papers (42%)          │
│ Chunks: 1,234                                               │
│ Started: 2 minutes ago                                      │
│                                                             │
│                              [Cancel]  [View Logs]          │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ semantic_section_700t + openai_3large        [Failed]      │
│                                                             │
│ Error: OpenAI rate limit exceeded                          │
│ Retry: 1/3                                                  │
│                                                             │
│                              [Retry]  [Delete]              │
└─────────────────────────────────────────────────────────────┘
```

### 5.2 실시간 업데이트

- 5초마다 `/status` API 폴링
- 또는 Server-Sent Events (SSE) 사용

---

## 6. 마이그레이션 계획

### Phase 1: 기반 구축
1. `JobStateManager` 클래스 구현
2. Celery Beat 스케줄 추가
3. `job_dispatcher` 태스크 구현

### Phase 2: 기존 코드 통합
1. `run_sample_embed` 태스크 수정 (JobStateManager 사용)
2. Admin API 수정
3. DB 스키마 변경 (retry_count 컬럼 추가)

### Phase 3: Admin UI
1. Retry/Cancel 버튼 추가
2. 실시간 진행률 표시
3. 에러 메시지 표시 개선

---

## 7. 고려사항

### 7.1 Redis 장애 시

- DB를 source of truth로 유지
- Redis 복구 후 DB에서 상태 동기화

### 7.2 확장성

- 여러 워커가 동시에 다른 작업 처리 가능
- 분산 락으로 동일 작업 중복 실행 방지

### 7.3 모니터링

- Flower에서 태스크 상태 확인
- Redis에서 실시간 진행률 확인
- 로그에 structured logging 유지
