"""텍스트 Chunker

OAR-29 기반: 섹션 기반 Recursive Chunking 구현
- offset 추적 (근거 재현용)
- 가변 청크 크기 (600-800 토큰 목표)
- Contextual prefix 지원
"""

import hashlib
from dataclasses import dataclass
from typing import Optional

import tiktoken


@dataclass
class Chunk:
    """청크 데이터"""

    chunk_id: str  # pmid:12345678|results|3
    paper_id: str  # pmid:12345678
    section: str  # results
    chunk_index: int  # 3

    text: str  # 원문 텍스트
    offset_start: int  # canonical text 기준 시작 위치
    offset_end: int  # canonical text 기준 끝 위치

    token_count: int  # 토큰 수
    char_count: int  # 문자 수

    # 메타데이터
    text_version: str = "v1"
    parent_expand_chars: int = 500

    # 섹션 범위 (Parent 확장 시 경계 체크용)
    section_offset_start: int = 0
    section_offset_end: int = 0

    # 임베딩용 (저장 X, 생성 시에만 사용)
    embedding_input: str = ""


@dataclass
class Section:
    """섹션 정보"""

    name: str  # abstract, introduction, methods, results, discussion
    title: str  # 원본 제목
    text: str  # 섹션 텍스트
    offset_start: int  # fulltext 내 시작 위치
    offset_end: int  # fulltext 내 끝 위치


@dataclass
class ChunkingResult:
    """청킹 결과"""

    paper_id: str
    title: str
    fulltext: str
    fulltext_hash: str
    sections: list[Section]
    chunks: list[Chunk]

    # 통계
    total_chars: int = 0
    total_tokens: int = 0
    avg_chunk_tokens: float = 0.0


