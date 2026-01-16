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

from ..models import Author, DisplayFigure, DisplayParagraph, DisplaySection, Figure, Paper, Section
from .preprocess import clean_text, preprocess_fulltext


# 섹션 이름 정규화 매핑
# NOTE: 각 섹션을 고유하게 유지하여 chunk_id 충돌 방지 (batch-07-260101)
# - 이전: conclusion→discussion, background→introduction, summary→abstract (중복 발생)
# - 변경: 각 섹션을 별도로 유지
SECTION_NAME_MAP = {
    # Abstract 계열 - 분리 유지
    "abstract": "abstract",
    "summary": "summary",  # abstract와 분리 (chunk_id 충돌 방지)
    # Introduction 계열 - 분리 유지
    "introduction": "introduction",
    "intro": "introduction",
    "background": "background",  # introduction과 분리 (chunk_id 충돌 방지)
    # Methods 계열 - 분리 유지
    "methods": "methods",
    "method": "methods",
    "materials and methods": "methods",
    "methodology": "methodology",  # methods와 분리
    "experimental": "experimental",  # methods와 분리
    "experimental procedures": "experimental",
    # Results 계열 - 분리 유지
    "results": "results",
    "findings": "findings",  # results와 분리
    # Discussion 계열 - 분리 유지
    "discussion": "discussion",
    "conclusion": "conclusion",  # discussion과 분리 (chunk_id 충돌 방지)
    "conclusions": "conclusion",
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

        # Figure 추출 (Hotlink용) - 섹션 추출 전에 먼저 파싱
        figures = self._parse_figures(root)

        # 섹션 및 fulltext 추출 (figures 전달하여 섹션별 연결)
        sections, display_sections, fulltext = self._extract_sections(root, figures)

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
            display_sections=display_sections,
            figures=figures,
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

    def _extract_sections(
        self, root: etree._Element, figures: list[Figure]
    ) -> tuple[list[Section], list[DisplaySection], str]:
        """XML에서 섹션 추출 및 fulltext 생성

        Args:
            root: XML root element
            figures: 파싱된 Figure 목록 (섹션별 연결용)

        Returns:
            tuple: (sections, display_sections, fulltext)
            - sections: 임베딩용 섹션 (fulltext 오프셋)
            - display_sections: 디스플레이용 섹션 (문단 구분 + 인라인 Figure)
            - fulltext: 전체 텍스트
        """
        sections = []
        display_sections = []
        text_parts = []
        current_offset = 0

        # Figure ID → Figure 매핑 (빠른 조회용)
        figure_map = {fig.id: fig for fig in figures}

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

                # Display: Abstract는 <p> 태그 기준으로 문단 분리
                abstract_paragraphs = self._extract_paragraphs(abstract_elem)
                display_sections.append(DisplaySection(
                    name="abstract",
                    title="Abstract",
                    paragraphs=abstract_paragraphs,
                    figures=[],  # Abstract에는 보통 Figure 없음
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

                # Display: 각 자식 요소를 문단으로 처리
                display_paragraphs = self._extract_paragraphs_from_sec(sec)

                # 섹션 내 Figure 추출 (인라인 배치용)
                sec_figures = self._extract_section_figures(sec, figure_map)

                display_sections.append(DisplaySection(
                    name=sec_name,
                    title=sec_title or sec_name.title(),
                    paragraphs=display_paragraphs,
                    figures=sec_figures,
                ))

        fulltext = "".join(text_parts)
        return sections, display_sections, fulltext

    def _extract_section_figures(
        self, sec: etree._Element, figure_map: dict[str, Figure]
    ) -> list[DisplayFigure]:
        """섹션 내 Figure 추출 (인라인 배치용)

        섹션 내의 <fig> 태그를 찾아 DisplayFigure 리스트 반환
        """
        sec_figures = []

        for fig_elem in sec.iter("fig"):
            fig_id = fig_elem.get("id", "")
            if fig_id and fig_id in figure_map:
                fig = figure_map[fig_id]
                sec_figures.append(DisplayFigure(
                    id=fig.id,
                    label=fig.label,
                    caption=fig.caption,
                    graphic_href=fig.graphic_href,
                ))

        return sec_figures

    def _extract_paragraphs(self, elem: etree._Element) -> list[DisplayParagraph]:
        """요소 내의 <p> 태그들을 문단으로 추출"""
        paragraphs = []

        # <p> 태그들 찾기
        p_elements = elem.findall(".//p")

        if not p_elements:
            # <p> 태그가 없으면 전체 텍스트를 하나의 문단으로
            text = clean_text(extract_text_from_element(elem))
            if text:
                paragraphs.append(DisplayParagraph(text=text))
        else:
            for p_elem in p_elements:
                text = clean_text(extract_text_from_element(p_elem))
                if text:
                    paragraphs.append(DisplayParagraph(text=text))

        return paragraphs

    def _extract_paragraphs_from_sec(self, sec: etree._Element) -> list[DisplayParagraph]:
        """섹션의 자식 요소들을 문단으로 추출

        Note: 모든 자식 요소를 처리하여 fulltext와 일관성 유지
        """
        paragraphs = []

        for child in sec:
            if child.tag == "title":
                continue

            # 중첩 섹션이면 재귀 처리
            if child.tag == "sec":
                # 중첩 섹션 제목 추가
                nested_title_elem = child.find("title")
                if nested_title_elem is not None:
                    nested_title = clean_text(extract_text_from_element(nested_title_elem))
                    if nested_title:
                        paragraphs.append(DisplayParagraph(text=f"**{nested_title}**"))

                # 중첩 섹션 내용 추가
                nested_paragraphs = self._extract_paragraphs_from_sec(child)
                paragraphs.extend(nested_paragraphs)
            else:
                # 일반 요소 (p, table-wrap, list, fig 등)
                text = clean_text(extract_text_from_element(child))
                if text:
                    paragraphs.append(DisplayParagraph(text=text))

        return paragraphs

    def _parse_figures(self, root: etree._Element) -> list[Figure]:
        """XML에서 Figure 정보 추출 (Hotlink용)

        PMC XML의 <fig> 태그에서 Figure 정보를 추출합니다.
        이미지는 다운로드하지 않고 graphic_href만 저장하여
        Europe PMC 서버에서 직접 로드합니다. (Hotlink 방식)

        Returns:
            list[Figure]: Figure 정보 목록
        """
        figures = []
        xlink_ns = "{http://www.w3.org/1999/xlink}"

        # body 내의 모든 <fig> 태그 찾기
        for fig in root.findall(".//fig"):
            fig_id = fig.get("id", "")

            # label 추출 (예: "Figure 1")
            label_elem = fig.find("label")
            label = clean_text(extract_text_from_element(label_elem)) if label_elem is not None else ""

            # caption 추출
            caption = None
            caption_elem = fig.find("caption")
            if caption_elem is not None:
                caption = clean_text(extract_text_from_element(caption_elem))

            # graphic href 추출 (이미지 파일명)
            graphic_href = ""
            graphic_elem = fig.find(".//graphic")
            if graphic_elem is not None:
                graphic_href = graphic_elem.get(f"{xlink_ns}href", "")

            # 최소한 id와 graphic_href가 있어야 유효한 Figure
            if fig_id and graphic_href:
                figures.append(Figure(
                    id=fig_id,
                    label=label or fig_id,  # label이 없으면 id 사용
                    caption=caption,
                    graphic_href=graphic_href,
                ))

        return figures
