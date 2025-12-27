"""
데이터 모델 정의

PostgreSQL 스키마 및 청킹 연계를 위한 데이터 클래스
"""

from dataclasses import dataclass, field


def determine_paper_id(pmid: str | None, pmcid: str | None, doi: str | None) -> str:
    """
    PMID 우선으로 paper_id 결정

    우선순위:
    1. pmid:{pmid} - PMID가 논문의 고유 식별자
    2. pmc:{pmcid} - PMID 없고 PMCID만 있을 때
    3. doi:{doi} - 둘 다 없을 때 fallback

    Args:
        pmid: PubMed ID (예: "27959700")
        pmcid: PMC ID (예: "PMC5765844")
        doi: DOI (예: "10.1056/NEJMoa1713137")

    Returns:
        paper_id (예: "pmid:27959700")

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
    order: int                          # 저자 순서 (1, 2, 3...)
    is_corresponding: bool = False      # 교신저자 여부
    orcid: str | None = None            # ORCID (0000-xxxx-xxxx-xxxx)
    affiliation: str | None = None      # 소속 기관


@dataclass
class Section:
    """섹션 정보 (paper_sections 테이블 + 청킹 연계)"""
    name: str                           # abstract, introduction, methods, results, discussion
    title: str                          # 원본 섹션 제목
    text: str                           # 섹션 텍스트
    order: int                          # 섹션 순서
    offset_start: int                   # canonical_text 내 시작 위치
    offset_end: int                     # canonical_text 내 끝 위치

    @property
    def char_count(self) -> int:
        return self.offset_end - self.offset_start


@dataclass
class ParsedPaper:
    """파싱된 논문 (PostgreSQL + S3 저장용)"""

    # 식별자
    paper_id: str                       # pmc:PMC12345678 또는 pmid:12345678
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

    # 저자 (paper_authors 테이블)
    authors: list[Author] = field(default_factory=list)

    # 섹션 (paper_sections 테이블 + 청킹 연계)
    sections: list[Section] = field(default_factory=list)

    # S3 저장용
    canonical_text: str = ""
    canonical_text_hash: str = ""

    # 변경 추적 (원본 변경 vs 파서 변경 구분)
    raw_xml_hash: str = ""              # 원본 XML bytes SHA256
    parser_version: str = "1.0.0"       # 파싱 로직 버전

    # 수집 정보
    source: str = "europe_pmc"
    source_url: str | None = None  # 원본 논문 페이지 URL
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
        """S3 저장 경로 prefix (: → _ 변환)

        Examples:
            pmid:27959700 → canonical/pmid_27959700/
            pmc:PMC5765844 → canonical/pmc_PMC5765844/
            doi:10.1056/NEJMoa1713137 → canonical/doi_10.1056_NEJMoa1713137/
        """
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

    def to_chunking_dict(self) -> dict:
        """청킹 모듈 전달용 딕셔너리 (OAR-18 연계)"""
        return {
            "paper_id": self.paper_id,
            "title": self.title,
            "year": self.year,
            "sections": [
                {
                    "name": s.name,
                    "title": s.title,
                    "text": s.text,
                    "offset_start": s.offset_start,
                    "offset_end": s.offset_end,
                }
                for s in self.sections
            ],
        }
