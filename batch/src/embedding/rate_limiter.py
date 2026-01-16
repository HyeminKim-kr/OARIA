"""임베딩 API Rate Limiter

OpenAI 임베딩 API의 TPM(Tokens Per Minute) 제한을 관리합니다.

주요 기능:
1. 지수 백오프 + 지터를 사용한 429 에러 재시도
2. 토큰 예산 기반 쓰로틀링
3. 에러 분류 (retryable vs terminal)
"""

import asyncio
import re
import time
import random
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
import structlog

logger = structlog.get_logger(__name__)


# ─────────────────────────────────────────────────────────────
# 설정 상수
# ─────────────────────────────────────────────────────────────

# OpenAI text-embedding-3-small 제한
DEFAULT_TPM_LIMIT = 1_000_000  # 1M tokens per minute
DEFAULT_RPM_LIMIT = 3_000      # 3K requests per minute

# 재시도 설정
MAX_RETRIES = 5
MIN_RETRY_DELAY = 0.25  # 250ms (버스트 완화용)
MAX_RETRY_DELAY = 30.0  # 최대 30초
BASE_BACKOFF = 0.5      # 초기 백오프 0.5초
JITTER_FACTOR = 0.2     # 지터 비율 (0~20%)


# ─────────────────────────────────────────────────────────────
# 에러 분류
# ─────────────────────────────────────────────────────────────

class ErrorCategory(Enum):
    """에러 분류"""
    RETRYABLE = "retryable"      # 재시도 가능 (429, 5xx, 네트워크 오류)
    TERMINAL = "terminal"        # 재시도 불가 (잘못된 데이터, 파싱 실패)
    UNKNOWN = "unknown"          # 알 수 없음


@dataclass
class ClassifiedError:
    """분류된 에러 정보"""
    category: ErrorCategory
    error_type: str
    message: str
    retry_after_ms: Optional[int] = None
    original_exception: Optional[Exception] = None


def classify_error(exception: Exception) -> ClassifiedError:
    """예외를 분류하여 재시도 가능 여부 판단
    
    Args:
        exception: 발생한 예외
        
    Returns:
        ClassifiedError: 분류된 에러 정보
    """
    error_msg = str(exception)
    error_type = type(exception).__name__
    
    # OpenAI API 에러
    if hasattr(exception, 'status_code'):
        status_code = exception.status_code
        
        # 429 Rate Limit
        if status_code == 429:
            retry_after_ms = _extract_retry_after(error_msg)
            return ClassifiedError(
                category=ErrorCategory.RETRYABLE,
                error_type="rate_limit",
                message=error_msg,
                retry_after_ms=retry_after_ms,
                original_exception=exception,
            )
        
        # 5xx 서버 에러
        if 500 <= status_code < 600:
            return ClassifiedError(
                category=ErrorCategory.RETRYABLE,
                error_type="server_error",
                message=error_msg,
                original_exception=exception,
            )
        
        # 400 잘못된 요청 (재시도 의미 없음)
        if status_code == 400:
            return ClassifiedError(
                category=ErrorCategory.TERMINAL,
                error_type="bad_request",
                message=error_msg,
                original_exception=exception,
            )
        
        # 401, 403 인증 에러
        if status_code in (401, 403):
            return ClassifiedError(
                category=ErrorCategory.TERMINAL,
                error_type="auth_error",
                message=error_msg,
                original_exception=exception,
            )
    
    # 네트워크/연결 에러 (재시도 가능)
    network_errors = (
        "ConnectionError", "TimeoutError", "ConnectTimeout",
        "ReadTimeout", "ConnectionRefusedError", "ConnectionResetError",
    )
    if error_type in network_errors or "connection" in error_msg.lower():
        return ClassifiedError(
            category=ErrorCategory.RETRYABLE,
            error_type="network_error",
            message=error_msg,
            original_exception=exception,
        )

    # [TERMINAL:xxx] 프리픽스가 있는 에러 - 재시도 의미 없음
    terminal_match = re.match(r"\[TERMINAL:(\w+)\]", error_msg)
    if terminal_match:
        terminal_type = terminal_match.group(1)
        return ClassifiedError(
            category=ErrorCategory.TERMINAL,
            error_type=terminal_type,
            message=error_msg,
            original_exception=exception,
        )

    # "No sections found" - 재시도 의미 없음 (레거시 호환)
    if "no sections found" in error_msg.lower():
        return ClassifiedError(
            category=ErrorCategory.TERMINAL,
            error_type="no_sections",
            message=error_msg,
            original_exception=exception,
        )

    # ValueError, TypeError 등 - 대부분 재시도 의미 없음
    if error_type in ("ValueError", "TypeError", "KeyError", "IndexError"):
        return ClassifiedError(
            category=ErrorCategory.TERMINAL,
            error_type="validation_error",
            message=error_msg,
            original_exception=exception,
        )
    
    # 기본: 알 수 없음 (안전하게 재시도 가능으로 처리)
    return ClassifiedError(
        category=ErrorCategory.UNKNOWN,
        error_type=error_type,
        message=error_msg,
        original_exception=exception,
    )


