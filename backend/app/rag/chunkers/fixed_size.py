"""고정 크기 문자 기반 청킹 전략

문자 수 기준으로 텍스트를 분할합니다.
섹션 경계를 고려하지 않는 단순 분할 방식입니다.
"""

from typing import Any
from app.rag.base import Chunk
from app.rag.registry import register_chunker


@register_chunker
class FixedChar1000Chunker:
    """고정 크기 문자 기반 청킹 (1000자 + 200자 오버랩)

    텍스트를 1000자 단위로 분할하고 200자씩 오버랩합니다.
    섹션 경계를 고려하지 않아 문맥이 끊길 수 있지만 처리가 빠릅니다.
    A/B 테스트에서 semantic 청킹과 비교할 때 baseline으로 사용합니다.

    파라미터:
    - chunk_size: 1000자 (청크 크기)
    - overlap: 200자 (오버랩)
    """

    name = "fixed_char_1000_200"

    def __init__(
        self,
        chunk_size: int = 1000,
        overlap: int = 200,
    ):
        """
        Args:
            chunk_size: 청크당 문자 수
            overlap: 청크 간 겹침 문자 수
        """
        if overlap >= chunk_size:
            raise ValueError("overlap은 chunk_size보다 작아야 합니다.")

        self.chunk_size = chunk_size
        self.overlap = overlap

    def chunk(self, text: str, **kwargs) -> list[Chunk]:
        """텍스트를 고정 크기로 분할

        Args:
            text: 분할할 텍스트

        Returns:
            청크 리스트
        """
        if not text:
            return []

        chunks = []
        start = 0
        index = 0
        step = self.chunk_size - self.overlap

        while start < len(text):
            end = min(start + self.chunk_size, len(text))
            content = text[start:end]

            chunks.append(Chunk(
                content=content,
                index=index,
                offset_start=start,
                offset_end=end,
                metadata={
                    "chunker": self.name,
                    "chunk_size": self.chunk_size,
                    "overlap": self.overlap,
                },
            ))

            start += step
            index += 1

        return chunks

    def get_config(self) -> dict[str, Any]:
        """현재 설정 반환"""
        return {
            "name": self.name,
            "chunk_size": self.chunk_size,
            "overlap": self.overlap,
        }
