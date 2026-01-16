"""Embedding 모듈

OAR-31 기반: OpenAI 임베딩 + Weaviate 클라이언트
Rate Limit 처리: 지수 백오프 + 토큰 예산 쓰로틀링 (2026-01-15)
"""

from .embeddings import AsyncEmbeddingClient, EmbeddingClient, MockEmbeddingClient
from .client import WeaviateClient
from .schema import (
    COLLECTION_NAME,
    EMBEDDING_VERSION,
    generate_paper_id,
    generate_chunk_id,
    generate_uuid_from_chunk_id,
    create_paper_chunk_collection,
    delete_paper_chunk_collection,
    get_collection_info,
)
from .rate_limiter import (
    ErrorCategory,
    ClassifiedError,
    TokenBudget,
    EmbeddingStats,
    classify_error,
    get_embedding_stats,
)

__all__ = [
    # Embedding Clients
    "AsyncEmbeddingClient",
    "EmbeddingClient",
    "MockEmbeddingClient",
    # Weaviate
    "WeaviateClient",
    # Schema
    "COLLECTION_NAME",
    "EMBEDDING_VERSION",
    "generate_paper_id",
    "generate_chunk_id",
    "generate_uuid_from_chunk_id",
    "create_paper_chunk_collection",
    "delete_paper_chunk_collection",
    "get_collection_info",
    # Rate Limiting & Error Handling
    "ErrorCategory",
    "ClassifiedError",
    "TokenBudget",
    "EmbeddingStats",
    "classify_error",
    "get_embedding_stats",
]
