# Rate Limit 처리 및 재시도 로직 설계

> **OAR-22**: Rate Limit 처리 및 재시도 로직 구현
>
> **서브태스크**: OAR-97
>
> **작성일**: 2025-12-28

---

## 1. 배경 및 필요성

### 1.1 문제 상황

논문 배치 수집 시 발생할 수 있는 문제:

```
배치 수집 (1000건)
    ├── 200건 처리 후 → 429 Too Many Requests
    ├── 500건 처리 후 → 네트워크 타임아웃
    └── 750건 처리 후 → 503 Service Unavailable
```

현재 구현(OAR-19)은 단순히 실패 시 `None` 반환 → **데이터 유실**

### 1.2 목표

| 목표 | 설명 |
|------|------|
| API 밴 방지 | Rate limit 준수로 IP 차단 예방 |
| 수집 안정성 | 일시적 오류에서 자동 복구 |
| 가시성 확보 | 실패 원인 및 통계 추적 |

---

## 2. Europe PMC API 특성

### 2.1 공식 Rate Limit

> Europe PMC REST API는 명시적인 rate limit을 공개하지 않음.

### 2.2 실험 결과 (2025-12-28) ✅

직접 실험을 통해 실제 rate limit 특성을 파악했습니다.

**Search API 테스트:**
| Delay | 요청 수 | 429 발생 | RPS |
|-------|---------|----------|-----|
| 1.0s | 10 | ❌ | 0.65 |
| 0.5s | 10 | ❌ | 0.96 |
| 0.3s | 10 | ❌ | 1.24 |
| 0.2s | 10 | ❌ | 1.42 |
| 0.1s | 10 | ❌ | 1.59 |
| **무대기** | **100** | ❌ | **2.10** |

**Fulltext XML API 테스트:**
| Delay | 요청 수 | 429 발생 | RPS | 평균 크기 |
|-------|---------|----------|-----|-----------|
| 무대기 | 10 | ❌ | 0.19 | 129 KB |

**핵심 발견:**
1. **Europe PMC는 매우 관대함** - 무대기 100회 연속 요청에도 429 미발생
2. **Fulltext XML은 자체가 느림** - 요청당 ~4초 소요 (네트워크 병목)
3. **429 발생 안 함** - 실험 범위 내에서는 rate limit 미적용

**결론:**
- 기존 0.3초 delay는 과도하게 보수적
- **권장: 0.1초 delay** (3배 빨라짐, 여전히 안전마진 확보)

> 실험 코드: `tests/rate_limit_experiment_v3.py`

### 2.3 관찰된 응답 패턴

| 상황 | HTTP 코드 | 설명 |
|------|-----------|------|
| 정상 | 200 | 성공 |
| Rate Limit | 429 | 요청 과다 (대기 후 재시도 가능) |
| 서버 과부하 | 503 | 일시적 서비스 불가 |
| 서버 오류 | 500, 502 | 서버 측 문제 |
| 콘텐츠 없음 | 404 | 해당 논문 없음 (재시도 불필요) |
| 잘못된 요청 | 400 | 파라미터 오류 (재시도 불필요) |

### 2.4 Retry-After 헤더

```
429 응답 시 Retry-After 헤더가 있을 수 있음:
  Retry-After: 60       # 60초 후 재시도
  Retry-After: <date>   # 특정 시간 후 재시도

→ 헤더가 있으면 해당 값 사용, 없으면 backoff 적용
```

---

## 3. 에러 분류 및 처리 전략

### 3.1 에러 분류 체계

```python
class ErrorCategory(Enum):
    RETRYABLE_RATE_LIMIT = "rate_limit"      # 429 → backoff 후 재시도
    RETRYABLE_SERVER = "server_error"         # 5xx → 즉시 재시도
    RETRYABLE_NETWORK = "network_error"       # 타임아웃, 연결실패 → 재시도
    NON_RETRYABLE_CLIENT = "client_error"     # 400, 404 → 재시도 불필요
    NON_RETRYABLE_FATAL = "fatal_error"       # 예상치 못한 오류
```

### 3.2 HTTP 코드별 처리

| HTTP 코드 | 분류 | 처리 |
|-----------|------|------|
| 429 | `RETRYABLE_RATE_LIMIT` | Exponential backoff (1s→2s→4s→8s→16s) |
| 500, 502, 503, 504 | `RETRYABLE_SERVER` | 고정 대기 (2초) 후 재시도 |
| Timeout, ConnectionError | `RETRYABLE_NETWORK` | 고정 대기 (1초) 후 재시도 |
| 400, 401, 403 | `NON_RETRYABLE_CLIENT` | 즉시 실패 처리, 로그 기록 |
| 404 | `NON_RETRYABLE_CLIENT` | 콘텐츠 없음으로 처리 (정상 케이스) |

---

## 4. Exponential Backoff 알고리즘

### 4.1 기본 공식

```python
wait_time = min(base_delay * (2 ** attempt), max_delay) + jitter
```

