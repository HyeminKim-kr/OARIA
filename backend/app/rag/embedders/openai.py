"""OpenAI 임베딩 모델

기존 embedding_service를 래핑하여 모듈화된 인터페이스를 제공합니다.
"""

from typing import Any
from app.rag.registry import register_embedder
from app.services.embedding_service import embedding_service
from app.config import settings


@register_embedder
class OpenAI3SmallEmbedder:
    """OpenAI text-embedding-3-small (1536차원)

    범용 임베딩 모델로 의료/과학 논문에서도 좋은 성능을 보입니다.
    API 기반으로 GPU 없이 사용 가능하며, 빠른 응답 속도가 장점입니다.

    스펙:
    - 모델: text-embedding-3-small
    - 차원: 1536
    - 비용: $0.02/1M tokens
    - 최대 토큰: 8191
    """

    name = "openai_3small_1536d"

    def __init__(
        self,
        model: str | None = None,
        dimensions: int | None = None,
    ):
        """
        Args:
            model: OpenAI 모델명 (기본: settings에서 가져옴)
            dimensions: 벡터 차원 수 (기본: settings에서 가져옴)
        """
        self.model = model or settings.openai_embedding_model
        self.dimensions = dimensions or settings.openai_embedding_dimensions
        self._service = embedding_service

    def embed(self, text: str, **kwargs) -> list[float]:
        """단일 텍스트 임베딩"""
        return self._service.embed_text(text)

    def embed_batch(self, texts: list[str], **kwargs) -> list[list[float]]:
        """복수 텍스트 임베딩"""
        return self._service.embed_texts(texts)

    def get_config(self) -> dict[str, Any]:
        """현재 설정 반환"""
        return {
            "name": self.name,
            "model": self.model,
            "dimensions": self.dimensions,
            "use_mock": self._service.use_mock,
        }
