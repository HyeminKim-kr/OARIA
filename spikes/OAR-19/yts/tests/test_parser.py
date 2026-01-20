"""
파싱 로직 테스트
"""

import pytest
from src.preprocess import decode_html_entities, clean_text, normalize_whitespace
from src.parser import normalize_section_name, parse_fulltext_xml
from src.models import Author, Section


class TestPreprocess:
    """전처리 함수 테스트"""

    def test_decode_html_entities_numeric(self):
        """숫자형 HTML 엔티티 디코딩"""
        assert decode_html_entities("&#x02010;") == "-"
        assert decode_html_entities("&#60;") == "<"
        assert decode_html_entities("&#x003E;") == ">"

    def test_decode_html_entities_named(self):
        """명명된 HTML 엔티티 디코딩"""
        assert decode_html_entities("&amp;") == "&"
        assert decode_html_entities("&lt;") == "<"
        assert decode_html_entities("&gt;") == ">"

    def test_decode_html_entities_hyphen_normalization(self):
        """하이픈 계열 문자 정규화"""
        # EN DASH
        assert decode_html_entities("\u2013") == "-"
        # EM DASH
        assert decode_html_entities("\u2014") == "-"
        # MINUS SIGN
        assert decode_html_entities("\u2212") == "-"

    def test_normalize_whitespace(self):
        """공백 정규화"""
        assert normalize_whitespace("  hello   world  ") == "hello world"
        assert normalize_whitespace("hello\n\nworld") == "hello world"
        assert normalize_whitespace("hello\t\tworld") == "hello world"

    def test_clean_text_pipeline(self):
        """전체 정제 파이프라인"""
        text = "  Hello&#x02010;World  \n\n  &amp;  Test  "
        assert clean_text(text) == "Hello-World & Test"


class TestParser:
    """파서 함수 테스트"""

    def test_normalize_section_name(self):
        """섹션 이름 정규화"""
        assert normalize_section_name("Introduction") == "introduction"
        assert normalize_section_name("1. Introduction") == "introduction"
        assert normalize_section_name("Materials and Methods") == "methods"
        assert normalize_section_name("RESULTS") == "results"
        assert normalize_section_name("Conclusions") == "discussion"

    def test_parse_fulltext_xml_basic(self):
        """기본 XML 파싱"""
        xml = """<?xml version="1.0"?>
        <article>
            <front>
                <article-meta>
                    <article-id pub-id-type="pmc">PMC12345678</article-id>
                    <article-id pub-id-type="pmid">12345678</article-id>
                    <article-id pub-id-type="doi">10.1234/test</article-id>
                    <title-group>
                        <article-title>Test Article Title</article-title>
                    </title-group>
                    <contrib-group>
                        <contrib contrib-type="author" corresp="yes">
                            <name>
                                <surname>Kim</surname>
                                <given-names>Taesik</given-names>
                            </name>
                            <contrib-id contrib-id-type="orcid">0000-0001-2345-6789</contrib-id>
                        </contrib>
                        <contrib contrib-type="author">
                            <name>
                                <surname>Lee</surname>
                                <given-names>Minjun</given-names>
                            </name>
                        </contrib>
                    </contrib-group>
                    <abstract>
                        <p>This is the abstract of the test article.</p>
                    </abstract>
                    <pub-date>
                        <year>2024</year>
                    </pub-date>
                    <journal-title>Test Journal</journal-title>
                </article-meta>
            </front>
            <body>
                <sec>
                    <title>Introduction</title>
                    <p>This is the introduction section.</p>
                </sec>
                <sec>
                    <title>Methods</title>
                    <p>This is the methods section.</p>
                </sec>
                <sec>
                    <title>Results</title>
                    <p>This is the results section.</p>
                </sec>
            </body>
        </article>
        """

        paper = parse_fulltext_xml(xml)

        # 기본 메타데이터 확인 (PMID 우선 정책)
        assert paper.paper_id == "pmid:12345678"  # PMID가 있으면 PMID 우선
        assert paper.pmcid == "PMC12345678"
        assert paper.pmid == "12345678"
        assert paper.doi == "10.1234/test"
        assert paper.title == "Test Article Title"
        assert paper.year == 2024
        assert paper.journal == "Test Journal"

        # 저자 확인
        assert len(paper.authors) == 2
        assert paper.authors[0].name == "Taesik Kim"
        assert paper.authors[0].order == 1
        assert paper.authors[0].is_corresponding is True
        assert paper.authors[0].orcid == "0000-0001-2345-6789"
        assert paper.authors[1].name == "Minjun Lee"
        assert paper.authors[1].order == 2
        assert paper.authors[1].is_corresponding is False

        # 섹션 확인 (abstract + 3개 body 섹션)
        assert len(paper.sections) == 4
        assert paper.sections[0].name == "abstract"
        assert paper.sections[1].name == "introduction"
        assert paper.sections[2].name == "methods"
        assert paper.sections[3].name == "results"

        # canonical_text 확인
        assert "[TITLE] Test Article Title" in paper.canonical_text
        assert "[ABSTRACT]" in paper.canonical_text
        assert "[INTRODUCTION]" in paper.canonical_text

        # offset 확인
        for section in paper.sections:
            assert section.offset_start >= 0
            assert section.offset_end > section.offset_start
            # offset이 실제 텍스트 위치와 일치하는지 확인
            extracted = paper.canonical_text[section.offset_start:section.offset_end]
            assert section.text in extracted or extracted in section.text

        # 해시 확인
        assert len(paper.canonical_text_hash) == 64  # SHA-256

    def test_parse_fulltext_xml_pmcid_format(self):
        """실제 API에서 오는 pmcid 형식 테스트 (pub-id-type='pmcid')"""
        xml = """<?xml version="1.0"?>
        <article>
            <front>
                <article-meta>
                    <article-id pub-id-type="pmcid">12664089</article-id>
                    <article-id pub-id-type="pmid">41317095</article-id>
                    <article-id pub-id-type="doi">10.1002/cam4.71431</article-id>
                    <title-group>
                        <article-title>Test Article with pmcid format</article-title>
                    </title-group>
                </article-meta>
            </front>
        </article>
        """

        paper = parse_fulltext_xml(xml)

        # pmcid 형식으로 와도 정상 파싱되어야 함 (PMID 우선 정책)
        assert paper.pmcid == "PMC12664089"
        assert paper.pmid == "41317095"
        assert paper.paper_id == "pmid:41317095"  # PMID가 있으므로 PMID 우선

    def test_parse_fulltext_xml_pmid_only(self):
        """PMID만 있는 경우 paper_id 생성"""
        xml = """<?xml version="1.0"?>
        <article>
            <front>
                <article-meta>
                    <article-id pub-id-type="pmid">99999999</article-id>
                    <title-group>
                        <article-title>PMID Only Article</article-title>
                    </title-group>
                </article-meta>
            </front>
        </article>
        """

        paper = parse_fulltext_xml(xml)
        assert paper.paper_id == "pmid:99999999"

    def test_parse_corresponding_author_xref_format(self):
        """실제 API에서 오는 교신저자 형식 테스트 (xref ref-type='corresp')"""
        xml = """<?xml version="1.0"?>
        <article>
            <front>
                <article-meta>
                    <article-id pub-id-type="pmcid">12650373</article-id>
                    <title-group>
                        <article-title>Test Article</article-title>
                    </title-group>
                    <contrib-group>
                        <contrib contrib-type="author">
                            <name>
                                <surname>Kim</surname>
                                <given-names>Taesik</given-names>
                            </name>
                            <xref ref-type="corresp" rid="c1">*</xref>
                        </contrib>
                        <contrib contrib-type="author">
                            <name>
                                <surname>Lee</surname>
                                <given-names>Minjun</given-names>
                            </name>
                        </contrib>
                    </contrib-group>
                    <contrib-group>
                        <contrib contrib-type="editor">
                            <name>
                                <surname>Editor</surname>
                                <given-names>Test</given-names>
                            </name>
                        </contrib>
                    </contrib-group>
                </article-meta>
            </front>
        </article>
        """

        paper = parse_fulltext_xml(xml)

        # 저자만 추출되어야 함 (editor 제외)
        assert len(paper.authors) == 2

        # 첫 번째 저자가 xref 기반 교신저자
        assert paper.authors[0].name == "Taesik Kim"
        assert paper.authors[0].is_corresponding is True

        # 두 번째 저자는 일반 저자
        assert paper.authors[1].name == "Minjun Lee"
        assert paper.authors[1].is_corresponding is False


