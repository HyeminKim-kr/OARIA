"""고정 크기 문자 기반 청킹 전략

문자 수 기준으로 텍스트를 분할합니다.
섹션 경계를 고려하지 않는 단순 분할 방식입니다.
"""

import hashlib
from typing import Any, Optional

from ..registry import register_chunker
from ..base import Chunk, ChunkingResult, Section


@register_chunker
class FixedCharChunker:
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

    def chunk(
        self,
        fulltext: str,
        sections: list[dict],
        paper_id: str,
        title: str,
        year: Optional[int] = None,
    ) -> ChunkingResult:
        """텍스트를 고정 크기로 분할

        Args:
            fulltext: 논문 전체 텍스트
            sections: 섹션 정보 리스트
            paper_id: 논문 ID
            title: 논문 제목
            year: 출판 연도

        Returns:
            ChunkingResult
        """
        if not fulltext:
            return ChunkingResult(
                paper_id=paper_id,
                title=title,
                fulltext="",
                fulltext_hash="",
                sections=[],
                chunks=[],
                chunker_name=self.name,
                chunker_config=self.get_config(),
            )

        fulltext_hash = hashlib.sha256(fulltext.encode()).hexdigest()

        # 섹션 객체 생성
        section_objects = []
        for sec in sections:
            section_objects.append(
                Section(
                    name=sec["name"],
                    title=sec.get("title", sec["name"].title()),
                    offset_start=sec["offset_start"],
                    offset_end=sec["offset_end"],
                )
            )

        # 고정 크기로 분할
        chunks = []
        start = 0
        index = 0
        step = self.chunk_size - self.overlap
        year_str = str(year) if year else "Unknown"

        while start < len(fulltext):
            end = min(start + self.chunk_size, len(fulltext))
            chunk_text = fulltext[start:end]

            # 해당 위치의 섹션 찾기
            section_name = self._find_section(start, sections)

            # chunk_id 생성
            chunk_id = f"{paper_id}|{section_name}|{index}"

            # 임베딩용 텍스트 (컨텍스트 포함)
            embedding_text = f"""[TITLE] {title}
[SECTION] {section_name}
[YEAR] {year_str}
[TEXT] {chunk_text}"""

            chunks.append(
                Chunk(
                    chunk_id=chunk_id,
                    paper_id=paper_id,
                    section=section_name,
                    chunk_index=index,
                    offset_start=start,
                    offset_end=end,
                    text=chunk_text,
                    embedding_text=embedding_text,
                    char_count=len(chunk_text),
                    metadata={
                        "chunker": self.name,
                        "chunk_size": self.chunk_size,
                        "overlap": self.overlap,
                    },
                )
            )

            start += step
            index += 1

        # 통계 계산
        total_chars = sum(c.char_count for c in chunks)
        avg_chars = total_chars / len(chunks) if chunks else 0

        return ChunkingResult(
            paper_id=paper_id,
            title=title,
            fulltext=fulltext,
            fulltext_hash=fulltext_hash,
            sections=section_objects,
            chunks=chunks,
            total_chars=len(fulltext),
            avg_chunk_tokens=avg_chars / 4,  # 대략적인 토큰 수 추정
            chunker_name=self.name,
            chunker_config=self.get_config(),
        )

    def _find_section(self, offset: int, sections: list[dict]) -> str:
        """주어진 offset이 속한 섹션 이름 반환"""
        for sec in sections:
            if sec["offset_start"] <= offset < sec["offset_end"]:
                return sec["name"]
        return "unknown"

    def get_config(self) -> dict[str, Any]:
        """현재 설정 반환"""
        return {
            "name": self.name,
            "chunk_size": self.chunk_size,
            "overlap": self.overlap,
        }
