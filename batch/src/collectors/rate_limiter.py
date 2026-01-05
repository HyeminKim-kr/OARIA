"""Rate Limiter

OAR-22 설계 기반:
- RPS 제한 (토큰 버킷)
- 동시성 제한 (세마포어)
- 429 백오프 (Retry-After 우선, 지수 백오프 + 지터)
- Circuit Breaker (연속 429 시 쿨다운)
"""

import asyncio
import random
import time
from dataclasses import dataclass, field
from enum import Enum

import structlog

logger = structlog.get_logger()


class CircuitState(Enum):
    """Circuit Breaker 상태"""

    CLOSED = "closed"  # 정상
    OPEN = "open"  # 차단
    HALF_OPEN = "half_open"  # 테스트 중


@dataclass
class RateLimiterConfig:
    """Rate Limiter 설정"""

    rps_limit: float = 5.0  # 초당 요청 수
    max_concurrent: int = 3  # 동시 요청 수
    base_backoff: float = 1.0  # 기본 백오프 (초)
    max_backoff: float = 60.0  # 최대 백오프 (초)
    circuit_threshold: int = 5  # 연속 429 N회 시 서킷 오픈
    circuit_duration: float = 300.0  # 서킷 오픈 지속 시간 (초)


@dataclass
class RateLimiter:
    """Rate Limiter

    토큰 버킷 + 세마포어 + Circuit Breaker
    """

    config: RateLimiterConfig = field(default_factory=RateLimiterConfig)

    # 내부 상태
    _semaphore: asyncio.Semaphore | None = field(default=None, repr=False)
    _tokens: float = field(default=0.0, repr=False)
    _last_refill: float = field(default_factory=time.monotonic, repr=False)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock, repr=False)

    # Circuit Breaker 상태
    _circuit_state: CircuitState = field(default=CircuitState.CLOSED, repr=False)
    _consecutive_429s: int = field(default=0, repr=False)
    _circuit_opened_at: float | None = field(default=None, repr=False)

    # 통계
    total_requests: int = field(default=0)
    total_429s: int = field(default=0)
    total_5xxs: int = field(default=0)

    def __post_init__(self):
        self._semaphore = asyncio.Semaphore(self.config.max_concurrent)
        self._tokens = self.config.rps_limit

    async def acquire(self) -> None:
        """요청 전 호출 - 토큰 획득 + 세마포어"""
        # Circuit Breaker 체크
        if self._circuit_state == CircuitState.OPEN:
            await self._check_circuit_recovery()
            if self._circuit_state == CircuitState.OPEN:
                wait_time = self._get_circuit_remaining_time()
                raise CircuitOpenError(f"Circuit open, retry after {wait_time:.1f}s")

        # 세마포어 획득
        await self._semaphore.acquire()

        try:
            # 토큰 버킷에서 토큰 획득
            await self._acquire_token()
        except Exception:
            self._semaphore.release()
            raise

    def release(self) -> None:
        """요청 후 호출 - 세마포어 해제"""
        self._semaphore.release()

    async def _acquire_token(self) -> None:
        """토큰 버킷에서 토큰 획득"""
        async with self._lock:
            self._refill_tokens()

            if self._tokens >= 1.0:
                self._tokens -= 1.0
                return

            # 토큰 부족 - 대기
            wait_time = (1.0 - self._tokens) / self.config.rps_limit
            await asyncio.sleep(wait_time)
            self._tokens = 0.0

    def _refill_tokens(self) -> None:
        """토큰 리필"""
        now = time.monotonic()
        elapsed = now - self._last_refill
        self._tokens = min(
            self.config.rps_limit, self._tokens + elapsed * self.config.rps_limit
        )
        self._last_refill = now

    def record_success(self) -> None:
        """성공 기록 - 연속 실패 카운터 리셋"""
        self.total_requests += 1
        self._consecutive_429s = 0

        # Half-Open → Closed
        if self._circuit_state == CircuitState.HALF_OPEN:
            self._circuit_state = CircuitState.CLOSED
            logger.info("circuit_closed", total_429s=self.total_429s)

    def record_429(self, retry_after: float | None = None) -> float:
        """429 에러 기록 - 백오프 시간 반환"""
        self.total_requests += 1
        self.total_429s += 1
        self._consecutive_429s += 1

        # Circuit Breaker 체크
        if self._consecutive_429s >= self.config.circuit_threshold:
            self._open_circuit()

        # 백오프 시간 계산
        wait_time = self._calculate_backoff(retry_after)

        logger.warning(
            "rate_limit_hit",
            consecutive_429s=self._consecutive_429s,
            wait_time=wait_time,
            circuit_state=self._circuit_state.value,
        )

        return wait_time

    def record_5xx(self) -> float:
        """5xx 에러 기록 - 백오프 시간 반환"""
        self.total_requests += 1
        self.total_5xxs += 1

        # 5xx는 circuit breaker에 영향 안 줌, 단순 백오프
        return self._calculate_backoff(None)

    def _calculate_backoff(self, retry_after: float | None) -> float:
        """백오프 시간 계산: Retry-After 우선, 없으면 지수 백오프 + 지터"""
        if retry_after is not None:
            return retry_after

        # 지수 백오프
        backoff = min(
            self.config.base_backoff * (2 ** (self._consecutive_429s - 1)),
            self.config.max_backoff,
        )

        # 지터 추가 (0~10%)
        jitter = random.uniform(0, backoff * 0.1)
        return backoff + jitter

    def _open_circuit(self) -> None:
        """Circuit 열기"""
        self._circuit_state = CircuitState.OPEN
        self._circuit_opened_at = time.monotonic()
        logger.error(
            "circuit_opened",
            consecutive_429s=self._consecutive_429s,
            duration=self.config.circuit_duration,
        )

    async def _check_circuit_recovery(self) -> None:
        """Circuit 회복 체크"""
        if self._circuit_opened_at is None:
            return

        elapsed = time.monotonic() - self._circuit_opened_at
        if elapsed >= self.config.circuit_duration:
            self._circuit_state = CircuitState.HALF_OPEN
            self._consecutive_429s = 0
            logger.info("circuit_half_open")

    def _get_circuit_remaining_time(self) -> float:
        """Circuit 오픈 남은 시간"""
        if self._circuit_opened_at is None:
            return 0.0
        elapsed = time.monotonic() - self._circuit_opened_at
        return max(0.0, self.config.circuit_duration - elapsed)

    def get_stats(self) -> dict:
        """통계 반환"""
        return {
            "total_requests": self.total_requests,
            "total_429s": self.total_429s,
            "total_5xxs": self.total_5xxs,
            "circuit_state": self._circuit_state.value,
            "consecutive_429s": self._consecutive_429s,
        }


class CircuitOpenError(Exception):
    """Circuit Breaker가 열려있을 때 발생"""

    pass


class RateLimitError(Exception):
    """429 에러 발생 시"""

    def __init__(self, wait_time: float):
        self.wait_time = wait_time
        super().__init__(f"Rate limited, retry after {wait_time:.1f}s")


class RetryableError(Exception):
    """재시도 가능한 에러 (5xx, timeout)"""

    def __init__(self, status_code: int, wait_time: float):
        self.status_code = status_code
        self.wait_time = wait_time
        super().__init__(f"Retryable error {status_code}, retry after {wait_time:.1f}s")