class TestModels:
    """데이터 모델 테스트"""

    def test_section_char_count(self):
        """섹션 char_count 계산"""
        section = Section(
            name="abstract",
            title="Abstract",
            text="Test content",
            order=1,
            offset_start=0,
            offset_end=100,
        )
        assert section.char_count == 100

    def test_parsed_paper_to_db_dict(self):
        """ParsedPaper.to_db_dict() 확인"""
        from src.models import ParsedPaper

        paper = ParsedPaper(
            paper_id="pmc:PMC123",
            pmcid="PMC123",
            title="Test",
            canonical_text="Test content",
            canonical_text_hash="abc123",
        )

        db_dict = paper.to_db_dict()

        assert db_dict["paper_id"] == "pmc:PMC123"
        assert db_dict["canonical_prefix"] == "canonical/pmc_PMC123/"  # : → _ 변환
        assert db_dict["canonical_text_version"] == "v1"
        assert db_dict["canonical_text_length"] == 12

    def test_parsed_paper_to_chunking_dict(self):
        """ParsedPaper.to_chunking_dict() 확인"""
        from src.models import ParsedPaper

        paper = ParsedPaper(
            paper_id="pmc:PMC123",
            title="Test",
            year=2024,
            sections=[
                Section(
                    name="abstract",
                    title="Abstract",
                    text="Abstract text",
                    order=1,
                    offset_start=0,
                    offset_end=50,
                )
            ],
        )

        chunking_dict = paper.to_chunking_dict()

        assert chunking_dict["paper_id"] == "pmc:PMC123"
        assert chunking_dict["title"] == "Test"
        assert chunking_dict["year"] == 2024
        assert len(chunking_dict["sections"]) == 1
        assert chunking_dict["sections"][0]["name"] == "abstract"
        assert chunking_dict["sections"][0]["offset_start"] == 0
        assert chunking_dict["sections"][0]["offset_end"] == 50
