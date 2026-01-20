"""청킹 전략 모듈

사용 가능한 전략:
- semantic_section_700t: 섹션 기반 시맨틱 청킹 (700토큰, 프로덕션 사용)
- fixed_char_1000_200: 고정 크기 문자 기반 청킹 (1000자 + 200 오버랩)
"""

from .base import ChunkerProtocol
from .fixed_size import FixedChar1000Chunker
from .semantic import SemanticSection700tChunker

__all__ = [
    "ChunkerProtocol",
    "FixedChar1000Chunker",
    "SemanticSection700tChunker",
]
