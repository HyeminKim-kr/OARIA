# 배치 아키텍처 설계: 수집 파이프라인 분리

> **OAR-22**: Rate Limit 처리 및 재시도 로직 구현 - 부속 문서
>
> **작성일**: 2025-12-28

---

## 1. 배치 분리 필요성

### 1.1 핵심 문제

| 배치 유형 | 문제 영역 | SLA |
|----------|----------|-----|
| 초기 적재 | **양(Volume)** | 완료되면 됨 |
| 증분 수집 | **신선도(Freshness)** | 매일 최신 반영 필수 |

**분리하지 않으면:**
```
초기 적재 (10,000건 수집 중)
    └── rate limit 또는 느린 처리
         └── 증분 수집 밀림
              └── 최신 데이터 반영 지연 (SLA 위반)
```

### 1.2 분리 원칙

> 초기 적재가 증분 수집을 **절대 블로킹하면 안 됨**

---

## 2. 배치 유형 정의

### 2.1 A. 초기 적재 (Backfill / Full Load)

| 항목 | 내용 |
|------|------|
| **목적** | 과거 전체 데이터를 한 번 채우기 |
| **트리거** | 수동 실행, 새 검색 쿼리 추가 시 |
| **데이터량** | 대량 (1,000건 ~ 100,000건) |
| **특징** | 트래픽 크고 오래 걸림, rate limit에 민감 |
| **운영** | 낮은 우선순위, throttle 강하게, 체크포인트 필수 |

```
[초기 적재 흐름]
    │
    ├── 검색 쿼리: "breast cancer AND immunotherapy"
    │
    ├── Search API → 전체 논문 목록 수집
    │      └── 페이지네이션 (pageSize=1000)
    │
    ├── 체크포인트 저장 (중단 시 재개 가능)
    │      └── checkpoint.json: {last_page: 5, last_pmcid: "PMC12345"}
    │
    ├── Fulltext XML 수집
    │      └── rate_limit_delay: 0.1s (또는 더 느리게)
    │      └── 실패 시: failed_requests.json 저장
    │
    └── 파싱 및 저장
```

**체크포인트 필수 이유:**
- 10,000건 수집 중 5,000건에서 중단되면?
- 체크포인트 없으면 처음부터 다시 시작 → 비효율

### 2.2 B. 증분 수집 (Incremental / Daily Ingest)

| 항목 | 내용 |
|------|------|
| **목적** | 신규 논문 + 최신 업데이트 빠르게 반영 |
| **트리거** | 정기 스케줄 (매일, 또는 6~12시간마다) |
| **데이터량** | 소량 (일일 수십~수백 건) |
| **특징** | 짧게 자주, 실패해도 다음 날 복구 가능 |
| **운영** | 높은 우선순위, 워터마크 기반 |

```
[증분 수집 흐름]
    │
    ├── 워터마크 로드
    │      └── last_run: "2025-12-27T00:00:00Z"
    │
    ├── 안전 윈도우 적용 (-2일)
    │      └── from_date = last_run - 2days
    │
    ├── Search API (날짜 필터)
    │      └── FIRST_PDATE:[2025-12-25 TO 2025-12-28]
    │
    ├── 중복 제거 (upsert)
    │      └── overlap으로 들어온 기존 데이터 → DB에서 자동 처리
    │
    ├── Fulltext XML 수집 + 파싱 + 저장
    │
    └── 워터마크 업데이트
           └── last_run: "2025-12-28T00:00:00Z"
```

**안전 윈도우 (-2일) 이유:**
- Europe PMC 인덱싱 지연 가능성
- 늦게 반영되는 데이터 누락 방지
- overlap 중복은 DB upsert로 해결

### 2.3 C. 보정 (Reconciliation / Repair)

| 항목 | 내용 |
|------|------|
| **목적** | 데이터 품질 향상, 누락 복구, 중복 병합 |
| **트리거** | 주 1회, 월 1회, 또는 backlog 기반 |
| **데이터량** | 작지만 중요 |
| **특징** | 데이터 정합성 유지 |
| **운영** | 낮은 빈도, 높은 정확도 |

