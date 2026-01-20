"""
XML 파싱 모듈

Europe PMC XML에서 저자, 섹션 추출 및 canonical_text 생성
"""

import hashlib
import re
from lxml import etree

from .models import Author, Section, ParsedPaper, determine_paper_id
from .preprocess import clean_text, preprocess_fulltext


# 섹션 이름 정규화 매핑
SECTION_NAME_MAP = {
    # Abstract 계열
    "abstract": "abstract",
    "summary": "abstract",
    # Introduction 계열
    "introduction": "introduction",
    "intro": "introduction",
    "background": "introduction",
    # Methods 계열
    "methods": "methods",
    "method": "methods",
    "materials and methods": "methods",
    "methodology": "methods",
    "experimental": "methods",
    "experimental procedures": "methods",
    # Results 계열
    "results": "results",
    "findings": "results",
    # Discussion 계열
    "discussion": "discussion",
    "conclusions": "discussion",
    "conclusion": "discussion",
    # 기타 (유지)
    "acknowledgements": "acknowledgements",
    "acknowledgments": "acknowledgements",
    "references": "references",
}


def normalize_section_name(title: str) -> str:
    """섹션 제목을 표준 이름으로 정규화"""
    if not title:
        return "unknown"

    # 소문자 변환 및 공백 정규화
    normalized = title.lower().strip()

    # 숫자 접두사 제거 (1. Introduction → introduction)
    normalized = re.sub(r"^\d+\.?\s*", "", normalized)

    # 매핑 테이블에서 찾기
    return SECTION_NAME_MAP.get(normalized, normalized)


def parse_authors(root: etree._Element) -> list[Author]:
    """XML에서 저자 정보 추출

    Europe PMC XML 구조:
    <contrib-group>
        <contrib contrib-type="author">
            <name>
                <surname>Kim</surname>
                <given-names>Taesik</given-names>
            </name>
            <xref ref-type="aff" rid="aff1"/>
            <contrib-id contrib-id-type="orcid">0000-0001-2345-6789</contrib-id>
        </contrib>
    </contrib-group>
    """
    authors = []

    # contrib 태그 찾기 (author 타입만)
    contrib_xpath = ".//contrib[@contrib-type='author']"
    contribs = root.xpath(contrib_xpath)

    for idx, contrib in enumerate(contribs, start=1):
        # 이름 추출
        surname = contrib.findtext(".//surname", default="")
        given_names = contrib.findtext(".//given-names", default="")
        name = f"{given_names} {surname}".strip()

        if not name:
            continue

        # ORCID 추출
        orcid = None
        orcid_elem = contrib.find(".//contrib-id[@contrib-id-type='orcid']")
        if orcid_elem is not None and orcid_elem.text:
            orcid = orcid_elem.text.strip()
            # URL 형식이면 ID만 추출
            if "orcid.org/" in orcid:
                orcid = orcid.split("orcid.org/")[-1]

        # 소속 추출 (xref로 연결된 aff 찾기)
        affiliation = None
        xref = contrib.find(".//xref[@ref-type='aff']")
        if xref is not None:
            aff_id = xref.get("rid")
            if aff_id:
                aff_elem = root.find(f".//aff[@id='{aff_id}']")
                if aff_elem is not None:
                    # 텍스트 전체 추출 (자식 포함)
                    affiliation = "".join(aff_elem.itertext()).strip()
                    affiliation = clean_text(affiliation)

        # 교신저자 여부
        # 방법 1: corresp="yes" 속성 확인
        # 방법 2: <xref ref-type="corresp"> 요소 확인 (실제 Europe PMC에서 더 흔함)
        is_corresponding = (
            contrib.get("corresp") == "yes"
            or contrib.find(".//xref[@ref-type='corresp']") is not None
        )

        authors.append(Author(
            name=clean_text(name),
            order=idx,
            is_corresponding=is_corresponding,
            orcid=orcid,
            affiliation=affiliation,
        ))

    return authors


def extract_text_from_element(elem: etree._Element) -> str:
    """XML 요소에서 텍스트 추출 (자식 포함, 태그 제거)"""
    return "".join(elem.itertext())


