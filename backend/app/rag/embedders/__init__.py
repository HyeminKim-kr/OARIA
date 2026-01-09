"""임베딩 모델 모듈

사용 가능한 모델:
- openai_3small_1536d: OpenAI text-embedding-3-small (1536차원, 프로덕션 사용)
- pubmedbert: PubMedBERT (TODO)
- bge: BGE-M3 (TODO)
"""

from .base import EmbedderProtocol
from .openai import OpenAI3SmallEmbedder

__all__ = [
    "EmbedderProtocol",
    "OpenAI3SmallEmbedder",
]
