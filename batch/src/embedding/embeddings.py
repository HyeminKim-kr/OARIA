"""임베딩 생성 유틸리티

OAR-31 기반: OpenAI text-embedding-3-small 모델 사용
Async 지원: AsyncEmbeddingClient 추가 (2026-01-15)
Rate Limit 처리: 지수 백오프 + 지터 추가 (2026-01-15)
"""

import asyncio
import hashlib
import os
import random
from typing import Optional

import structlog

from .rate_limiter import (
    MAX_RETRIES,
    TokenBudget,
    classify_error,
    ErrorCategory,
    async_sleep_with_backoff,
    sync_sleep_with_backoff,
    get_embedding_stats,
)

logger = structlog.get_logger(__name__)


# ─────────────────────────────────────────────────────────────
# 설정
# ─────────────────────────────────────────────────────────────

DEFAULT_MODEL = "text-embedding-3-small"
DEFAULT_DIMENSIONS = 1536  # text-embedding-3-small 기본 차원


class MockEmbeddingClient:
    """테스트용 Mock 임베딩 클라이언트 (결정적 랜덤 벡터)"""

    def __init__(self, dimensions: int = DEFAULT_DIMENSIONS):
        self.dimensions = dimensions

    def embed_text(self, text: str) -> list[float]:
        """텍스트를 해시하여 결정적 임베딩 생성"""
        # 텍스트 해시를 시드로 사용 (같은 텍스트 → 같은 벡터)
        seed = int(hashlib.md5(text.encode()).hexdigest(), 16) % (2**32)
        rng = random.Random(seed)
        return [rng.gauss(0, 1) for _ in range(self.dimensions)]

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [self.embed_text(t) for t in texts]

    def get_version_string(self) -> str:
        return "mock:random:v1"


class EmbeddingClient:
    """OpenAI 임베딩 클라이언트"""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = DEFAULT_MODEL,
        dimensions: int = DEFAULT_DIMENSIONS,
        use_mock: bool = False,
    ):
        """
        Args:
            api_key: OpenAI API 키 (None이면 환경변수에서 읽음)
            model: 임베딩 모델명
            dimensions: 임베딩 차원 수
            use_mock: True면 Mock 클라이언트 사용 (테스트용)
        """
        self.dimensions = dimensions
        self.model = model
        self.use_mock = use_mock

        if use_mock:
            self._mock = MockEmbeddingClient(dimensions)
            self.client = None
        else:
            api_key = api_key or os.getenv("OPENAI_API_KEY")
            if not api_key:
                print("⚠️ OPENAI_API_KEY가 없습니다. Mock 모드로 전환합니다.")
                self._mock = MockEmbeddingClient(dimensions)
                self.use_mock = True
                self.client = None
            else:
                from openai import OpenAI
                self.client = OpenAI(api_key=api_key)
                self._mock = None

    def embed_text(self, text: str) -> list[float]:
        """단일 텍스트 임베딩 생성 (재시도 로직 포함)

        Args:
            text: 임베딩할 텍스트

        Returns:
            임베딩 벡터 (float 리스트)

        Raises:
            Exception: MAX_RETRIES 초과 시 마지막 에러 발생
        """
        if self.use_mock:
            return self._mock.embed_text(text)

        stats = get_embedding_stats()
        last_error = None

        for attempt in range(MAX_RETRIES):
            try:
                response = self.client.embeddings.create(
                    model=self.model,
                    input=text,
                    dimensions=self.dimensions,
                )
                # 성공 시 토큰 사용량 기록
                tokens = response.usage.total_tokens if hasattr(response, 'usage') else 0
                stats.record_success(tokens)
                return response.data[0].embedding

            except Exception as e:
                last_error = e
                classified = classify_error(e)

                # Terminal 에러는 재시도하지 않음
                if classified.category == ErrorCategory.TERMINAL:
                    logger.warning(
                        "embedding_terminal_error",
                        error_type=classified.error_type,
                        message=classified.message[:200],
                    )
                    stats.record_failure(classified.error_type)
                    raise

                # Retryable 에러는 백오프 후 재시도
                if attempt < MAX_RETRIES - 1:
                    stats.record_retry(classified.error_type)
                    logger.warning(
                        "embedding_retry",
                        attempt=attempt + 1,
                        max_retries=MAX_RETRIES,
                        error_type=classified.error_type,
                        retry_after_ms=classified.retry_after_ms,
                    )
                    sync_sleep_with_backoff(attempt, classified.retry_after_ms)

        # 모든 재시도 실패
        stats.record_failure("max_retries_exceeded")
        logger.error("embedding_max_retries_exceeded", attempts=MAX_RETRIES)
        raise last_error

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """복수 텍스트 임베딩 생성 (배치, 재시도 로직 포함)

        Args:
            texts: 임베딩할 텍스트 리스트

        Returns:
            임베딩 벡터 리스트

        Raises:
            Exception: MAX_RETRIES 초과 시 마지막 에러 발생
        """
        if not texts:
            return []

        if self.use_mock:
            return self._mock.embed_texts(texts)

        stats = get_embedding_stats()
        last_error = None

        for attempt in range(MAX_RETRIES):
            try:
                response = self.client.embeddings.create(
                    model=self.model,
                    input=texts,
                    dimensions=self.dimensions,
                )

                # 성공 시 토큰 사용량 기록
                tokens = response.usage.total_tokens if hasattr(response, 'usage') else 0
                stats.record_success(tokens)

                # 입력 순서대로 정렬
                embeddings = [None] * len(texts)
                for item in response.data:
                    embeddings[item.index] = item.embedding

                return embeddings

            except Exception as e:
                last_error = e
                classified = classify_error(e)

                # Terminal 에러는 재시도하지 않음
                if classified.category == ErrorCategory.TERMINAL:
                    logger.warning(
                        "embedding_batch_terminal_error",
                        error_type=classified.error_type,
                        message=classified.message[:200],
                        batch_size=len(texts),
                    )
                    stats.record_failure(classified.error_type)
                    raise

                # Retryable 에러는 백오프 후 재시도
                if attempt < MAX_RETRIES - 1:
                    stats.record_retry(classified.error_type)
                    logger.warning(
                        "embedding_batch_retry",
                        attempt=attempt + 1,
                        max_retries=MAX_RETRIES,
                        error_type=classified.error_type,
                        retry_after_ms=classified.retry_after_ms,
                        batch_size=len(texts),
                    )
                    sync_sleep_with_backoff(attempt, classified.retry_after_ms)

        # 모든 재시도 실패
        stats.record_failure("max_retries_exceeded")
        logger.error("embedding_batch_max_retries_exceeded", attempts=MAX_RETRIES, batch_size=len(texts))
        raise last_error

    def get_version_string(self) -> str:
        """임베딩 버전 문자열 반환"""
        if self.use_mock:
            return self._mock.get_version_string()
        return f"openai:{self.model}:v1"