| 파라미터 | 값 | 설명 |
|----------|-----|------|
| `base_delay` | 1초 | 기본 대기 시간 |
| `max_delay` | 60초 | 최대 대기 시간 |
| `max_attempts` | 5 | 최대 재시도 횟수 |
| `jitter` | 0~0.5초 | 랜덤 지연 (thundering herd 방지) |

### 4.2 대기 시간 예시 (429 에러)

```
시도 1: 실패 → 대기 1초 (+ jitter)
시도 2: 실패 → 대기 2초 (+ jitter)
시도 3: 실패 → 대기 4초 (+ jitter)
시도 4: 실패 → 대기 8초 (+ jitter)
시도 5: 실패 → 대기 16초 (+ jitter)
시도 6: 최종 실패 → 예외 발생 또는 None 반환
```

### 4.3 Retry-After 헤더 우선

```python
def get_wait_time(response: httpx.Response, attempt: int) -> float:
    """Retry-After 헤더가 있으면 우선 사용"""
    retry_after = response.headers.get("Retry-After")

    if retry_after:
        try:
            return float(retry_after)
        except ValueError:
            # HTTP-date 형식인 경우 파싱
            pass

    # 헤더 없으면 exponential backoff
    return min(BASE_DELAY * (2 ** attempt), MAX_DELAY) + random.uniform(0, 0.5)
```

---

## 5. 재시도 로직 구현

### 5.1 RetryConfig 설정

```python
@dataclass
class RetryConfig:
    """재시도 설정"""
    max_attempts: int = 5           # 최대 재시도 횟수
    base_delay: float = 1.0         # 기본 대기 (초)
    max_delay: float = 60.0         # 최대 대기 (초)
    rate_limit_delay: float = 0.3   # 정상 요청 간 간격 (초)
    timeout: float = 60.0           # 요청 타임아웃 (초)

    # 재시도 대상 HTTP 코드
    retryable_status_codes: tuple = (429, 500, 502, 503, 504)
```

### 5.2 핵심 재시도 로직

```python
async def request_with_retry(
    self,
    method: str,
    url: str,
    **kwargs
) -> httpx.Response:
    """재시도 로직이 포함된 HTTP 요청"""

    last_exception = None

    for attempt in range(self.config.max_attempts):
        try:
            # Rate limit 준수
            await self._wait_rate_limit()

            # 요청 실행
            response = await self.client.request(method, url, **kwargs)

            # 성공
            if response.status_code < 400:
                self.stats.record_success()
                return response

            # 재시도 가능한 에러
            if response.status_code in self.config.retryable_status_codes:
                wait_time = self._get_wait_time(response, attempt)
                self.stats.record_retry(response.status_code, attempt)

                logger.warning(
                    f"HTTP {response.status_code}, "
                    f"attempt {attempt + 1}/{self.config.max_attempts}, "
                    f"waiting {wait_time:.1f}s"
                )

                await asyncio.sleep(wait_time)
                continue

            # 재시도 불가능한 에러
            self.stats.record_failure(response.status_code)
            response.raise_for_status()

        except (httpx.TimeoutException, httpx.ConnectError) as e:
            last_exception = e
            self.stats.record_network_error()

            if attempt < self.config.max_attempts - 1:
                wait_time = 1.0 + random.uniform(0, 0.5)
                logger.warning(
                    f"Network error: {e}, "
                    f"attempt {attempt + 1}/{self.config.max_attempts}, "
                    f"waiting {wait_time:.1f}s"
                )
                await asyncio.sleep(wait_time)
                continue

    # 모든 재시도 실패
    self.stats.record_final_failure()
    raise MaxRetriesExceeded(
        f"Max retries ({self.config.max_attempts}) exceeded",
        last_exception=last_exception
    )
```

### 5.3 실패 처리 전략

```python
class FailureStrategy(Enum):
    RAISE = "raise"           # 예외 발생 (배치 중단)
    RETURN_NONE = "none"      # None 반환 (건너뛰기)
    COLLECT = "collect"       # 실패 목록에 수집 (나중에 재처리)
```

배치 수집 시 권장: `COLLECT` → 실패 건만 별도 재처리

---

## 6. 통계 수집 및 모니터링

### 6.1 수집 메트릭

```python
@dataclass
class RequestStats:
    """요청 통계"""
    total_requests: int = 0          # 총 요청 수
    successful_requests: int = 0      # 성공 수
    failed_requests: int = 0          # 최종 실패 수

    # 재시도 통계
    retry_count: int = 0              # 총 재시도 횟수
    rate_limit_hits: int = 0          # 429 발생 횟수
    server_errors: int = 0            # 5xx 발생 횟수
    network_errors: int = 0           # 네트워크 오류 횟수

    # 타이밍
    total_wait_time: float = 0.0      # 총 대기 시간 (초)
    start_time: float = 0.0           # 배치 시작 시간

    @property
    def success_rate(self) -> float:
        if self.total_requests == 0:
            return 0.0
        return self.successful_requests / self.total_requests * 100

    @property
    def avg_retries_per_request(self) -> float:
        if self.total_requests == 0:
            return 0.0
        return self.retry_count / self.total_requests
```

### 6.2 로그 출력 예시

