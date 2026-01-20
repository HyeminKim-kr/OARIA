"""
전처리 모듈

HTML 엔티티 디코딩 및 텍스트 정규화
"""

import html
import re
import unicodedata


def decode_html_entities(text: str) -> str:
    """HTML 엔티티를 유니코드 문자로 변환

    Examples:
        &#x02010; → - (하이픈)
        &amp; → &
        &lt; → <
        &#60; → <
    """
    if not text:
        return ""

    # 1. 숫자형 엔티티 (&#x2010; &#60;)
    decoded = html.unescape(text)

    # 2. 추가 유니코드 정규화 (하이픈 계열 통일)
    hyphen_chars = [
        "\u2010",  # HYPHEN
        "\u2011",  # NON-BREAKING HYPHEN
        "\u2012",  # FIGURE DASH
        "\u2013",  # EN DASH
        "\u2014",  # EM DASH
        "\u2015",  # HORIZONTAL BAR
        "\u2212",  # MINUS SIGN
    ]
    for char in hyphen_chars:
        decoded = decoded.replace(char, "-")

    return decoded


def normalize_whitespace(text: str) -> str:
    """공백 정규화

    - 연속 공백 → 단일 공백
    - 탭, 개행 → 공백
    - 앞뒤 공백 제거
    """
    if not text:
        return ""

    # 모든 종류의 공백을 단일 공백으로
    normalized = re.sub(r"\s+", " ", text)
    return normalized.strip()


def normalize_unicode(text: str) -> str:
    """유니코드 정규화 (NFC)

    - 합성 문자 통일 (é = e + ´ → é)
    - 제어 문자 제거
    """
    if not text:
        return ""

    # NFC 정규화
    normalized = unicodedata.normalize("NFC", text)

    # 제어 문자 제거 (줄바꿈, 탭 제외)
    normalized = "".join(
        char for char in normalized
        if unicodedata.category(char) != "Cc" or char in "\n\t"
    )

    return normalized


def clean_text(text: str) -> str:
    """텍스트 정제 파이프라인

    순서:
    1. HTML 엔티티 디코딩
    2. 유니코드 정규화
    3. 공백 정규화
    """
    if not text:
        return ""

    text = decode_html_entities(text)
    text = normalize_unicode(text)
    text = normalize_whitespace(text)

    return text


def fix_bare_ampersands(xml_content: str) -> str:
    """XML에서 이스케이프되지 않은 & 문자 수정

    'xmlParseEntityRef: no name' 오류 방지

    Examples:
        R&D → R&amp;D
        AT&T → AT&amp;T
        &amp; (이미 이스케이프됨) → 유지
    """
    if not xml_content:
        return ""

    # 이미 이스케이프된 엔티티는 건너뛰고,
    # & 뒤에 알파벳이나 #이 아닌 경우만 이스케이프
    # 또는 & 뒤에 공백/끝인 경우
    result = re.sub(
        r'&(?!(?:[a-zA-Z][a-zA-Z0-9]*|#[0-9]+|#x[0-9a-fA-F]+);)',
        '&amp;',
        xml_content
    )
    return result


def preprocess_fulltext(fulltext_xml: str) -> str:
    """전문 XML 전처리

    - 이스케이프되지 않은 & 문자 수정
    - 유니코드 정규화
    - 원본 구조 유지 (태그 보존)
    """
    if not fulltext_xml:
        return ""

    # 1. 이스케이프되지 않은 & 문자 수정 (XML 파싱 전 필수!)
    processed = fix_bare_ampersands(fulltext_xml)

    # 2. 유니코드 정규화
    processed = normalize_unicode(processed)

    return processed
