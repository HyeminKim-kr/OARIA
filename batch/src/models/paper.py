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
    """논문 섹션 (임베딩용 - fulltext 오프셋)"""

    name: str  # abstract, introduction, methods, results, discussion
    title: str | None
    order: int
    offset_start: int
    offset_end: int


@dataclass
class DisplayParagraph:
    """디스플레이용 문단 (가독성) - Legacy, DisplayContent로 대체"""

    text: str


@dataclass
class DisplayFigure:
    """디스플레이용 Figure - Legacy, DisplayContent로 대체"""

    id: str  # "fig1"
    label: str  # "Figure 1"
    caption: str | None = None
    graphic_href: str = ""


@dataclass
class DisplayContent:
    """디스플레이 컨텐츠 (문단 또는 Figure)

    XML 원본 순서대로 저장하여 fulltext와 동일한 위치에 Figure 배치
    """

    type: str  # "paragraph" | "figure"
    # paragraph인 경우
    text: str | None = None
    # figure인 경우
    id: str | None = None
    label: str | None = None
    caption: str | None = None
    graphic_href: str | None = None


@dataclass
class DisplaySection:
    """디스플레이용 섹션 (가독성)

    Note: fulltext 오프셋은 Weaviate에서 조회 (section_fulltext_offset)
    """

    name: str
    title: str
    contents: list[DisplayContent] = field(default_factory=list)  # XML 순서대로 문단/Figure 혼합
    # Legacy fields (하위 호환)
    paragraphs: list[DisplayParagraph] = field(default_factory=list)
    figures: list[DisplayFigure] = field(default_factory=list)


@dataclass
class Figure:
    """Figure 정보 (Hotlink 이미지용)"""

    id: str  # "fig1"
    label: str  # "Figure 1"
    caption: str | None = None  # 캡션 텍스트
    graphic_href: str = ""  # "tlcr-14-12-5465-f1" (이미지 파일명)


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

    # 디스플레이용 섹션 (가독성 + fulltext 오프셋)
    display_sections: list[DisplaySection] = field(default_factory=list)

    # Figure (Hotlink 이미지)
    figures: list[Figure] = field(default_factory=list)

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
