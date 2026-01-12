"""임베딩 전략 모듈

텍스트를 벡터로 변환하는 전략들을 제공합니다.

사용 예시:
    from src.rag import get_embedder

    # OpenAI embedder
    embedder = get_embedder('openai_3small')
    vectors = embedder.embed_batch(texts)

    # PubMedBERT embedder (의생명 도메인)
    bio_embedder = get_embedder('pubmedbert_768')
    bio_vectors = bio_embedder.embed_batch(texts)
"""

from .openai import OpenAISmallEmbedder, OpenAILargeEmbedder
from .pubmedbert import PubMedBERTEmbedder, PubMedBERTLargeEmbedder

__all__ = [
    # OpenAI
    "OpenAISmallEmbedder",
    "OpenAILargeEmbedder",
    # PubMedBERT
    "PubMedBERTEmbedder",
    "PubMedBERTLargeEmbedder",
]
