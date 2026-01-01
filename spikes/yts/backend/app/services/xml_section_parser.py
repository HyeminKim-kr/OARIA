"""XML 섹션 파서

S3에서 가져온 PMC XML에서 섹션별 단락 추출
"""

import re
from dataclasses import dataclass

from lxml import etree


@dataclass
class Paragraph:
    """단락 데이터"""
    text: str
    offset_start: int
    offset_end: int


@dataclass
class SectionContent:
    """섹션 내용"""
    section_name: str
    section_title: str
    paragraphs: list[Paragraph]
    total_text: str  # 전체 텍스트 (offset 계산용)


# 섹션 이름 정규화 매핑 (batch/xml_parser.py와 동일)
SECTION_NAME_MAP = {
    "abstract": "abstract",
    "summary": "summary",
    "introduction": "introduction",
    "intro": "introduction",
    "background": "background",
    "methods": "methods",
    "method": "methods",
    "materials and methods": "methods",
    "methodology": "methodology",
    "experimental": "experimental",
    "experimental procedures": "experimental",
    "results": "results",
    "findings": "findings",
    "discussion": "discussion",
    "conclusion": "conclusion",
    "conclusions": "conclusion",
    "acknowledgements": "acknowledgements",
    "acknowledgments": "acknowledgements",
    "references": "references",
}


def normalize_section_name(title: str) -> str:
    """섹션 제목을 표준 이름으로 정규화"""
    if not title:
        return "unknown"

    normalized = title.lower().strip()
    normalized = re.sub(r"^\d+\.?\s*", "", normalized)

    return SECTION_NAME_MAP.get(normalized, normalized)


def clean_text(text: str) -> str:
    """텍스트 정리 (불필요한 공백 제거)"""
    if not text:
        return ""
    # 연속 공백을 하나로
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def extract_text_from_element(elem: etree._Element) -> str:
    """XML 요소에서 텍스트 추출 (자식 포함, 태그 제거)"""
    return "".join(elem.itertext())


class XMLSectionParser:
    """PMC XML 섹션 파서"""

    def parse_section(self, xml_content: str, target_section: str) -> SectionContent | None:
        """XML에서 특정 섹션 추출

        Args:
            xml_content: PMC XML 문자열
            target_section: 찾을 섹션 이름 (정규화된 이름)

        Returns:
            SectionContent 또는 None (섹션을 찾지 못한 경우)
        """
        try:
            root = etree.fromstring(xml_content.encode("utf-8"))
        except etree.XMLSyntaxError:
            return None

        # Abstract 처리
        if target_section == "abstract":
            return self._parse_abstract(root)

        # Body 섹션 처리
        body = root.find(".//body")
        if body is None:
            return None

        for sec in body.findall(".//sec"):
            # 중첩 섹션은 부모만 처리
            sec_title_elem = sec.find("title")
            sec_title = ""
            if sec_title_elem is not None:
                sec_title = clean_text(extract_text_from_element(sec_title_elem))

            sec_name = normalize_section_name(sec_title)

            if sec_name == target_section:
                return self._parse_section_element(sec, sec_name, sec_title)

        return None

    def _parse_abstract(self, root: etree._Element) -> SectionContent | None:
        """Abstract 파싱"""
        abstract_elem = root.find(".//abstract")
        if abstract_elem is None:
            return None

        paragraphs = []
        total_text = ""
        current_offset = 0

        # Abstract 내의 p 태그들
        p_elements = abstract_elem.findall(".//p")

        if not p_elements:
            # p 태그가 없으면 전체 텍스트를 하나의 단락으로
            text = clean_text(extract_text_from_element(abstract_elem))
            if text:
                paragraphs.append(Paragraph(
                    text=text,
                    offset_start=0,
                    offset_end=len(text),
                ))
                total_text = text
        else:
            for p_elem in p_elements:
                text = clean_text(extract_text_from_element(p_elem))
                if text:
                    paragraphs.append(Paragraph(
                        text=text,
                        offset_start=current_offset,
                        offset_end=current_offset + len(text),
                    ))
                    total_text += text + "\n\n"
                    current_offset += len(text) + 2  # +2 for \n\n

        return SectionContent(
            section_name="abstract",
            section_title="Abstract",
            paragraphs=paragraphs,
            total_text=total_text.strip(),
        )

    def _parse_section_element(
        self, sec: etree._Element, sec_name: str, sec_title: str
    ) -> SectionContent:
        """섹션 요소 파싱"""
        paragraphs = []
        total_text = ""
        current_offset = 0

        # 섹션 내의 직접 자식 p 태그들
        for child in sec:
            if child.tag == "title":
                continue

            if child.tag == "p":
                text = clean_text(extract_text_from_element(child))
                if text:
                    paragraphs.append(Paragraph(
                        text=text,
                        offset_start=current_offset,
                        offset_end=current_offset + len(text),
                    ))
                    total_text += text + "\n\n"
                    current_offset += len(text) + 2

            elif child.tag == "sec":
                # 중첩 섹션의 내용도 포함
                nested_text = self._extract_nested_paragraphs(child, paragraphs, current_offset)
                if nested_text:
                    total_text += nested_text
                    current_offset += len(nested_text)

        return SectionContent(
            section_name=sec_name,
            section_title=sec_title or sec_name.title(),
            paragraphs=paragraphs,
            total_text=total_text.strip(),
        )

    def _extract_nested_paragraphs(
        self, sec: etree._Element, paragraphs: list[Paragraph], start_offset: int
    ) -> str:
        """중첩 섹션의 단락 추출"""
        result = ""
        current_offset = start_offset

        # 중첩 섹션 제목
        sec_title_elem = sec.find("title")
        if sec_title_elem is not None:
            title_text = clean_text(extract_text_from_element(sec_title_elem))
            if title_text:
                result += f"**{title_text}**\n\n"
                current_offset += len(title_text) + 6  # ** + ** + \n\n

        for child in sec:
            if child.tag == "title":
                continue

            if child.tag == "p":
                text = clean_text(extract_text_from_element(child))
                if text:
                    paragraphs.append(Paragraph(
                        text=text,
                        offset_start=current_offset,
                        offset_end=current_offset + len(text),
                    ))
                    result += text + "\n\n"
                    current_offset += len(text) + 2

        return result


# 싱글톤 인스턴스
xml_section_parser = XMLSectionParser()
