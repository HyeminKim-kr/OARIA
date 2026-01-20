"""
전처리 모듈

HTML 엔티티 디코딩 및 텍스트 정규화
기반: OAR-19/yts/src/preprocess.py
"""

import html
import re
import unicodedata


def decode_html_entities(text: str) -> str:
    """HTML 엔티티를 유니코드 문자로 변환"""
    if not text:
        return ""

    decoded = html.unescape(text)

    # 하이픈 계열 통일
    hyphen_chars = [
        "\u2010", "\u2011", "\u2012", "\u2013",
        "\u2014", "\u2015", "\u2212",
    ]
    for char in hyphen_chars:
        decoded = decoded.replace(char, "-")

    return decoded


def normalize_whitespace(text: str) -> str:
    """공백 정규화"""
    if not text:
        return ""
    normalized = re.sub(r"\s+", " ", text)
    return normalized.strip()


def normalize_unicode(text: str) -> str:
    """유니코드 정규화 (NFC)"""
    if not text:
        return ""

    normalized = unicodedata.normalize("NFC", text)
    normalized = "".join(
        char for char in normalized
        if unicodedata.category(char) != "Cc" or char in "\n\t"
    )
    return normalized


def clean_text(text: str) -> str:
    """텍스트 정제 파이프라인"""
    if not text:
        return ""

    text = decode_html_entities(text)
    text = normalize_unicode(text)
    text = normalize_whitespace(text)
    return text


def fix_bare_ampersands(xml_content: str) -> str:
    """XML에서 이스케이프되지 않은 & 문자 수정"""
    if not xml_content:
        return ""

    result = re.sub(
        r'&(?!(?:[a-zA-Z][a-zA-Z0-9]*|#[0-9]+|#x[0-9a-fA-F]+);)',
        '&amp;',
        xml_content
    )
    return result


def preprocess_fulltext(fulltext_xml: str) -> str:
    """전문 XML 전처리"""
    if not fulltext_xml:
        return ""

    processed = fix_bare_ampersands(fulltext_xml)
    processed = normalize_unicode(processed)
    return processed