def _extract_retry_after(error_msg: str) -> Optional[int]:
    """에러 메시지에서 retry-after 값 추출 (ms)
    
    OpenAI 에러 메시지 형식: "Please try again in XXms" 또는 "Please retry after XXs"
    """
    # ms 단위
    match = re.search(r"try again in (\d+)ms", error_msg, re.IGNORECASE)
    if match:
        return int(match.group(1))
    
    # 초 단위
    match = re.search(r"retry after (\d+(?:\.\d+)?)s", error_msg, re.IGNORECASE)
    if match:
        return int(float(match.group(1)) * 1000)
    
    return None


# ─────────────────────────────────────────────────────────────
# 재시도 유틸리티
# ─────────────────────────────────────────────────────────────

def calculate_backoff(attempt: int, retry_after_ms: Optional[int] = None) -> float:
    """재시도 대기 시간 계산 (지수 백오프 + 지터)
    
    Args:
        attempt: 현재 시도 횟수 (0부터 시작)
        retry_after_ms: API에서 권장하는 대기 시간 (ms)
        
    Returns:
        대기 시간 (초)
    """
    # 기본 지수 백오프: 0.5s, 1s, 2s, 4s, 8s... (최대 30초)
    base = min(BASE_BACKOFF * (2 ** attempt), MAX_RETRY_DELAY)
    
    # API 권장 시간이 있으면 해당 값 사용
    if retry_after_ms:
        api_delay = retry_after_ms / 1000.0
        base = max(base, api_delay)
    
    # 최소 대기 시간 보장 (버스트 완화)
    base = max(base, MIN_RETRY_DELAY)
    
    # 지터 추가 (0~20%)
    jitter = random.uniform(0, JITTER_FACTOR * base)
    
    return base + jitter


async def async_sleep_with_backoff(attempt: int, retry_after_ms: Optional[int] = None) -> None:
    """비동기 백오프 대기"""
    delay = calculate_backoff(attempt, retry_after_ms)
    logger.debug("backoff_sleep", attempt=attempt, delay_seconds=delay)
    await asyncio.sleep(delay)


def sync_sleep_with_backoff(attempt: int, retry_after_ms: Optional[int] = None) -> None:
    """동기 백오프 대기"""
    delay = calculate_backoff(attempt, retry_after_ms)
    logger.debug("backoff_sleep", attempt=attempt, delay_seconds=delay)
    time.sleep(delay)


# ─────────────────────────────────────────────────────────────
# Token Budget Tracker
# ─────────────────────────────────────────────────────────────

