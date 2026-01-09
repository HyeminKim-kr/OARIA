"""OpenAI 임베딩 전략

OpenAI의 text-embedding-3 모델을 사용합니다.
"""

import os
from typing import Any, Optional

from openai import OpenAI

from ..registry import register_embedder


@register_embedder
class OpenAISmallEmbedder:
    """OpenAI text-embedding-3-small (1536차원)

    비용 효율적인 임베딩 모델입니다.
    대부분의 RAG 사용 케이스에 적합합니다.
    비용: $0.02 / 1M tokens

    파라미터:
    - model: text-embedding-3-small
    - dimension: 1536
    """

    name = "openai_3small"
    dimension = 1536

    def __init__(self, api_key: Optional[str] = None):
        """
        Args:
            api_key: OpenAI API 키 (없으면 환경변수에서 읽음)
        """
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.client = OpenAI(api_key=self.api_key)
        self.model = "text-embedding-3-small"

    def embed(self, text: str) -> list[float]:
        """단일 텍스트 임베딩"""
        response = self.client.embeddings.create(
            model=self.model,
            input=text,
        )
        return response.data[0].embedding

    def embed_batch(
        self,
        texts: list[str],
        batch_size: int = 100,
    ) -> list[list[float]]:
        """배치 텍스트 임베딩

        OpenAI API는 한 번에 최대 2048개까지 처리 가능합니다.
        안전을 위해 기본 batch_size는 100으로 설정합니다.
        """
        all_embeddings = []

        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]

            # 빈 텍스트 필터링
            non_empty_batch = [t if t.strip() else " " for t in batch]

            response = self.client.embeddings.create(
                model=self.model,
                input=non_empty_batch,
            )

            # 인덱스 순서대로 정렬
            sorted_embeddings = sorted(response.data, key=lambda x: x.index)
            all_embeddings.extend([e.embedding for e in sorted_embeddings])

        return all_embeddings

    def get_config(self) -> dict[str, Any]:
        """현재 설정 반환"""
        return {
            "name": self.name,
            "model": self.model,
            "dimension": self.dimension,
        }

    def get_version_string(self) -> str:
        """임베딩 버전 문자열 반환 (Weaviate 저장용)"""
        return f"openai:{self.model}:v1"


@register_embedder
class OpenAILargeEmbedder:
    """OpenAI text-embedding-3-large (3072차원)

    고품질 임베딩 모델입니다.
    더 정밀한 의미 표현이 필요한 경우 사용합니다.
    비용: $0.13 / 1M tokens (small 대비 6.5배)

    파라미터:
    - model: text-embedding-3-large
    - dimension: 3072
    """

    name = "openai_3large"
    dimension = 3072

    def __init__(self, api_key: Optional[str] = None):
        """
        Args:
            api_key: OpenAI API 키 (없으면 환경변수에서 읽음)
        """
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.client = OpenAI(api_key=self.api_key)
        self.model = "text-embedding-3-large"

    def embed(self, text: str) -> list[float]:
        """단일 텍스트 임베딩"""
        response = self.client.embeddings.create(
            model=self.model,
            input=text,
        )
        return response.data[0].embedding

    def embed_batch(
        self,
        texts: list[str],
        batch_size: int = 100,
    ) -> list[list[float]]:
        """배치 텍스트 임베딩"""
        all_embeddings = []

        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]

            # 빈 텍스트 필터링
            non_empty_batch = [t if t.strip() else " " for t in batch]

            response = self.client.embeddings.create(
                model=self.model,
                input=non_empty_batch,
            )

            # 인덱스 순서대로 정렬
            sorted_embeddings = sorted(response.data, key=lambda x: x.index)
            all_embeddings.extend([e.embedding for e in sorted_embeddings])

        return all_embeddings

    def get_config(self) -> dict[str, Any]:
        """현재 설정 반환"""
        return {
            "name": self.name,
            "model": self.model,
            "dimension": self.dimension,
        }

    def get_version_string(self) -> str:
        """임베딩 버전 문자열 반환 (Weaviate 저장용)"""
        return f"openai:{self.model}:v1"