**보정 대상:**

| 케이스 | 설명 | 처리 |
|--------|------|------|
| DOI-only → PMID 매핑 | 처음엔 DOI만 있다가 나중에 PMID 부여 | 7~30일간 주기적 재조회 |
| 메타데이터 보강 | 저자 정보, 소속 등 나중에 추가 | 주기적 재수집 |
| 중복 병합 | 같은 논문이 다른 ID로 수집됨 | OAR-23 중복 검출 후 병합 |
| 누락 복구 | 네트워크 오류로 수집 실패한 건 | failed_requests.json 재처리 |

```
[보정 흐름 - DOI-only 재조회]
    │
    ├── DOI-only 레코드 조회
    │      └── SELECT * FROM papers WHERE pmid IS NULL AND doi IS NOT NULL
    │              AND created_at > NOW() - INTERVAL '30 days'
    │
    ├── Europe PMC API로 PMID 조회
    │      └── DOI 기반 검색
    │
    └── PMID 있으면 업데이트
           └── UPDATE papers SET pmid = $1, paper_id = $2 WHERE id = $3
```

---

## 3. 증분 수집: 변경 감지 원칙

### 3.1 원칙 1: 서버 제공 업데이트 기준 우선 (2트랙 전략)

> ⚠️ **중요**: API마다 제공하는 날짜 필드가 다르고, 의미도 다를 수 있음.
> 구현 전 각 소스의 필드 정확성 검증 필수!

**현실적인 2트랙 전략:**

| 트랙 | 목적 | 방법 |
|------|------|------|
| **트랙 1: 신규** | 새 논문 수집 | 출판일(FIRST_PDATE) 기반 증분 |
| **트랙 2: 변경** | 메타데이터 업데이트 반영 | 보정(C) 배치로 주기적 재확인 |

```python
# 트랙 1: 출판일 기반 신규 논문 (확실함)
query = f"{base_query} AND FIRST_PDATE:[{from_date} TO {to_date}]"

# 트랙 2: 보정 배치에서 기존 논문 변경 확인
# → DB의 raw_xml_hash와 재수집 결과 비교
```

**이유:**
- 출판일(FIRST_PDATE)은 대부분 API에서 신뢰 가능
- UPDATE_DATE는 API마다 의미가 다르거나 없을 수 있음
- 정정(Erratum), 저자 수정 등은 출판일 이후 발생 → 보정으로 처리

**결론:** 신규는 증분(B)으로, 변경은 보정(C)으로 분리하는 게 가장 안전

### 3.2 원칙 2: 워터마크 + 안전 윈도우

```python
@dataclass
class IncrementalState:
    """증분 수집 상태"""
    last_completed_at: datetime     # 마지막 "성공 완료" 시각 (중요!)
    overlap_days: int = 2           # 안전 윈도우 (일)

    @property
    def from_date(self) -> datetime:
        """시작 날짜 (overlap 적용)"""
        return self.last_completed_at - timedelta(days=self.overlap_days)
```

> ⚠️ **워터마크 저장 시점 주의**
>
> | 방식 | 문제점 |
> |------|--------|
> | 시작 시점에 저장 | 중간 실패 시 워터마크만 앞으로 가서 **누락 발생** |
> | **완료 시점에 저장** ✅ | 실패해도 다음에 다시 시도 가능 |
>
> **권장: 성공적으로 완료된 시점(completed_at)을 워터마크로 저장**

```python
async def run_incremental():
    state = load_watermark()
    from_date = state.from_date

    try:
        await collect_papers_since(from_date)
        # 성공 시에만 워터마크 업데이트
        save_watermark(IncrementalState(last_completed_at=datetime.now()))
    except Exception:
        # 실패 시 워터마크 유지 → 다음 실행에서 재시도
        raise
```

**Overlap으로 인한 중복 처리:**
```sql
-- papers 테이블 UPSERT
INSERT INTO papers (paper_id, ...) VALUES ($1, ...)
ON CONFLICT (paper_id) DO UPDATE SET
    title = EXCLUDED.title,
    updated_at = NOW()
```

