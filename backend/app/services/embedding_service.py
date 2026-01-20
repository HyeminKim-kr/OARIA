"""임베딩 서비스

OpenAI text-embedding-3-small 모델 사용
비동기 지원: AsyncOpenAI 사용 (2026-01-15)
"""

import hashlib
import random

from openai import AsyncOpenAI

from app.config import settings


class EmbeddingService:
    """비동기 OpenAI 임베딩 서비스"""

    _instance: "EmbeddingService | None" = None
    _client: AsyncOpenAI | None = None

    def __new__(cls) -> "EmbeddingService":
        """싱글톤 패턴"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def _get_client(self) -> AsyncOpenAI | None:
        """AsyncOpenAI 클라이언트 반환 (지연 초기화)"""
        if self._client is None and settings.openai_api_key:
            self._client = AsyncOpenAI(api_key=settings.openai_api_key)
        return self._client

    @property
    def use_mock(self) -> bool:
        """Mock 모드 여부"""
        return not settings.openai_api_key

    async def embed_text(self, text: str) -> list[float]:
        """비동기 단일 텍스트 임베딩 생성

        Args:
            text: 임베딩할 텍스트

        Returns:
            임베딩 벡터
        """
        if self.use_mock:
            return self._mock_embed(text)

        client = self._get_client()
        response = await client.embeddings.create(
            model=settings.openai_embedding_model,
            input=text,
            dimensions=settings.openai_embedding_dimensions,
        )
        return response.data[0].embedding

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """비동기 복수 텍스트 임베딩 생성

        Args:
            texts: 임베딩할 텍스트 리스트

        Returns:
            임베딩 벡터 리스트
        """
        if not texts:
            return []

        if self.use_mock:
            return [self._mock_embed(t) for t in texts]

        client = self._get_client()
        response = await client.embeddings.create(
            model=settings.openai_embedding_model,
            input=texts,
            dimensions=settings.openai_embedding_dimensions,
        )

        # 입력 순서대로 정렬
        embeddings = [None] * len(texts)
        for item in response.data:
            embeddings[item.index] = item.embedding

        return embeddings

    def _mock_embed(self, text: str) -> list[float]:
        """Mock 임베딩 (테스트용)"""
        seed = int(hashlib.md5(text.encode()).hexdigest(), 16) % (2**32)
        rng = random.Random(seed)
        return [rng.gauss(0, 1) for _ in range(settings.openai_embedding_dimensions)]


# 싱글톤 인스턴스
embedding_service = EmbeddingService()


def get_embedding_service() -> EmbeddingService:
    """임베딩 서비스 의존성"""
    return embedding_service
