"""논문 데이터 모델"""

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Author:
    """저자 정보"""

    name: str
    order: int
    is_corresponding: bool = False
    orcid: str | None = None
    affiliation: str | None = None


@dataclass
class Section:
    """논문 섹션"""

    name: str  # abstract, introduction, methods, results, discussion
    title: str | None
    order: int
    offset_start: int
    offset_end: int


@dataclass
class Paper:
    """논문 메타데이터"""

    # 식별자
    paper_id: str  # pmid:12345678 또는 pmc:PMC12345678
    pmcid: str | None = None
    pmid: str | None = None
    doi: str | None = None

    # 메타데이터
    title: str = ""
    abstract: str | None = None
    journal: str | None = None
    year: int | None = None
    keywords: list[str] = field(default_factory=list)

    # 저자
    authors: list[Author] = field(default_factory=list)

    # 섹션
    sections: list[Section] = field(default_factory=list)

    # 원문
    fulltext: str | None = None
    raw_xml: str | None = None
    raw_xml_hash: str | None = None

    # 수집 정보
    source: str = "europe_pmc"
    source_url: str | None = None
    is_open_access: bool = True

    # 타임스탬프
    collected_at: datetime = field(default_factory=datetime.now)

    @classmethod
    def create_paper_id(cls, pmcid: str | None, pmid: str | None) -> str:
        """고유 paper_id 생성"""
        if pmcid:
            return f"pmc:{pmcid}"
        if pmid:
            return f"pmid:{pmid}"
        raise ValueError("pmcid 또는 pmid 중 하나는 필수")
