"""섹션 기반 시맨틱 청킹 전략

논문의 섹션 구조를 존중하며 Recursive Character Text Splitter 방식으로 분할합니다.
기존 batch/src/chunker/chunker.py의 TextChunker를 리팩토링한 버전입니다.
"""

import hashlib
from typing import Any, Optional

import tiktoken

from ..registry import register_chunker
from ..base import Chunk, ChunkingResult, Section


@register_chunker
class SemanticSectionChunker:
    """섹션 기반 시맨틱 청킹 (700토큰, Recursive)

    논문의 섹션 구조(Abstract, Methods, Results 등)를 존중합니다.
    섹션 내에서 700토큰을 초과하면 문단 > 줄바꿈 > 문장 순으로 분할합니다.
    섹션 경계에서 문맥이 끊기지 않아 검색 품질이 높습니다.

    파라미터:
    - chunk_size_tokens: 700 (목표 청크 크기)
    - overlap_tokens: 100 (오버랩)
    - separators: ["\\n\\n", "\\n", ". ", " "]
    """

    name = "semantic_section_700t"

    def __init__(
        self,
        chunk_size_tokens: int = 700,
        chunk_overlap_tokens: int = 100,
        min_chunk_tokens: int = 50,
        encoding_name: str = "cl100k_base",
    ):
        """
        Args:
            chunk_size_tokens: 목표 청크 크기 (토큰)
            chunk_overlap_tokens: 오버랩 크기 (토큰)
            min_chunk_tokens: 최소 청크 크기 (이보다 작으면 이전 청크에 병합)
            encoding_name: tiktoken 인코딩 이름
        """
        self.chunk_size_tokens = chunk_size_tokens
        self.chunk_overlap_tokens = chunk_overlap_tokens
        self.min_chunk_tokens = min_chunk_tokens
        self.encoding = tiktoken.get_encoding(encoding_name)

        # 분할 우선순위: 문단 > 줄바꿈 > 문장 > 공백
        self.separators = ["\n\n", "\n", ". ", " "]

    def count_tokens(self, text: str) -> int:
        """토큰 수 계산"""
        return len(self.encoding.encode(text))

    def chunk(
        self,
        fulltext: str,
        sections: list[dict],
        paper_id: str,
        title: str,
        year: Optional[int] = None,
    ) -> ChunkingResult:
        """논문 전체 청킹

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

        # 섹션별 청킹
        all_chunks = []
        for section in section_objects:
            section_text = fulltext[section.offset_start:section.offset_end]
            section_chunks = self._chunk_section(
                paper_id=paper_id,
                title=title,
                year=year,
                section=section,
                section_text=section_text,
                fulltext=fulltext,
            )
            all_chunks.extend(section_chunks)

        # 통계 계산
        total_tokens = sum(c.token_count for c in all_chunks)
        avg_tokens = total_tokens / len(all_chunks) if all_chunks else 0

        return ChunkingResult(
            paper_id=paper_id,
            title=title,
            fulltext=fulltext,
            fulltext_hash=fulltext_hash,
            sections=section_objects,
            chunks=all_chunks,
            total_chars=len(fulltext),
            total_tokens=total_tokens,
            avg_chunk_tokens=avg_tokens,
            chunker_name=self.name,
            chunker_config=self.get_config(),
        )

    def _chunk_section(
        self,
        paper_id: str,
        title: str,
        year: Optional[int],
        section: Section,
        section_text: str,
        fulltext: str,
    ) -> list[Chunk]:
        """섹션 내 청킹"""
        chunks = []

        # 빈 섹션 처리
        if not section_text.strip():
            return []

        # 섹션이 충분히 작으면 그대로 반환
        if self.count_tokens(section_text) <= self.chunk_size_tokens:
            chunk = self._create_chunk(
                paper_id=paper_id,
                title=title,
                year=year,
                section=section,
                chunk_index=0,
                chunk_text=section_text,
                offset_in_section=0,
                fulltext=fulltext,
            )
            return [chunk]

        # Recursive splitting
        split_texts = self._recursive_split(section_text, 0)

        # 청크 생성
        current_offset = 0
        for idx, chunk_text in enumerate(split_texts):
            # 원본 텍스트에서 위치 찾기
            pos = section_text.find(chunk_text, current_offset)
            if pos == -1:
                pos = section_text.find(chunk_text)
            if pos == -1:
                pos = current_offset

            chunk = self._create_chunk(
                paper_id=paper_id,
                title=title,
                year=year,
                section=section,
                chunk_index=idx,
                chunk_text=chunk_text,
                offset_in_section=pos,
                fulltext=fulltext,
            )
            chunks.append(chunk)

            if pos != -1:
                current_offset = pos + len(chunk_text)

        return chunks

    def _recursive_split(self, text: str, separator_idx: int) -> list[str]:
        """재귀적으로 텍스트 분할"""
        if separator_idx >= len(self.separators):
            return self._force_split(text)

        separator = self.separators[separator_idx]
        splits = text.split(separator)

        if len(splits) == 1:
            return self._recursive_split(text, separator_idx + 1)

        chunks = []
        current_chunk = ""

        for i, split in enumerate(splits):
            if i < len(splits) - 1:
                split_with_sep = split + separator
            else:
                split_with_sep = split

            test_chunk = current_chunk + split_with_sep
            test_tokens = self.count_tokens(test_chunk)

            if test_tokens <= self.chunk_size_tokens:
                current_chunk = test_chunk
            else:
                if current_chunk.strip():
                    if self.count_tokens(current_chunk) > self.chunk_size_tokens:
                        sub_chunks = self._recursive_split(current_chunk, separator_idx + 1)
                        chunks.extend(sub_chunks)
                    else:
                        chunks.append(current_chunk)

                if self.count_tokens(split_with_sep) > self.chunk_size_tokens:
                    sub_chunks = self._recursive_split(split_with_sep, separator_idx + 1)
                    if sub_chunks:
                        chunks.extend(sub_chunks[:-1])
                        current_chunk = sub_chunks[-1]
                    else:
                        current_chunk = ""
                else:
                    current_chunk = split_with_sep

        if current_chunk.strip():
            if self.count_tokens(current_chunk) > self.chunk_size_tokens:
                sub_chunks = self._recursive_split(current_chunk, separator_idx + 1)
                chunks.extend(sub_chunks)
            else:
                chunks.append(current_chunk)

        return chunks

    def _force_split(self, text: str) -> list[str]:
        """강제 분할 (문자 단위)"""
        chunks = []
        chars_per_chunk = self.chunk_size_tokens * 4

        start = 0
        while start < len(text):
            end = min(start + chars_per_chunk, len(text))
            chunks.append(text[start:end])
            start = end

        return chunks

    def _create_chunk(
        self,
        paper_id: str,
        title: str,
        year: Optional[int],
        section: Section,
        chunk_index: int,
        chunk_text: str,
        offset_in_section: int,
        fulltext: str,
    ) -> Chunk:
        """Chunk 객체 생성"""
        # 전역 offset 계산
        offset_start = section.offset_start + offset_in_section
        offset_end = offset_start + len(chunk_text)

        # chunk_id 생성
        chunk_id = f"{paper_id}|{section.name}|{chunk_index}"

        # 토큰 수
        token_count = self.count_tokens(chunk_text)

        # 오버랩 컨텍스트 생성 (embedding_text용)
        overlap_chars = self.chunk_overlap_tokens * 4
        overlap_start = max(section.offset_start, offset_start - overlap_chars)
        text_with_overlap = fulltext[overlap_start:offset_end]

        # Contextual embedding input
        year_str = str(year) if year else "Unknown"
        embedding_text = f"""[TITLE] {title}
[SECTION] {section.name}
[YEAR] {year_str}
[TEXT] {text_with_overlap}"""

        return Chunk(
            chunk_id=chunk_id,
            paper_id=paper_id,
            section=section.name,
            chunk_index=chunk_index,
            offset_start=offset_start,
            offset_end=offset_end,
            text=chunk_text,
            embedding_text=embedding_text,
            token_count=token_count,
            char_count=len(chunk_text),
            section_offset_start=section.offset_start,
            section_offset_end=section.offset_end,
            metadata={
                "chunker": self.name,
                "chunk_size_tokens": self.chunk_size_tokens,
                "overlap_tokens": self.chunk_overlap_tokens,
            },
        )

    def get_config(self) -> dict[str, Any]:
        """현재 설정 반환"""
        return {
            "name": self.name,
            "chunk_size_tokens": self.chunk_size_tokens,
            "chunk_overlap_tokens": self.chunk_overlap_tokens,
            "min_chunk_tokens": self.min_chunk_tokens,
        }