### 3.3 원칙 3: DOI-only 보정은 별도 큐

```python
# 보정 대상 큐
doi_only_backlog = [
    {"doi": "10.1234/example", "created_at": "2025-12-20", "retry_count": 0},
    {"doi": "10.5678/another", "created_at": "2025-12-21", "retry_count": 1},
]

# 보정 정책
MAX_RETRY_DAYS = 30     # 30일까지 재시도
RETRY_INTERVAL = 7      # 7일마다 재시도
```

---

## 4. 스케줄 및 우선순위

### 4.1 권장 스케줄

| 배치 | 빈도 | 시간대 | 우선순위 |
|------|------|--------|----------|
| **증분 수집 (B)** | 매일 1회 | 새벽 3시 | 🔴 최우선 |
| 초기 적재 (A) | 필요시 | 증분 외 시간 (밤) | 🟡 낮음 |
| 보정 (C) | 주 1회 | 주말 새벽 | 🟢 낮음 |

### 4.2 실행 정책

```
[일일 스케줄 예시]

00:00-03:00  초기 적재 (저속, 여유 있을 때)
03:00-04:00  증분 수집 (최우선, 빠르게)
04:00-06:00  초기 적재 재개
06:00-       일반 운영 시간 (필요시 수동 실행)

[주간 스케줄]

일요일 02:00  보정 배치 실행
```

---

## 5. 구현 전략: 단일 큐 + 우선순위

### 5.1 설계 원칙

> 시스템을 완전히 쪼개지 않고, **작업 큐 하나 + 우선순위**로 관리

```python
@dataclass
class CollectionJob:
    """수집 작업"""
    job_id: str
    job_type: Literal["backfill", "incremental", "repair"]
    priority: int                   # 낮을수록 우선 (1=최우선)
    query: str                      # 검색 쿼리
    params: dict                    # 추가 파라미터
    status: str = "pending"
    created_at: datetime = field(default_factory=datetime.now)

# 우선순위 설정
PRIORITY = {
    "incremental": 1,   # 최우선
    "repair": 5,        # 중간
    "backfill": 10,     # 낮음
}
```

### 5.2 작업 테이블 (프로덕션 레벨)

```sql
CREATE TABLE collection_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- 기본 정보
    job_type VARCHAR(20) NOT NULL,      -- backfill, incremental, repair
    priority INT DEFAULT 10,
    query TEXT NOT NULL,
    params JSONB,
    api_name VARCHAR(50) DEFAULT 'europe_pmc',  -- API별 limiter 연결

    -- 상태 관리
    status VARCHAR(20) DEFAULT 'pending',  -- pending, running, completed, failed, delayed
    checkpoint JSONB,                    -- 체크포인트 (중단 재개용)

    -- 재시도 관리
    attempt_count INT DEFAULT 0,         -- 현재까지 시도 횟수
    max_attempts INT DEFAULT 5,          -- 최대 재시도 횟수
    next_run_at TIMESTAMPTZ,             -- 429/백오프 후 재실행 시각 (delay queue)

    -- 워커 락 (동시 처리 방지)
    locked_at TIMESTAMPTZ,               -- 워커가 집어간 시각
    locked_by VARCHAR(100),              -- 워커 ID

    -- 에러 추적
    last_error_code VARCHAR(10),         -- 429, 500, TIMEOUT 등
    last_error_message TEXT,
    last_error_at TIMESTAMPTZ,

    -- 타임스탬프
    created_at TIMESTAMPTZ DEFAULT NOW(),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ
);

-- 인덱스 1: 우선순위 순으로 pending 작업 조회
CREATE INDEX idx_jobs_pending ON collection_jobs (priority, created_at)
    WHERE status = 'pending' AND (next_run_at IS NULL OR next_run_at <= NOW());

-- 인덱스 2: delayed 작업 중 실행 가능한 것
CREATE INDEX idx_jobs_delayed ON collection_jobs (next_run_at)
    WHERE status = 'delayed' AND next_run_at IS NOT NULL;

-- 인덱스 3: 오래된 락 감지 (좀비 워커)
CREATE INDEX idx_jobs_stale_lock ON collection_jobs (locked_at)
    WHERE status = 'running';
```