class AsyncEmbeddingClient:
    """비동기 OpenAI 임베딩 클라이언트

    ThreadPoolExecutor 대신 asyncio.gather()와 함께 사용하여
    I/O 바운드 작업의 병렬성을 극대화합니다.

    특징:
    - 429 에러 시 지수 백오프 + 지터로 재시도
    - 토큰 예산 기반 쓰로틀링 (TPM 한도 관리)
    - 에러 분류 (retryable vs terminal)
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = DEFAULT_MODEL,
        dimensions: int = DEFAULT_DIMENSIONS,
        use_mock: bool = False,
        use_token_budget: bool = True,
        tpm_limit: int = 1_000_000,
    ):
        """
        Args:
            api_key: OpenAI API 키 (None이면 환경변수에서 읽음)
            model: 임베딩 모델명
            dimensions: 임베딩 차원 수
            use_mock: True면 Mock 클라이언트 사용 (테스트용)
            use_token_budget: 토큰 예산 쓰로틀링 사용 여부
            tpm_limit: 분당 토큰 한도 (기본값: 1,000,000)
        """
        self.dimensions = dimensions
        self.model = model
        self.use_mock = use_mock

        # 토큰 예산 추적기
        self._token_budget: Optional[TokenBudget] = None
        if use_token_budget and not use_mock:
            self._token_budget = TokenBudget(tpm_limit=tpm_limit)

        if use_mock:
            self._mock = MockEmbeddingClient(dimensions)
            self._client = None
        else:
            api_key = api_key or os.getenv("OPENAI_API_KEY")
            if not api_key:
                print("⚠️ OPENAI_API_KEY가 없습니다. Mock 모드로 전환합니다.")
                self._mock = MockEmbeddingClient(dimensions)
                self.use_mock = True
                self._client = None
                self._token_budget = None
            else:
                from openai import AsyncOpenAI

                self._client = AsyncOpenAI(api_key=api_key)
                self._mock = None

    async def embed_text(self, text: str) -> list[float]:
        """비동기 단일 텍스트 임베딩 생성 (재시도 로직 + 토큰 예산 포함)

        Args:
            text: 임베딩할 텍스트

        Returns:
            임베딩 벡터 (float 리스트)

        Raises:
            Exception: MAX_RETRIES 초과 시 마지막 에러 발생
        """
        if self.use_mock:
            return self._mock.embed_text(text)

        stats = get_embedding_stats()

        # 토큰 예산 확인 (대기)
        if self._token_budget:
            estimated_tokens = self._token_budget.estimate_tokens(text)
            await self._token_budget.wait_for_budget(estimated_tokens)

        last_error = None

        for attempt in range(MAX_RETRIES):
            try:
                response = await self._client.embeddings.create(
                    model=self.model,
                    input=text,
                    dimensions=self.dimensions,
                )

                # 성공 시 토큰 사용량 기록
                tokens = response.usage.total_tokens if hasattr(response, 'usage') else 0
                stats.record_success(tokens)
                if self._token_budget:
                    self._token_budget.record_usage(tokens)

                return response.data[0].embedding

            except Exception as e:
                last_error = e
                classified = classify_error(e)

                # Terminal 에러는 재시도하지 않음
                if classified.category == ErrorCategory.TERMINAL:
                    logger.warning(
                        "async_embedding_terminal_error",
                        error_type=classified.error_type,
                        message=classified.message[:200],
                    )
                    stats.record_failure(classified.error_type)
                    raise

                # Retryable 에러는 백오프 후 재시도
                if attempt < MAX_RETRIES - 1:
                    stats.record_retry(classified.error_type)
                    logger.warning(
                        "async_embedding_retry",
                        attempt=attempt + 1,
                        max_retries=MAX_RETRIES,
                        error_type=classified.error_type,
                        retry_after_ms=classified.retry_after_ms,
                    )
                    await async_sleep_with_backoff(attempt, classified.retry_after_ms)

        # 모든 재시도 실패
        stats.record_failure("max_retries_exceeded")
        logger.error("async_embedding_max_retries_exceeded", attempts=MAX_RETRIES)
        raise last_error

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """비동기 복수 텍스트 임베딩 생성 (배치, 재시도 로직 + 토큰 예산 포함)

        Args:
            texts: 임베딩할 텍스트 리스트

        Returns:
            임베딩 벡터 리스트

        Raises:
            Exception: MAX_RETRIES 초과 시 마지막 에러 발생
        """
        if not texts:
            return []

        if self.use_mock:
            return self._mock.embed_texts(texts)

        stats = get_embedding_stats()

        # 토큰 예산 확인 (대기)
        if self._token_budget:
            estimated_tokens = self._token_budget.estimate_batch_tokens(texts)
            await self._token_budget.wait_for_budget(estimated_tokens)

        last_error = None

        for attempt in range(MAX_RETRIES):
            try:
                response = await self._client.embeddings.create(
                    model=self.model,
                    input=texts,
                    dimensions=self.dimensions,
                )

                # 성공 시 토큰 사용량 기록
                tokens = response.usage.total_tokens if hasattr(response, 'usage') else 0
                stats.record_success(tokens)
                if self._token_budget:
                    self._token_budget.record_usage(tokens)

                # 입력 순서대로 정렬
                embeddings = [None] * len(texts)
                for item in response.data:
                    embeddings[item.index] = item.embedding

                return embeddings

            except Exception as e:
                last_error = e
                classified = classify_error(e)

                # Terminal 에러는 재시도하지 않음
                if classified.category == ErrorCategory.TERMINAL:
                    logger.warning(
                        "async_embedding_batch_terminal_error",
                        error_type=classified.error_type,
                        message=classified.message[:200],
                        batch_size=len(texts),
                    )
                    stats.record_failure(classified.error_type)
                    raise

                # Retryable 에러는 백오프 후 재시도
                if attempt < MAX_RETRIES - 1:
                    stats.record_retry(classified.error_type)
                    logger.warning(
                        "async_embedding_batch_retry",
                        attempt=attempt + 1,
                        max_retries=MAX_RETRIES,
                        error_type=classified.error_type,
                        retry_after_ms=classified.retry_after_ms,
                        batch_size=len(texts),
                    )
                    await async_sleep_with_backoff(attempt, classified.retry_after_ms)

        # 모든 재시도 실패
        stats.record_failure("max_retries_exceeded")
        logger.error("async_embedding_batch_max_retries_exceeded", attempts=MAX_RETRIES, batch_size=len(texts))
        raise last_error

    def get_version_string(self) -> str:
        """임베딩 버전 문자열 반환"""
        if self.use_mock:
            return self._mock.get_version_string()
        return f"openai:{self.model}:v1"

    async def close(self) -> None:
        """클라이언트 리소스 정리"""
        if self._client is not None:
            await self._client.close()


# ─────────────────────────────────────────────────────────────
# 편의 함수
# ─────────────────────────────────────────────────────────────

_default_client: Optional[EmbeddingClient] = None


def get_default_client() -> EmbeddingClient:
    """기본 임베딩 클라이언트 반환 (싱글톤)"""
    global _default_client
    if _default_client is None:
        _default_client = EmbeddingClient()
    return _default_client


def embed(text: str) -> list[float]:
    """텍스트 임베딩 생성 (편의 함수)"""
    return get_default_client().embed_text(text)


def embed_batch(texts: list[str]) -> list[list[float]]:
    """복수 텍스트 임베딩 생성 (편의 함수)"""
    return get_default_client().embed_texts(texts)
