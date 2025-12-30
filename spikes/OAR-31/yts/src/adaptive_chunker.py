"""적응형 청커 (Adaptive Chunker)

OAR-31 A/B 테스트: 섹션 크기 기반 적응형 청킹 전략

Strategy A (baseline): 모든 섹션을 700토큰 단위로 분할
Strategy B (adaptive): 섹션 크기에 따라 적응
  - 800토큰 이하: 섹션 그대로 (의미적 완결성 유지)
  - 800토큰 초과: 700토큰 단위로 분할
"""

import hashlib
from dataclasses import dataclass
from enum import Enum
from typing import Optional

import tiktoken


class ChunkingStrategy(Enum):
    """청킹 전략"""
    FIXED = "fixed"      # Strategy A: 고정 크기 분할
    ADAPTIVE = "adaptive"  # Strategy B: 섹션 크기 기반 적응형


@dataclass
class Chunk:
    """청크 데이터"""
    chunk_id: str
    paper_id: str
    section: str
    chunk_index: int
    text: str
    offset_start: int
    offset_end: int
    token_count: int
    strategy: str  # 'fixed' or 'adaptive'

    # 임베딩용 입력
    embedding_input: str = ""


@dataclass
class Section:
    """섹션 정보"""
    name: str
    title: str
    text: str
    offset_start: int
    offset_end: int


@dataclass
class ChunkingResult:
    """청킹 결과"""
    paper_id: str
    title: str
    strategy: ChunkingStrategy
    chunks: list[Chunk]

    # 통계
    total_sections: int = 0
    preserved_sections: int = 0  # 분할 없이 보존된 섹션 수
    split_sections: int = 0  # 분할된 섹션 수
    total_tokens: int = 0
    avg_chunk_tokens: float = 0.0