**워커의 작업 획득 (SKIP LOCKED 패턴):**

```sql
-- 동시 워커 안전하게 작업 획득
-- ORDER BY: 우선순위 → next_run_at(delayed 작업) → created_at
UPDATE collection_jobs
SET status = 'running',
    locked_at = NOW(),
    locked_by = $1  -- worker_id
    -- ⚠️ attempt_count는 여기서 증가 안 함 (아래 설명 참고)
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

> ⚠️ **attempt_count 증가 시점 주의**
>
> | 방식 | 문제점 |
> |------|--------|
> | 작업 획득 시 +1 | 429로 바로 delayed 되면 실제 수집 안 했는데 attempt만 소진 |
> | **실제 요청 후 +1** ✅ | 외부 API 호출 성공/실패 후에만 카운트 |
>
> **권장:** attempt_count는 `실제 외부 요청을 수행한 후`에만 증가
> 429는 별도 `rate_limit_count`로 분리하고, max_attempts 적용 안 함 (또는 느슨하게)

**429 발생 시 delay queue로 이동:**

```sql
UPDATE collection_jobs
SET status = 'delayed',
    next_run_at = NOW() + INTERVAL '30 seconds',  -- 백오프 시간
    last_error_code = '429',
    last_error_at = NOW(),
    locked_at = NULL,
    locked_by = NULL
WHERE id = $1;
```

### 5.3 Request Manager (Rate Limit 통합 관리) - 강화 버전

> **핵심 원칙**: 단순 delay로는 벤 방지 불가. 429 대응 + Circuit Breaker 필수.

```python
@dataclass
class APILimiterConfig:
    """API별 Rate Limiter 설정"""
    api_name: str
    rps_limit: float = 2.0              # 초당 요청 수 제한
    max_concurrent: int = 3              # 동시 요청 수 제한
    base_backoff: float = 1.0            # 기본 백오프 (초)
    max_backoff: float = 60.0            # 최대 백오프 (초)
    circuit_break_threshold: int = 5     # 연속 429 N회 시 쿨다운
    circuit_break_duration: float = 300  # 쿨다운 시간 (초)


