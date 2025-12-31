"""Embedding 모듈

OAR-31 기반: OpenAI 임베딩 + Weaviate 클라이언트
"""

from .embeddings import EmbeddingClient, MockEmbeddingClient
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

__all__ = [
    "EmbeddingClient",
    "MockEmbeddingClient",
    "WeaviateClient",
    "COLLECTION_NAME",
    "EMBEDDING_VERSION",
    "generate_paper_id",
    "generate_chunk_id",
    "generate_uuid_from_chunk_id",
    "create_paper_chunk_collection",
    "delete_paper_chunk_collection",
    "get_collection_info",
]