def extract_sections(root: etree._Element) -> tuple[list[Section], str]:
    """XML에서 섹션 추출 및 canonical_text 생성

    Returns:
        (sections, canonical_text)

    canonical_text 구조:
        [TITLE] 논문 제목

        [ABSTRACT]
        초록 내용...

        [INTRODUCTION]
        소개 내용...
    """
    sections = []
    canonical_parts = []
    current_offset = 0

    # 제목 추출
    title = root.findtext(".//article-title", default="")
    title = clean_text(title)
    if title:
        title_block = f"[TITLE] {title}\n\n"
        canonical_parts.append(title_block)
        current_offset += len(title_block)

    # Abstract 추출
    abstract_elem = root.find(".//abstract")
    if abstract_elem is not None:
        abstract_text = extract_text_from_element(abstract_elem)
        abstract_text = clean_text(abstract_text)

        if abstract_text:
            section_header = "[ABSTRACT]\n"
            canonical_parts.append(section_header)
            current_offset += len(section_header)

            offset_start = current_offset
            canonical_parts.append(abstract_text + "\n\n")
            current_offset += len(abstract_text) + 2

            sections.append(Section(
                name="abstract",
                title="Abstract",
                text=abstract_text,
                order=len(sections) + 1,
                offset_start=offset_start,
                offset_end=current_offset - 2,  # 개행 제외
            ))

    # Body 섹션 추출
    body = root.find(".//body")
    if body is not None:
        for sec in body.findall(".//sec"):
            # 중첩 섹션은 스킵 (최상위만)
            if sec.getparent() != body:
                continue

            # 섹션 제목
            sec_title_elem = sec.find("title")
            sec_title = ""
            if sec_title_elem is not None:
                sec_title = extract_text_from_element(sec_title_elem)
                sec_title = clean_text(sec_title)

            # 섹션 내용 (title 제외)
            sec_text_parts = []
            for child in sec:
                if child.tag != "title":
                    sec_text_parts.append(extract_text_from_element(child))

            sec_text = " ".join(sec_text_parts)
            sec_text = clean_text(sec_text)

            if not sec_text:
                continue

            # 섹션 이름 정규화
            sec_name = normalize_section_name(sec_title)

            # canonical_text에 추가
            section_header = f"[{sec_name.upper()}]\n"
            if sec_title and sec_title.lower() != sec_name:
                section_header = f"[{sec_name.upper()}] {sec_title}\n"

            canonical_parts.append(section_header)
            current_offset += len(section_header)

            offset_start = current_offset
            canonical_parts.append(sec_text + "\n\n")
            current_offset += len(sec_text) + 2

            sections.append(Section(
                name=sec_name,
                title=sec_title or sec_name.title(),
                text=sec_text,
                order=len(sections) + 1,
                offset_start=offset_start,
                offset_end=current_offset - 2,
            ))

    canonical_text = "".join(canonical_parts)
    return sections, canonical_text


def parse_metadata(root: etree._Element) -> dict:
    """기본 메타데이터 추출"""
    metadata = {}

    # PMID
    pmid_elem = root.find(".//article-id[@pub-id-type='pmid']")
    if pmid_elem is not None and pmid_elem.text:
        metadata["pmid"] = pmid_elem.text.strip()

    # PMCID (pub-id-type이 'pmc' 또는 'pmcid'일 수 있음)
    pmcid_elem = root.find(".//article-id[@pub-id-type='pmcid']")
    if pmcid_elem is None:
        pmcid_elem = root.find(".//article-id[@pub-id-type='pmc']")
    if pmcid_elem is not None and pmcid_elem.text:
        pmc_id = pmcid_elem.text.strip()
        if not pmc_id.startswith("PMC"):
            pmc_id = f"PMC{pmc_id}"
        metadata["pmcid"] = pmc_id

    # DOI
    doi_elem = root.find(".//article-id[@pub-id-type='doi']")
    if doi_elem is not None:
        metadata["doi"] = doi_elem.text

    # 제목
    title = root.findtext(".//article-title", default="")
    metadata["title"] = clean_text(title)

    # 초록
    abstract_elem = root.find(".//abstract")
    if abstract_elem is not None:
        metadata["abstract"] = clean_text(extract_text_from_element(abstract_elem))
    else:
        metadata["abstract"] = ""

    # 저널
    metadata["journal"] = root.findtext(".//journal-title", default="")

    # 연도
    year_elem = root.find(".//pub-date/year")
    if year_elem is not None and year_elem.text:
        try:
            metadata["year"] = int(year_elem.text)
        except ValueError:
            metadata["year"] = None
    else:
        metadata["year"] = None

    # 키워드
    keywords = []
    for kwd in root.findall(".//kwd"):
        if kwd.text:
            keywords.append(clean_text(kwd.text))
    metadata["keywords"] = keywords

    # MeSH terms
    mesh_terms = []
    for mesh in root.findall(".//subject[@subject-type='mesh']"):
        if mesh.text:
            mesh_terms.append(clean_text(mesh.text))
    metadata["mesh_terms"] = mesh_terms

    return metadata


def compute_hash(text: str) -> str:
    """canonical_text 해시 계산 (SHA-256)"""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def parse_fulltext_xml(xml_content: str) -> ParsedPaper:
    """전체 파싱 파이프라인

    Args:
        xml_content: Europe PMC fulltext XML

    Returns:
        ParsedPaper 객체
    """
    # 원본 XML 해시 계산 (전처리 전 원본 기준)
    raw_xml_hash = compute_hash(xml_content)

    # XML 전처리
    preprocessed = preprocess_fulltext(xml_content)

    # XML 파싱
    root = etree.fromstring(preprocessed.encode("utf-8"))

    # 메타데이터 추출
    metadata = parse_metadata(root)

    # paper_id 생성 (PMID 우선)
    paper_id = determine_paper_id(
        pmid=metadata.get("pmid"),
        pmcid=metadata.get("pmcid"),
        doi=metadata.get("doi"),
    )

    # 저자 추출
    authors = parse_authors(root)

    # 섹션 및 canonical_text 추출
    sections, canonical_text = extract_sections(root)

    # 해시 계산
    canonical_text_hash = compute_hash(canonical_text)

    return ParsedPaper(
        paper_id=paper_id,
        pmid=metadata.get("pmid"),
        pmcid=metadata.get("pmcid"),
        doi=metadata.get("doi"),
        title=metadata.get("title", ""),
        abstract=metadata.get("abstract", ""),
        journal=metadata.get("journal"),
        year=metadata.get("year"),
        keywords=metadata.get("keywords", []),
        mesh_terms=metadata.get("mesh_terms", []),
        authors=authors,
        sections=sections,
        canonical_text=canonical_text,
        canonical_text_hash=canonical_text_hash,
        raw_xml_hash=raw_xml_hash,
    )
