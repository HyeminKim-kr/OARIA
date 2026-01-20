"""
데이터 모델 정의

PostgreSQL 스키마 및 청킹 연계를 위한 데이터 클래스
기반: OAR-19/yts/src/models.py
"""

from dataclasses import dataclass, field


def determine_paper_id(pmid: str | None, pmcid: str | None, doi: str | None) -> str:
    """
    PMID 우선으로 paper_id 결정

    우선순위:
    1. pmid:{pmid} - PMID가 논문의 고유 식별자
    2. pmc:{pmcid} - PMID 없고 PMCID만 있을 때
    3. doi:{doi} - 둘 다 없을 때 fallback

    Raises:
        ValueError: 유효한 ID가 없을 때
    """
    if pmid:
        return f"pmid:{pmid}"
    elif pmcid:
        return f"pmc:{pmcid}"
    elif doi:
        return f"doi:{doi}"
    else:
        raise ValueError("No valid identifier available (pmid, pmcid, or doi required)")


@dataclass
class Author:
    """저자 정보 (paper_authors 테이블 매핑)"""
    name: str
    order: int
    is_corresponding: bool = False
    orcid: str | None = None
    affiliation: str | None = None


@dataclass
class Section:
    """섹션 정보 (paper_sections 테이블 + 청킹 연계)"""
    name: str
    title: str
    text: str
    order: int
    offset_start: int
    offset_end: int

    @property
    def char_count(self) -> int:
        return self.offset_end - self.offset_start


@dataclass
class ParsedPaper:
    """파싱된 논문 (PostgreSQL + S3 저장용)"""

    # 식별자
    paper_id: str
    pmid: str | None = None
    pmcid: str | None = None
    doi: str | None = None

    # 메타데이터
    title: str = ""
    abstract: str = ""
    journal: str | None = None
    year: int | None = None
    keywords: list[str] = field(default_factory=list)
    mesh_terms: list[str] = field(default_factory=list)

    # 저자
    authors: list[Author] = field(default_factory=list)

    # 섹션
    sections: list[Section] = field(default_factory=list)

    # S3 저장용
    canonical_text: str = ""
    canonical_text_hash: str = ""

    # 변경 추적
    raw_xml_hash: str = ""
    parser_version: str = "1.0.0"

    # 수집 정보
    source: str = "europe_pmc"
    source_url: str | None = None
    is_open_access: bool = True

    def build_source_url(self) -> str | None:
        """원본 논문 페이지 URL 생성"""
        if self.source == "europe_pmc":
            if self.pmcid:
                return f"https://europepmc.org/article/PMC/{self.pmcid}"
            elif self.pmid:
                return f"https://europepmc.org/article/MED/{self.pmid}"
        return None

    @property
    def canonical_text_length(self) -> int:
        return len(self.canonical_text)

    @property
    def canonical_prefix(self) -> str:
        """S3 저장 경로 prefix"""
        safe_id = self.paper_id.replace(':', '_').replace('/', '_')
        return f"canonical/{safe_id}/"

    def to_db_dict(self) -> dict:
        """PostgreSQL papers 테이블용 딕셔너리"""
        return {
            "paper_id": self.paper_id,
            "pmcid": self.pmcid,
            "pmid": self.pmid,
            "doi": self.doi,
            "title": self.title,
            "abstract": self.abstract,
            "journal": self.journal,
            "year": self.year,
            "keywords": self.keywords,
            "source": self.source,
            "source_url": self.source_url or self.build_source_url(),
            "is_open_access": self.is_open_access,
            "canonical_prefix": self.canonical_prefix,
            "canonical_text_version": "v1",
            "canonical_text_hash": self.canonical_text_hash,
            "canonical_text_length": self.canonical_text_length,
            "raw_xml_hash": self.raw_xml_hash,
            "parser_version": self.parser_version,
        }