```
[2025-12-28 10:30:45] INFO: Batch progress: 500/1000 (50.0%)
[2025-12-28 10:30:46] WARN: HTTP 429, attempt 1/5, waiting 1.3s
[2025-12-28 10:30:47] WARN: HTTP 429, attempt 2/5, waiting 2.4s
[2025-12-28 10:30:50] INFO: Retry succeeded after 2 attempts

[2025-12-28 11:00:00] INFO: === Batch Complete ===
  Total: 1000, Success: 985, Failed: 15
  Success Rate: 98.5%
  Rate Limit Hits: 23
  Total Retries: 45
  Total Wait Time: 127.5s
```

### 6.3 실패 리포트

```python
@dataclass
class FailedRequest:
    """실패한 요청 정보"""
    paper_id: str                    # 논문 ID (pmcid 등)
    url: str                         # 요청 URL
    error_type: str                  # 에러 유형
    status_code: int | None          # HTTP 코드 (네트워크 오류시 None)
    attempts: int                    # 시도 횟수
    last_error: str                  # 마지막 에러 메시지
    timestamp: datetime              # 실패 시간

# 실패 목록 저장 → 나중에 재처리 가능
failed_requests: list[FailedRequest] = []
```

---

## 7. 배치 수집 통합

### 7.1 BatchCollector 인터페이스

```python
class BatchCollector:
    """배치 논문 수집기"""

    def __init__(
        self,
        client: ResilientPMCClient,
        failure_strategy: FailureStrategy = FailureStrategy.COLLECT,
    ):
        self.client = client
        self.failure_strategy = failure_strategy
        self.failed_requests: list[FailedRequest] = []

    async def collect_papers(
        self,
        paper_ids: list[str],
        progress_callback: Callable | None = None,
    ) -> BatchResult:
        """논문 목록 수집"""

        results = []

        for i, paper_id in enumerate(paper_ids):
            try:
                xml = await self.client.get_fulltext_xml(paper_id)
                results.append((paper_id, xml))

            except MaxRetriesExceeded as e:
                self._handle_failure(paper_id, e)

                if self.failure_strategy == FailureStrategy.RAISE:
                    raise

            # 진행률 콜백
            if progress_callback and i % 100 == 0:
                progress_callback(i, len(paper_ids), self.client.stats)

        return BatchResult(
            successful=results,
            failed=self.failed_requests,
            stats=self.client.stats,
        )
```

### 7.2 재처리 워크플로우

```
1차 배치 수집 (1000건)
    ├── 성공: 985건 → 파싱 및 저장
    └── 실패: 15건 → failed_requests.json 저장

(1시간 후)

재처리 배치
    ├── failed_requests.json 로드
    ├── 더 관대한 설정으로 재시도
    │   (max_attempts: 10, base_delay: 5s)
    └── 최종 실패 건 → 수동 검토 대상
```

---

## 8. 설정 가이드

### 8.1 환경별 권장 설정 (실험 결과 반영)

| 환경 | rate_limit_delay | max_attempts | base_delay | 비고 |
|------|------------------|--------------|------------|------|
| 개발/테스트 | 0.2s | 3 | 1s | 빠른 피드백 |
| **일반 배치** | **0.1s** | 5 | 1s | ✅ 실험 결과 권장 |
| 대량 수집 | 0.1s | 5 | 2s | 안정성 우선 |
| 재처리 | 0.5s | 10 | 5s | 더 관대하게 |

### 8.2 환경 변수

```bash
# .env
EUROPEPMC_RATE_LIMIT_DELAY=0.3
EUROPEPMC_REQUEST_TIMEOUT=60
EUROPEPMC_MAX_RETRY_ATTEMPTS=5
EUROPEPMC_BASE_RETRY_DELAY=1.0
EUROPEPMC_MAX_RETRY_DELAY=60.0
```

---

## 9. 구현 체크리스트

- [ ] `RetryConfig` 데이터클래스
- [ ] `RequestStats` 통계 수집
- [ ] `ResilientPMCClient` 재시도 로직 포함 클라이언트
- [ ] Exponential backoff with jitter
- [ ] Retry-After 헤더 파싱
- [ ] 에러 분류 및 처리
- [ ] `BatchCollector` 배치 수집기
- [ ] 실패 리포트 저장/로드
- [ ] 로깅 통합
- [ ] 단위 테스트 (mock 429 응답)

---

## 10. 참고

- [OAR-19 europe_pmc_client.py](../../OAR-19/yts/src/europe_pmc_client.py) - 기존 구현
- [OAR-19 hash-design-improvements.md](../../OAR-19/yts/docs/hash-design-improvements.md) - 변경 감지 설계
- [OAR-23 duplicate-detection-scenarios.md](../../OAR-23/yts/docs/duplicate-detection-scenarios.md) - 중복 검출 설계
- [Europe PMC REST API](https://europepmc.org/RestfulWebService) - 공식 문서
- [Exponential Backoff (AWS)](https://aws.amazon.com/blogs/architecture/exponential-backoff-and-jitter/) - 알고리즘 참고