class RequestManager:
    """API 요청 통합 관리

    기능:
    1. API별 limiter 분리 (Europe PMC / PubMed / Crossref)
    2. 429 처리: Retry-After 우선, 없으면 지수 백오프+지터
    3. Circuit breaker: 연속 429 시 전면 휴식
    4. 동시성 제한(세마포어) + RPS 제한(토큰버킷)
    """

    def __init__(self):
        self.limiters: dict[str, APILimiter] = {}
        self._register_default_limiters()

    def _register_default_limiters(self):
        self.limiters["europe_pmc"] = APILimiter(APILimiterConfig(
            api_name="europe_pmc",
            rps_limit=5.0,          # 실험 결과 기반
            max_concurrent=3,
        ))

    async def request(
        self,
        api_name: str,
        url: str,
        **kwargs
    ) -> httpx.Response:
        """API별 rate limit + 에러 대응 (429/5xx/timeout 분기)"""
        limiter = self.limiters[api_name]

        # Circuit breaker 체크 (3-state: CLOSED → OPEN → HALF_OPEN → CLOSED)
        state = limiter.get_circuit_state()
        if state == CircuitState.OPEN:
            raise CircuitOpenError(api_name, retry_after=limiter.circuit_opens_at)
        elif state == CircuitState.HALF_OPEN:
            # half-open: probe 1~2개만 허용, 성공하면 close, 실패하면 다시 open
            if not limiter.try_acquire_probe():
                raise CircuitOpenError(api_name, retry_after=limiter.circuit_opens_at)

        # 동시성 제한 (세마포어)
        async with limiter.semaphore:
            # RPS 제한 (토큰 버킷)
            await limiter.acquire_token()

            try:
                response = await self._do_request(url, **kwargs)
            except (httpx.TimeoutException, httpx.ConnectError) as e:
                # 네트워크 오류: 백오프 + 재시도
                limiter.record_error("NETWORK")
                raise RetryableError(error_code="NETWORK", wait_time=self._get_backoff(limiter))

            status = response.status_code

            # 성공: circuit 리셋 (half-open → closed)
            if status < 400:
                limiter.record_success()
                return response

            # 429 Rate Limit: Retry-After 우선
            elif status == 429:
                wait_time = self._get_429_wait_time(response, limiter)
                limiter.record_429()
                if limiter.consecutive_errors >= limiter.config.circuit_break_threshold:
                    limiter.open_circuit()
                raise RateLimitError(error_code="429", wait_time=wait_time)

            # 5xx 서버 오류: 백오프 + 재시도
            elif status in (500, 502, 503, 504):
                limiter.record_error("5XX")
                raise RetryableError(error_code=str(status), wait_time=self._get_backoff(limiter))

            # 4xx 클라이언트 오류: 재시도 금지 (즉시 failed)
            elif status in (400, 401, 403, 404):
                raise NonRetryableError(status_code=status)

    def _get_429_wait_time(self, response: httpx.Response, limiter: APILimiter) -> float:
        """429 대기 시간 계산: Retry-After 우선, 없으면 지수 백오프+지터"""
        # Retry-After 헤더 우선
        retry_after = response.headers.get("Retry-After")
        if retry_after:
            try:
                return float(retry_after)
            except ValueError:
                pass  # HTTP-date 형식이면 파싱 필요

        # 지수 백오프 + 지터
        backoff = min(
            limiter.config.base_backoff * (2 ** limiter.consecutive_429s),
            limiter.config.max_backoff
        )
        jitter = random.uniform(0, backoff * 0.1)
        return backoff + jitter
```

**핵심 방어 레이어:**

| 레이어 | 역할 | 구현 |
|--------|------|------|
| RPS 제한 | 초당 요청 수 제한 | 토큰 버킷 |
| 동시성 제한 | 동시 요청 수 제한 | 세마포어 |
| 429 백오프 | 지수 백오프 + 지터 | Retry-After 우선 |
| Circuit Breaker | 연속 429 시 전면 휴식 | 5회 연속 → 5분 쿨다운 |

---

## 6. 구현 우선순위 (Rate Limit 조기 적용)

> ⚠️ **중요**: Rate Limit/재시도는 지속 수집 MVP에 필수! Phase 3까지 미루면 안 됨

| 단계 | 항목 | 필요성 |
|------|------|--------|
| **Phase 1** | 증분 수집 (B) | MVP 필수 |
| **Phase 1** | 초기 적재 (A) | MVP 필수 |
| **Phase 1** | 429/5xx/timeout 재시도 | ⚠️ **MVP 필수** - 없으면 수집 중단됨 |
| **Phase 1** | 동시성 제한 (세마포어) | ⚠️ **MVP 필수** - 과부하 방지 |
| Phase 2 | 체크포인트 (A용) | 대량 수집 안정성 |
| Phase 2 | 워터마크 관리 (B용) | 증분 정확성 |
| Phase 2 | Circuit Breaker | 연속 실패 시 자동 휴식 |
| Phase 3 | 보정 배치 (C) | 데이터 품질 |
| Phase 3 | 작업 큐 시스템 | 운영 자동화 |
| Phase 3 | API별 Limiter 분리 | 멀티 소스 대응 |

**Phase 1 최소 재시도 셋:**
```python
# MVP 최소 요구사항
- 429: Retry-After 준수 + backoff+jitter
- 5xx/timeout/connection: backoff+jitter 재시도
- 동시성 제한: 세마포어 (max_concurrent=3)
```

---

## 7. 실패 처리: 파일 → DB 승격

> ⚠️ **MVP의 failed_requests.json은 빠르게 DB 테이블로 승격 권장**

**파일 기반 문제점:**
- 병렬 워커에서 파일 경합
- 재처리/관측/리포팅 어려움
- 운영 중 유실 위험

**해결:** 작업 테이블(collection_jobs)에 실패 상태로 기록

```sql
-- 실패한 개별 논문 수집 작업
INSERT INTO collection_jobs (
    job_type, priority, query, params, status,
    last_error_code, last_error_message
) VALUES (
    'repair', 5, $1, $2, 'failed',
    $3, $4
);

