"""Batch RAG 모듈

논문 인덱싱 시 사용되는 청킹/임베딩 전략을 관리합니다.
Strategy Pattern + Registry Pattern으로 모듈화되어 있습니다.

사용 예시:
    from src.rag import get_chunker, get_embedder, list_chunkers, list_embedders

    # 청커 목록 조회
    print(list_chunkers())  # ['fixed_char_1000_200', 'semantic_section_700t']

    # 청커 인스턴스 가져오기
    chunker = get_chunker('fixed_char_1000_200')
    chunks = chunker.chunk(fulltext, sections=sections, paper_id=paper_id)

    # 임베더 인스턴스 가져오기
    embedder = get_embedder('openai_3small_1536d')
    vectors = embedder.embed_batch([c.embedding_text for c in chunks])
"""

from .registry import (
    # 청커
    get_chunker,
    list_chunkers,
    get_chunker_info,
    register_chunker,
    # 임베더
    get_embedder,
    list_embedders,
    get_embedder_info,
    register_embedder,
    # 전체 조회
    get_all_strategies,
    get_all_strategies_info,
)

from .base import Chunk, ChunkingResult

# chunkers, embedders 모듈 import (자동 등록)
from . import chunkers
from . import embedders

__all__ = [
    # 청커
    "get_chunker",
    "list_chunkers",
    "get_chunker_info",
    "register_chunker",
    # 임베더
    "get_embedder",
    "list_embedders",
    "get_embedder_info",
    "register_embedder",
    # 전체 조회
    "get_all_strategies",
    "get_all_strategies_info",
    # 타입
    "Chunk",
    "ChunkingResult",
]
