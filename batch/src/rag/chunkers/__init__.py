"""청킹 전략 모듈

논문 텍스트를 청크로 분할하는 전략들을 제공합니다.

사용 예시:
    from src.rag import get_chunker

    chunker = get_chunker('fixed_char_1000_200')
    result = chunker.chunk(
        fulltext=paper_fulltext,
        sections=sections,
        paper_id="pmid:12345678",
        title="Paper Title",
        year=2024,
    )

    for chunk in result.chunks:
        print(chunk.chunk_id, chunk.text[:100])
"""

from .fixed_char import FixedCharChunker
from .semantic import SemanticSectionChunker

__all__ = [
    "FixedCharChunker",
    "SemanticSectionChunker",
]