-- 재처리 대상 조회
SELECT * FROM collection_jobs
WHERE status = 'failed'
  AND attempt_count < max_attempts
ORDER BY created_at;
```

---

## 8. 관측 (Observability)

> 운영에서 문제 파악과 튜닝을 위한 최소 메트릭

### 8.1 필수 메트릭

| 메트릭 | 설명 | 용도 |
|--------|------|------|
| `api_429_count` | API별 429 발생 횟수 | Rate limit 튜닝 |
| `api_5xx_count` | API별 5xx 발생 횟수 | 서버 문제 감지 |
| `api_timeout_count` | API별 timeout 횟수 | 네트워크 문제 감지 |
| `job_queue_depth` | 상태별 작업 수 (pending/delayed/failed) | 적체 감지 |
| `request_latency_p95` | 요청 레이턴시 95퍼센타일 | 성능 모니터링 |
| `circuit_open_count` | Circuit breaker 열린 횟수 | API 건강 상태 |
| `circuit_open_duration` | Circuit 열린 지속 시간 | 복구 시간 |
| `ingest_rate` | 분/시간당 수집 건수 | 처리량 모니터링 |

### 8.2 로그 포맷

```python
# 구조화된 로그 (JSON)
logger.info("paper_collected", extra={
    "paper_id": "PMC12345",
    "api": "europe_pmc",
    "latency_ms": 1234,
    "attempt": 2,
    "job_type": "incremental",
})

logger.warning("rate_limit_hit", extra={
    "api": "europe_pmc",
    "wait_time": 30,
    "retry_after": "30",
    "consecutive_429s": 3,
})

logger.error("circuit_opened", extra={
    "api": "europe_pmc",
    "duration": 300,
    "consecutive_errors": 5,
})
```

### 8.3 대시보드 권장 패널

```
┌─────────────────┬─────────────────┬─────────────────┐
│ Ingest Rate     │ Queue Depth     │ Error Rate      │
│ (건/분)          │ (pending/delay) │ (429/5xx/timeout)│
├─────────────────┼─────────────────┼─────────────────┤
│ P95 Latency     │ Circuit Status  │ Success Rate    │
│ (ms)            │ (open/closed)   │ (%)             │
└─────────────────┴─────────────────┴─────────────────┘
```

---

## 9. 체크리스트

### Phase 1 (MVP)
- [ ] 증분 수집 구현 (날짜 필터 기반)
- [ ] 초기 적재 구현 (페이지네이션)
- [ ] **429/5xx/timeout 재시도** ⚠️
- [ ] **동시성 제한 (세마포어)** ⚠️
- [ ] 실패 처리 → DB 테이블 기록

### Phase 2
- [ ] 체크포인트 저장/복구
- [ ] 워터마크 관리 (완료 시점 저장)
- [ ] 안전 윈도우 적용 (-2일)
- [ ] Circuit Breaker (half-open 포함)
- [ ] SKIP LOCKED 패턴 워커

### Phase 3
- [ ] 보정 배치 (DOI-only 재조회)
- [ ] API별 Limiter 분리
- [ ] 우선순위 기반 스케줄러
- [ ] 메트릭/대시보드 구축

---

## 10. 참고

- [rate-limit-retry-design.md](./rate-limit-retry-design.md) - Rate Limit 및 재시도 설계
- [OAR-23 duplicate-detection-scenarios.md](../../OAR-23/yts/docs/duplicate-detection-scenarios.md) - 중복 검출 (보정 배치 연계)
- [OAR-19 hash-design-improvements.md](../../OAR-19/yts/docs/hash-design-improvements.md) - 변경 감지
