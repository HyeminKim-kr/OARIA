"""XML 파서

OAR-19 검증된 코드 기반:
- PMC XML 파싱
- 메타데이터 추출
- 섹션 offset 계산
"""

import hashlib
import re
from dataclasses import dataclass

from lxml import etree

from ..models import Author, Paper, Section
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


def extract_text_from_element(elem: etree._Element) -> str:
    """XML 요소에서 텍스트 추출 (자식 포함, 태그 제거)"""
    return "".join(elem.itertext())


@dataclass
class XMLParser:
    """PMC XML 파서 - OAR-19 검증 기반"""

    def parse(self, xml_content: str, pmcid: str) -> Paper:
        """XML 파싱하여 Paper 객체 반환

        Args:
            xml_content: PMC XML 문자열
            pmcid: PMC ID

        Returns:
            Paper: 파싱된 논문 데이터
        """
        # 원본 XML 해시 계산 (전처리 전 원본 기준)
        raw_xml_hash = hashlib.sha256(xml_content.encode("utf-8")).hexdigest()

        # XML 전처리 (OAR-19 검증된 로직)
        preprocessed = preprocess_fulltext(xml_content)

        # XML 파싱
        root = etree.fromstring(preprocessed.encode("utf-8"))

        # 메타데이터 추출
        metadata = self._parse_metadata(root)

        # pmcid 우선 사용 (인자로 받은 것)
        if pmcid:
            if not pmcid.startswith("PMC"):
                pmcid = f"PMC{pmcid}"
            metadata["pmcid"] = pmcid

        # 저자 추출
        authors = self._parse_authors(root)

        # 섹션 및 fulltext 추출
        sections, fulltext = self._extract_sections(root)

        return Paper(
            paper_id=Paper.create_paper_id(metadata.get("pmcid"), metadata.get("pmid")),
            pmcid=metadata.get("pmcid"),
            pmid=metadata.get("pmid"),
            doi=metadata.get("doi"),
            title=metadata.get("title", ""),
            abstract=metadata.get("abstract"),
            journal=metadata.get("journal"),
            year=metadata.get("year"),
            keywords=metadata.get("keywords", []),
            authors=authors,
            sections=sections,
            fulltext=fulltext,
            raw_xml=xml_content,
            raw_xml_hash=raw_xml_hash,
        )

    def _parse_metadata(self, root: etree._Element) -> dict:
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
        if doi_elem is not None and doi_elem.text:
            metadata["doi"] = doi_elem.text.strip()

        # 제목
        title = root.findtext(".//article-title", default="")
        metadata["title"] = clean_text(title)

        # 초록
        abstract_elem = root.find(".//abstract")
        if abstract_elem is not None:
            metadata["abstract"] = clean_text(extract_text_from_element(abstract_elem))
        else:
            metadata["abstract"] = None

        # 저널
        metadata["journal"] = root.findtext(".//journal-title", default=None)

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

        return metadata

    def _parse_authors(self, root: etree._Element) -> list[Author]:
        """XML에서 저자 정보 추출"""
        authors = []

        # contrib 태그 찾기 (author 타입만)
        contribs = root.xpath(".//contrib[@contrib-type='author']")

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
                        affiliation = clean_text("".join(aff_elem.itertext()))

            # 교신저자 여부
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

    def _extract_sections(self, root: etree._Element) -> tuple[list[Section], str]:
        """XML에서 섹션 추출 및 fulltext 생성"""
        sections = []
        text_parts = []
        current_offset = 0

        # 제목 추출
        title = root.findtext(".//article-title", default="")
        title = clean_text(title)
        if title:
            title_block = f"[TITLE] {title}\n\n"
            text_parts.append(title_block)
            current_offset += len(title_block)

        # Abstract 추출
        abstract_elem = root.find(".//abstract")
        if abstract_elem is not None:
            abstract_text = extract_text_from_element(abstract_elem)
            abstract_text = clean_text(abstract_text)

            if abstract_text:
                section_header = "[ABSTRACT]\n"
                text_parts.append(section_header)
                current_offset += len(section_header)

                offset_start = current_offset
                text_parts.append(abstract_text + "\n\n")
                current_offset += len(abstract_text) + 2

                sections.append(Section(
                    name="abstract",
                    title="Abstract",
                    order=len(sections) + 1,
                    offset_start=offset_start,
                    offset_end=current_offset - 2,
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
                    sec_title = clean_text(extract_text_from_element(sec_title_elem))

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

                # fulltext에 추가
                section_header = f"[{sec_name.upper()}]\n"
                if sec_title and sec_title.lower() != sec_name:
                    section_header = f"[{sec_name.upper()}] {sec_title}\n"

                text_parts.append(section_header)
                current_offset += len(section_header)

                offset_start = current_offset
                text_parts.append(sec_text + "\n\n")
                current_offset += len(sec_text) + 2

                sections.append(Section(
                    name=sec_name,
                    title=sec_title or sec_name.title(),
                    order=len(sections) + 1,
                    offset_start=offset_start,
                    offset_end=current_offset - 2,
                ))

        fulltext = "".join(text_parts)
        return sections, fulltext
