"""임베딩 전략 모듈

텍스트를 벡터로 변환하는 전략들을 제공합니다.

사용 예시:
    from src.rag import get_embedder

    embedder = get_embedder('openai_3small')
    vectors = embedder.embed_batch(texts)
"""

from .openai import OpenAISmallEmbedder, OpenAILargeEmbedder

__all__ = [
    "OpenAISmallEmbedder",
    "OpenAILargeEmbedder",
]
