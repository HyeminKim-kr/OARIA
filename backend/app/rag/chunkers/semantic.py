"""섹션 기반 시맨틱 청킹 전략

실제 인덱싱에 사용된 청킹 방식을 설명합니다.
(인덱싱 시점에 결정되어 검색 시 변경 불가)
"""

from typing import Any
from app.rag.base import Chunk
from app.rag.registry import register_chunker


@register_chunker
class SemanticSection700tChunker:
    """섹션 기반 시맨틱 청킹 (700토큰, Recursive)

    논문의 섹션 구조(Abstract, Methods, Results 등)를 존중합니다.
    섹션 내에서 700토큰을 초과하면 문단 > 줄바꿈 > 문장 순으로 분할합니다.
    섹션 경계에서 문맥이 끊기지 않아 검색 품질이 높습니다.

    인덱싱 시 사용된 설정:
    - 목표 청크 크기: 700 토큰
    - 오버랩: 100 토큰 (embedding_input에만 적용)
    - 분할 우선순위: 문단(\\n\\n) > 줄바꿈(\\n) > 문장(. ) > 공백
    """

    name = "semantic_section_700t"

    def __init__(
        self,
        chunk_size_tokens: int = 700,
        overlap_tokens: int = 100,
    ):
        """
        Args:
            chunk_size_tokens: 청크당 목표 토큰 수
            overlap_tokens: 오버랩 토큰 수
        """
        self.chunk_size_tokens = chunk_size_tokens
        self.overlap_tokens = overlap_tokens

    def chunk(self, text: str, **kwargs) -> list[Chunk]:
        """텍스트를 시맨틱하게 분할

        Note:
            실제 청킹은 batch 서비스의 TextChunker에서 수행됩니다.
            이 메서드는 인터페이스 호환성을 위해 존재합니다.

        Args:
            text: 분할할 텍스트

        Returns:
            청크 리스트
        """
        # 실제 인덱싱은 batch/src/chunker/chunker.py의 TextChunker가 수행
        # 이 클래스는 설명/설정 정보 제공용
        raise NotImplementedError(
            "SemanticSection700tChunker는 인덱싱 시점 설정 정보 제공용입니다. "
            "실제 청킹은 batch 서비스의 TextChunker를 사용하세요."
        )

    def get_config(self) -> dict[str, Any]:
        """현재 설정 반환"""
        return {
            "name": self.name,
            "chunk_size_tokens": self.chunk_size_tokens,
            "overlap_tokens": self.overlap_tokens,
            "strategy": "recursive_section_based",
            "separators": ["\\n\\n", "\\n", ". ", " "],
        }