class AdaptiveChunker:
    """적응형 청커

    Strategy A (FIXED):
        모든 섹션을 chunk_size_tokens 단위로 분할

    Strategy B (ADAPTIVE):
        섹션 크기가 threshold 이하면 그대로 유지
        초과하면 chunk_size_tokens 단위로 분할
    """

    def __init__(
        self,
        strategy: ChunkingStrategy = ChunkingStrategy.ADAPTIVE,
        chunk_size_tokens: int = 700,
        adaptive_threshold_tokens: int = 800,
        chunk_overlap_tokens: int = 100,
        encoding_name: str = "cl100k_base",
    ):
        """
        Args:
            strategy: 청킹 전략 (FIXED or ADAPTIVE)
            chunk_size_tokens: 분할 시 목표 청크 크기
            adaptive_threshold_tokens: ADAPTIVE 모드에서 분할 기준 크기
            chunk_overlap_tokens: 오버랩 크기 (embedding_input용)
            encoding_name: tiktoken 인코딩
        """
        self.strategy = strategy
        self.chunk_size_tokens = chunk_size_tokens
        self.adaptive_threshold_tokens = adaptive_threshold_tokens
        self.chunk_overlap_tokens = chunk_overlap_tokens
        self.encoding = tiktoken.get_encoding(encoding_name)

        # 분할 우선순위
        self.separators = ["\n\n", "\n", ". ", " "]

    def count_tokens(self, text: str) -> int:
        """토큰 수 계산"""
        return len(self.encoding.encode(text))

    def chunk_paper(
        self,
        paper_id: str,
        title: str,
        fulltext: str,
        sections: list[dict],
        year: Optional[int] = None,
    ) -> ChunkingResult:
        """논문 청킹

        Args:
            paper_id: 논문 ID
            title: 논문 제목
            fulltext: 전체 텍스트
            sections: 섹션 정보 리스트
            year: 출판 연도

        Returns:
            ChunkingResult
        """
        # 섹션 객체 생성
        section_objects = []
        for sec in sections:
            sec_text = fulltext[sec["offset_start"]:sec["offset_end"]]
            section_objects.append(Section(
                name=sec["name"],
                title=sec.get("title", sec["name"].title()),
                text=sec_text,
                offset_start=sec["offset_start"],
                offset_end=sec["offset_end"],
            ))

        # 청킹
        all_chunks = []
        preserved_count = 0
        split_count = 0

        for section in section_objects:
            section_tokens = self.count_tokens(section.text)

            # 전략에 따른 분할 결정
            should_split = self._should_split(section_tokens)

            if should_split:
                split_count += 1
                chunks = self._split_section(
                    paper_id, title, year, section, fulltext
                )
            else:
                preserved_count += 1
                chunks = [self._create_single_chunk(
                    paper_id, title, year, section, fulltext
                )]

            all_chunks.extend(chunks)

        # 통계
        total_tokens = sum(c.token_count for c in all_chunks)
        avg_tokens = total_tokens / len(all_chunks) if all_chunks else 0

        return ChunkingResult(
            paper_id=paper_id,
            title=title,
            strategy=self.strategy,
            chunks=all_chunks,
            total_sections=len(section_objects),
            preserved_sections=preserved_count,
            split_sections=split_count,
            total_tokens=total_tokens,
            avg_chunk_tokens=avg_tokens,
        )

    def _should_split(self, section_tokens: int) -> bool:
        """섹션 분할 여부 결정"""
        if self.strategy == ChunkingStrategy.FIXED:
            # Strategy A: 항상 분할 시도
            return section_tokens > self.chunk_size_tokens
        else:
            # Strategy B: threshold 초과 시에만 분할
            return section_tokens > self.adaptive_threshold_tokens

    def _create_single_chunk(
        self,
        paper_id: str,
        title: str,
        year: Optional[int],
        section: Section,
        fulltext: str,
    ) -> Chunk:
        """섹션 전체를 하나의 청크로 생성"""
        chunk_id = f"{paper_id}|{section.name}|0"

        # 임베딩 입력
        year_str = str(year) if year else "Unknown"
        embedding_input = f"""[TITLE] {title}
[SECTION] {section.name}
[YEAR] {year_str}
[TEXT] {section.text}"""

        return Chunk(
            chunk_id=chunk_id,
            paper_id=paper_id,
            section=section.name,
            chunk_index=0,
            text=section.text,
            offset_start=section.offset_start,
            offset_end=section.offset_end,
            token_count=self.count_tokens(section.text),
            strategy=self.strategy.value,
            embedding_input=embedding_input,
        )

    def _split_section(
        self,
        paper_id: str,
        title: str,
        year: Optional[int],
        section: Section,
        fulltext: str,
    ) -> list[Chunk]:
        """섹션을 여러 청크로 분할"""
        chunks = []
        text = section.text

        # 재귀적 분할
        split_texts = self._recursive_split(text, 0)

        # 청크 생성
        current_offset = 0
        for idx, chunk_text in enumerate(split_texts):
            pos = text.find(chunk_text, current_offset)
            if pos == -1:
                pos = text.find(chunk_text)
            if pos == -1:
                pos = current_offset

            offset_start = section.offset_start + pos
            offset_end = offset_start + len(chunk_text)

            # 오버랩 컨텍스트 생성
            overlap_chars = self.chunk_overlap_tokens * 4
            overlap_start = max(section.offset_start, offset_start - overlap_chars)
            text_with_overlap = fulltext[overlap_start:offset_end]

            year_str = str(year) if year else "Unknown"
            embedding_input = f"""[TITLE] {title}
[SECTION] {section.name}
[YEAR] {year_str}
[TEXT] {text_with_overlap}"""

            chunk = Chunk(
                chunk_id=f"{paper_id}|{section.name}|{idx}",
                paper_id=paper_id,
                section=section.name,
                chunk_index=idx,
                text=chunk_text,
                offset_start=offset_start,
                offset_end=offset_end,
                token_count=self.count_tokens(chunk_text),
                strategy=self.strategy.value,
                embedding_input=embedding_input,
            )
            chunks.append(chunk)

            if pos != -1:
                current_offset = pos + len(chunk_text)

        return chunks

    def _recursive_split(self, text: str, separator_idx: int) -> list[str]:
        """재귀적 텍스트 분할"""
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
                        sub_chunks = self._recursive_split(
                            current_chunk, separator_idx + 1
                        )
                        chunks.extend(sub_chunks)
                    else:
                        chunks.append(current_chunk)

                if self.count_tokens(split_with_sep) > self.chunk_size_tokens:
                    sub_chunks = self._recursive_split(
                        split_with_sep, separator_idx + 1
                    )
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


def compare_strategies(
    paper_id: str,
    title: str,
    fulltext: str,
    sections: list[dict],
    year: Optional[int] = None,
) -> dict:
    """두 전략 비교

    Returns:
        비교 결과 딕셔너리
    """
    # Strategy A: Fixed
    chunker_a = AdaptiveChunker(strategy=ChunkingStrategy.FIXED)
    result_a = chunker_a.chunk_paper(paper_id, title, fulltext, sections, year)

    # Strategy B: Adaptive
    chunker_b = AdaptiveChunker(strategy=ChunkingStrategy.ADAPTIVE)
    result_b = chunker_b.chunk_paper(paper_id, title, fulltext, sections, year)

    return {
        "paper_id": paper_id,
        "title": title,
        "strategy_a": {
            "name": "FIXED (700토큰 분할)",
            "chunk_count": len(result_a.chunks),
            "preserved_sections": result_a.preserved_sections,
            "split_sections": result_a.split_sections,
            "avg_tokens": round(result_a.avg_chunk_tokens, 1),
            "chunks": result_a.chunks,
        },
        "strategy_b": {
            "name": "ADAPTIVE (800토큰 기준)",
            "chunk_count": len(result_b.chunks),
            "preserved_sections": result_b.preserved_sections,
            "split_sections": result_b.split_sections,
            "avg_tokens": round(result_b.avg_chunk_tokens, 1),
            "chunks": result_b.chunks,
        },
    }