class TextChunker:
    """섹션 기반 Recursive Text Chunker"""

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

    def chunk_paper(
        self,
        paper_id: str,
        title: str,
        fulltext: str,
        sections: list[dict],  # [{"name": "abstract", "offset_start": 0, "offset_end": 1000}, ...]
        year: Optional[int] = None,
    ) -> ChunkingResult:
        """논문 전체 청킹

        Args:
            paper_id: 논문 ID (예: pmc:PMC12345678)
            title: 논문 제목
            fulltext: 전체 텍스트
            sections: 섹션 정보 리스트
            year: 출판 연도 (임베딩 prefix용)

        Returns:
            ChunkingResult: 청킹 결과
        """
        fulltext_hash = hashlib.sha256(fulltext.encode()).hexdigest()

        # 섹션 객체 생성
        section_objects = []
        for sec in sections:
            sec_text = fulltext[sec["offset_start"] : sec["offset_end"]]
            section_objects.append(
                Section(
                    name=sec["name"],
                    title=sec.get("title", sec["name"].title()),
                    text=sec_text,
                    offset_start=sec["offset_start"],
                    offset_end=sec["offset_end"],
                )
            )

        # 섹션별 청킹
        all_chunks = []
        for section in section_objects:
            section_chunks = self._chunk_section(
                paper_id=paper_id,
                title=title,
                year=year,
                section=section,
                fulltext=fulltext,  # 오버랩 컨텍스트 생성용
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
            total_tokens=self.count_tokens(fulltext),
            avg_chunk_tokens=avg_tokens,
        )

    def _chunk_section(
        self,
        paper_id: str,
        title: str,
        year: Optional[int],
        section: Section,
        fulltext: str,  # 추가: 오버랩 컨텍스트 생성용
    ) -> list[Chunk]:
        """섹션 내 청킹

        Recursive Character Text Splitter 방식:
        1. 현재 separator로 분할 시도
        2. 청크가 너무 크면 다음 separator로 재귀
        3. offset은 원본 텍스트 기준으로 정확히 계산
        4. 오버랩은 embedding_input에만 적용 (검색 품질용)
        """
        chunks = []
        text = section.text

        # 빈 섹션 처리
        if not text.strip():
            return []

        # 섹션이 충분히 작으면 그대로 반환
        if self.count_tokens(text) <= self.chunk_size_tokens:
            chunk = self._create_chunk(
                paper_id=paper_id,
                title=title,
                year=year,
                section=section,
                chunk_index=0,
                chunk_text=text,
                offset_in_section=0,
                fulltext=fulltext,
            )
            return [chunk]

        # Recursive splitting (오버랩 없이 순수 분할)
        split_texts = self._recursive_split_no_overlap(text, 0)

        # 청크 생성 (원본 텍스트로 정확한 offset 계산)
        current_offset = 0
        for idx, chunk_text in enumerate(split_texts):
            # strip 전 원본 텍스트로 위치 찾기
            # (split_texts는 이미 strip된 상태일 수 있음)
            pos = text.find(chunk_text, current_offset)
            if pos == -1:
                # fallback: 처음부터 찾기
                pos = text.find(chunk_text)

            # 여전히 못 찾으면 앞뒤 공백 포함해서 검색
            if pos == -1:
                # 공백이 있을 수 있는 패턴으로 검색
                for test_offset in range(max(0, current_offset - 10), min(len(text), current_offset + 10)):
                    test_text = text[test_offset:test_offset + len(chunk_text) + 5]
                    if chunk_text in test_text:
                        pos = test_offset + test_text.find(chunk_text)
                        break

            chunk = self._create_chunk(
                paper_id=paper_id,
                title=title,
                year=year,
                section=section,
                chunk_index=idx,
                chunk_text=chunk_text,
                offset_in_section=pos if pos != -1 else current_offset,
                fulltext=fulltext,
            )
            chunks.append(chunk)

            # 다음 검색 시작 위치 (청크 끝에서 시작)
            if pos != -1:
                current_offset = pos + len(chunk_text)

        return chunks

    def _recursive_split_no_overlap(self, text: str, separator_idx: int) -> list[str]:
        """재귀적으로 텍스트 분할 (오버랩 없이 순수 분할)

        Note: offset 정확성을 위해 오버랩을 적용하지 않음.
              오버랩은 embedding_input 생성 시 별도로 적용됨.
        """
        if separator_idx >= len(self.separators):
            # 모든 separator 시도 실패 → 강제 분할
            return self._force_split_no_overlap(text)

        separator = self.separators[separator_idx]
        splits = text.split(separator)

        # 분할 결과가 1개면 다음 separator 시도
        if len(splits) == 1:
            return self._recursive_split_no_overlap(text, separator_idx + 1)

        # 분할된 조각들을 청크로 병합
        chunks = []
        current_chunk = ""

        for i, split in enumerate(splits):
            # separator 복원 (마지막 제외)
            if i < len(splits) - 1:
                split_with_sep = split + separator
            else:
                split_with_sep = split

            # 현재 청크에 추가 시도
            test_chunk = current_chunk + split_with_sep
            test_tokens = self.count_tokens(test_chunk)

            if test_tokens <= self.chunk_size_tokens:
                current_chunk = test_chunk
            else:
                # 현재 청크 저장 (strip하지 않음 - offset 정확성을 위해)
                if current_chunk.strip():
                    # 현재 청크가 여전히 크면 재귀 분할
                    if self.count_tokens(current_chunk) > self.chunk_size_tokens:
                        sub_chunks = self._recursive_split_no_overlap(
                            current_chunk, separator_idx + 1
                        )
                        chunks.extend(sub_chunks)
                    else:
                        chunks.append(current_chunk)  # strip 제거

                # 새 split이 너무 크면 재귀 분할
                if self.count_tokens(split_with_sep) > self.chunk_size_tokens:
                    sub_chunks = self._recursive_split_no_overlap(
                        split_with_sep, separator_idx + 1
                    )
                    if sub_chunks:
                        # 마지막 sub_chunk를 current_chunk로
                        chunks.extend(sub_chunks[:-1])
                        current_chunk = sub_chunks[-1]
                    else:
                        current_chunk = ""
                else:
                    current_chunk = split_with_sep

        # 마지막 청크 처리
        if current_chunk.strip():
            if self.count_tokens(current_chunk) > self.chunk_size_tokens:
                sub_chunks = self._recursive_split_no_overlap(current_chunk, separator_idx + 1)
                chunks.extend(sub_chunks)
            else:
                chunks.append(current_chunk)  # strip 제거

        # Note: _merge_small_chunks를 사용하지 않음
        # 이유: 병합 시 공백 추가로 offset 정확성이 깨짐
        # 작은 청크는 그대로 유지 (offset 정확성 우선)

        return chunks

    def _force_split_no_overlap(self, text: str) -> list[str]:
        """강제 분할 (문자 단위, 오버랩 없음)"""
        chunks = []
        # 대략 토큰당 4자로 계산
        chars_per_chunk = self.chunk_size_tokens * 4

        start = 0
        while start < len(text):
            end = min(start + chars_per_chunk, len(text))
            chunks.append(text[start:end])
            start = end  # 오버랩 없이 다음 위치로

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
        """Chunk 객체 생성

        Note:
            - chunk.text는 원본 텍스트 그대로 (offset 정확성 보장)
            - chunk.embedding_input에만 오버랩 컨텍스트 포함 (검색 품질 향상)
        """
        # 전역 offset 계산
        offset_start = section.offset_start + offset_in_section
        offset_end = offset_start + len(chunk_text)

        # chunk_id 생성
        chunk_id = f"{paper_id}|{section.name}|{chunk_index}"

        # 토큰 수
        token_count = self.count_tokens(chunk_text)

        # 오버랩 컨텍스트 생성 (embedding_input용)
        # 섹션 경계를 존중하면서 앞쪽으로 확장
        overlap_chars = self.chunk_overlap_tokens * 4  # 대략 토큰당 4자
        overlap_start = max(section.offset_start, offset_start - overlap_chars)

        # 오버랩이 적용된 텍스트 (앞쪽 컨텍스트 포함)
        text_with_overlap = fulltext[overlap_start:offset_end]

        # Contextual embedding input (오버랩 포함된 텍스트 사용)
        year_str = str(year) if year else "Unknown"
        embedding_input = f"""[TITLE] {title}
[SECTION] {section.name}
[YEAR] {year_str}
[TEXT] {text_with_overlap}"""

        return Chunk(
            chunk_id=chunk_id,
            paper_id=paper_id,
            section=section.name,
            chunk_index=chunk_index,
            text=chunk_text,  # 원본 텍스트 (offset 정확성)
            offset_start=offset_start,
            offset_end=offset_end,
            token_count=token_count,
            char_count=len(chunk_text),
            section_offset_start=section.offset_start,
            section_offset_end=section.offset_end,
            embedding_input=embedding_input,  # 오버랩 포함 (검색 품질)
        )

    def verify_offsets(self, result: ChunkingResult) -> list[dict]:
        """offset 정확성 검증

        Returns:
            검증 결과 리스트 [{"chunk_id": ..., "valid": True/False, "detail": ...}, ...]
        """
        verifications = []

        for chunk in result.chunks:
            extracted = result.fulltext[chunk.offset_start : chunk.offset_end]
            is_valid = extracted == chunk.text

            verifications.append(
                {
                    "chunk_id": chunk.chunk_id,
                    "valid": is_valid,
                    "stored_preview": chunk.text[:50] + "..." if len(chunk.text) > 50 else chunk.text,
                    "extracted_preview": extracted[:50] + "..." if len(extracted) > 50 else extracted,
                    "offset_start": chunk.offset_start,
                    "offset_end": chunk.offset_end,
                }
            )

        return verifications
