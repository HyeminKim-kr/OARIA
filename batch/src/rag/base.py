"""Batch RAG 공통 타입 정의

청킹/임베딩 결과를 표현하는 데이터 클래스들을 정의합니다.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class Chunk:
    """청크 데이터

    논문을 청킹한 결과 단위입니다.
    Weaviate 저장 및 임베딩 생성에 사용됩니다.
    """

    # 식별자
    chunk_id: str  # pmid:12345678|results|3
    paper_id: str  # pmid:12345678

    # 위치 정보
    section: str  # results
    chunk_index: int  # 3
    offset_start: int  # fulltext 기준 시작 위치
    offset_end: int  # fulltext 기준 끝 위치

    # 텍스트
    text: str  # 원문 텍스트 (offset 재현용)
    embedding_text: str  # 임베딩용 텍스트 (컨텍스트 포함)

    # 메타데이터
    token_count: int = 0
    char_count: int = 0
    text_version: str = "v1"

    # 섹션 범위 (Parent 확장 시 경계 체크용)
    section_offset_start: int = 0
    section_offset_end: int = 0

    # 추가 메타데이터
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Section:
    """섹션 정보"""

    name: str  # abstract, introduction, methods, results, discussion
    title: str  # 원본 제목
    offset_start: int  # fulltext 내 시작 위치
    offset_end: int  # fulltext 내 끝 위치


@dataclass
class ChunkingResult:
    """청킹 결과

    논문 전체를 청킹한 결과입니다.
    """

    paper_id: str
    title: str
    fulltext: str
    fulltext_hash: str
    sections: List["Section"]
    chunks: List[Chunk]

    # 통계
    total_chars: int = 0
    total_tokens: int = 0
    avg_chunk_tokens: float = 0.0

    # 청커 정보
    chunker_name: str = ""
    chunker_config: Dict[str, Any] = field(default_factory=dict)
