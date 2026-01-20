"""임베딩 생성 유틸리티

OpenAI text-embedding-3-small 모델 사용
"""

import hashlib
import os
import random
from typing import Optional


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
        """단일 텍스트 임베딩 생성

        Args:
            text: 임베딩할 텍스트

        Returns:
            임베딩 벡터 (float 리스트)
        """
        if self.use_mock:
            return self._mock.embed_text(text)

        response = self.client.embeddings.create(
            model=self.model,
            input=text,
            dimensions=self.dimensions,
        )
        return response.data[0].embedding

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """복수 텍스트 임베딩 생성 (배치)

        Args:
            texts: 임베딩할 텍스트 리스트

        Returns:
            임베딩 벡터 리스트
        """
        if not texts:
            return []

        if self.use_mock:
            return self._mock.embed_texts(texts)

        response = self.client.embeddings.create(
            model=self.model,
            input=texts,
            dimensions=self.dimensions,
        )

        # 입력 순서대로 정렬
        embeddings = [None] * len(texts)
        for item in response.data:
            embeddings[item.index] = item.embedding

        return embeddings

    def get_version_string(self) -> str:
        """임베딩 버전 문자열 반환"""
        if self.use_mock:
            return self._mock.get_version_string()
        return f"openai:{self.model}:v1"


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