@dataclass
class TokenBudget:
    """분당 토큰 예산 추적기
    
    슬라이딩 윈도우 방식으로 분당 토큰 사용량을 추적합니다.
    """
    tpm_limit: int = DEFAULT_TPM_LIMIT
    window_seconds: int = 60
    
    # 내부 상태
    _tokens_used: int = field(default=0, repr=False)
    _window_start: float = field(default_factory=time.time, repr=False)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock, repr=False)
    
    def _reset_if_needed(self) -> None:
        """윈도우가 만료되었으면 리셋"""
        now = time.time()
        if now - self._window_start >= self.window_seconds:
            self._tokens_used = 0
            self._window_start = now
    
    def remaining_tokens(self) -> int:
        """현재 윈도우에서 남은 토큰 수"""
        self._reset_if_needed()
        return max(0, self.tpm_limit - self._tokens_used)
    
    def can_request(self, tokens: int) -> bool:
        """요청 가능한지 확인"""
        return self.remaining_tokens() >= tokens
    
    def record_usage(self, tokens: int) -> None:
        """토큰 사용량 기록"""
        self._reset_if_needed()
        self._tokens_used += tokens
        logger.debug(
            "token_usage_recorded",
            tokens=tokens,
            total_used=self._tokens_used,
            remaining=self.remaining_tokens(),
        )
    
    async def wait_for_budget(self, tokens: int) -> None:
        """토큰 예산이 확보될 때까지 대기
        
        Args:
            tokens: 필요한 토큰 수
        """
        async with self._lock:
            while not self.can_request(tokens):
                # 남은 윈도우 시간 계산
                elapsed = time.time() - self._window_start
                wait_time = max(0.1, self.window_seconds - elapsed)
                
                logger.info(
                    "waiting_for_token_budget",
                    needed=tokens,
                    remaining=self.remaining_tokens(),
                    wait_seconds=wait_time,
                )
                await asyncio.sleep(wait_time)
                self._reset_if_needed()
    
    def estimate_tokens(self, text: str) -> int:
        """텍스트의 토큰 수 추정 (대략적)
        
        OpenAI 임베딩의 경우 대략 4자당 1토큰
        """
        return len(text) // 4 + 1
    
    def estimate_batch_tokens(self, texts: list[str]) -> int:
        """배치 텍스트의 총 토큰 수 추정"""
        return sum(self.estimate_tokens(t) for t in texts)


# ─────────────────────────────────────────────────────────────
# 통계
# ─────────────────────────────────────────────────────────────

@dataclass
class EmbeddingStats:
    """임베딩 API 호출 통계"""
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    total_retries: int = 0
    rate_limit_errors: int = 0
    server_errors: int = 0
    terminal_errors: int = 0
    total_tokens_used: int = 0
    
    def record_success(self, tokens: int = 0) -> None:
        self.total_requests += 1
        self.successful_requests += 1
        self.total_tokens_used += tokens
    
    def record_retry(self, error_type: str) -> None:
        self.total_retries += 1
        if error_type == "rate_limit":
            self.rate_limit_errors += 1
        elif error_type == "server_error":
            self.server_errors += 1
    
    def record_failure(self, error_type: str) -> None:
        self.total_requests += 1
        self.failed_requests += 1
        self.terminal_errors += 1
    
    def get_stats(self) -> dict:
        return {
            "total_requests": self.total_requests,
            "successful_requests": self.successful_requests,
            "failed_requests": self.failed_requests,
            "success_rate": (
                self.successful_requests / self.total_requests * 100
                if self.total_requests > 0 else 0
            ),
            "total_retries": self.total_retries,
            "rate_limit_errors": self.rate_limit_errors,
            "server_errors": self.server_errors,
            "terminal_errors": self.terminal_errors,
            "total_tokens_used": self.total_tokens_used,
        }


# 전역 통계 (싱글톤)
_global_stats: Optional[EmbeddingStats] = None


def get_embedding_stats() -> EmbeddingStats:
    """전역 임베딩 통계 반환"""
    global _global_stats
    if _global_stats is None:
        _global_stats = EmbeddingStats()
    return _global_stats
