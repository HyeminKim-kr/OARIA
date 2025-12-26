# OAR-95: 논문 메타데이터 파싱 로직 설계

> **목적**: Europe PMC에서 수집한 데이터를 PostgreSQL 스키마에 맞게 파싱하는 로직 설계
>
> **작성일**: 2025-12-23
>
> **상태**: 설계 초안
>
> **관련**: OAR-18 (API 연동), OAR-20 (스키마 설계)

---

## TL;DR

| 구분 | 현재 (OAR-18) | 목표 (OAR-95) |
|------|--------------|---------------|
| 메타데이터 파싱 | 기본 필드 추출 | PostgreSQL 스키마 매핑 |
| 저자 파싱 | fullName 리스트 | 순서, ORCID, 소속 포함 |
| 섹션 추출 | 문자열 find (부정확) | XML 파서 기반 (정확) |
| offset 추적 | 없음 | 섹션별 offset_start/end |
| 전처리 | 정규식 태그 제거 | HTML 엔티티 디코딩 + 정규화 |

---

## 1. 데이터 흐름 개요

```
┌─────────────────────────────────────────────────────────────────┐
│  Europe PMC API                                                  │
│  (JSON + XML 전문)                                               │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│  [1단계] 메타데이터 파싱                                          │
│  - 기본 필드: pmid, pmcid, doi, title, abstract, year, journal  │
│  - 저자: 순서, ORCID, 소속, 교신저자                              │
│  - 키워드, MeSH 용어                                             │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│  [2단계] 전문 전처리                                              │
│  - HTML 엔티티 디코딩 (&#x02010; → -)                            │
│  - 불필요 태그 제거 (메타데이터 태그 등)                           │
│  - 공백 정규화                                                   │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│  [3단계] 섹션 추출 (XML 파서)                                     │
│  - Abstract, Introduction, Methods, Results, Discussion, etc.  │
│  - 각 섹션의 offset_start, offset_end 계산                       │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│  [4단계] 저장                                                    │
│  - PostgreSQL: papers, paper_authors                            │
│  - S3: canonical_text (정제된 전문)                              │
└─────────────────────────────────────────────────────────────────┘
```

---

## 2. 현재 데이터 분석

### 2.1 Europe PMC API 응답 (JSON)

```json
{
  "id": "europepmc:PMC12707179",
  "source": "europe_pmc",
  "pmid": "41400420",
  "pmcid": "PMC12707179",
  "doi": "10.1002/cncy.70064",
  "title": "Risk of malignancy of cytologic categories...",
  "abstract": "<h4>Background</h4>Renal mass biopsy...",
  "authors": ["Lin X"],  // ⚠️ 현재: 이름만
  "journal": null,       // ⚠️ 누락된 경우 있음
  "year": 2026,
  "keywords": ["Renal Mass Biopsy", ...],
  "mesh_terms": ["Humans", "Adenoma, Oxyphilic", ...],
  "is_open_access": true,
  "has_full_text": true,
  "full_text": "pmc Cancer Cytopathol..."  // XML 태그 제거된 상태
}
```

### 2.2 전문(full_text) 원본 분석

```xml
<!-- Europe PMC fullTextXML 응답 예시 -->
<article>
  <front>
    <article-meta>
      <contrib-group>
        <contrib contrib-type="author">
          <name><surname>Lin</surname><given-names>Xiaoqi</given-names></name>
          <xref ref-type="aff" rid="aff1">1</xref>
          <email>xlin@northwestern.edu</email>
          <!-- ORCID 정보 -->
          <contrib-id contrib-id-type="orcid">0000-0002-0760-3950</contrib-id>
        </contrib>
      </contrib-group>
      <aff id="aff1">
        Department of Pathology Northwestern University...
      </aff>
    </article-meta>
  </front>
  <body>
    <sec sec-type="intro">
      <title>INTRODUCTION</title>
      <p>A few types of renal neoplasms may exhibit...</p>
    </sec>
    <sec sec-type="materials|methods">
      <title>MATERIALS AND METHODS</title>
      ...
    </sec>
  </body>
</article>
```

### 2.3 현재 문제점

| 문제 | 현재 상태 | 영향 |
|------|----------|------|
| **저자 정보 부족** | fullName만 추출 | ORCID, 소속, 순서 누락 |
| **저널 누락** | API 응답에 null | 메타데이터 불완전 |
| **HTML 엔티티** | `&#x02010;` 잔존 | 텍스트 품질 저하 |
| **섹션 경계** | 문자열 find 사용 | offset 부정확 |
| **Abstract HTML** | `<h4>Background</h4>` 포함 | 전처리 필요 |

---

## 3. PostgreSQL 스키마 매핑

### 3.1 papers 테이블 매핑

| PostgreSQL 필드 | Europe PMC 소스 | 파싱 로직 |
|----------------|-----------------|----------|
| `paper_id` | pmcid or pmid | `f"pmid:{pmid}"` 또는 `f"pmc:{pmcid}"` |
| `pmcid` | pmcid | 직접 매핑 |
| `pmid` | pmid | 직접 매핑 |
| `doi` | doi | 직접 매핑 |
| `title` | title | 직접 매핑 |
| `abstract` | abstract | HTML 태그 제거 후 매핑 |
| `journal` | journalTitle (API) 또는 XML 추출 | XML front/journal-meta에서 추출 |
| `year` | pubYear | int 변환 |
| `keywords` | keywordList | TEXT[] 변환 |
| `source` | - | `'europe_pmc'` 고정 |
| `is_open_access` | isOpenAccess | `== 'Y'` |
| `canonical_prefix` | - | `f"canonical/{paper_id}/"` |
| `canonical_text_version` | - | `'v1'` 초기값 |
| `canonical_text_hash` | - | SHA256(canonical_text) |
| `canonical_text_length` | - | len(canonical_text) |

### 3.2 paper_authors 테이블 매핑

| PostgreSQL 필드 | Europe PMC 소스 | 파싱 로직 |
|----------------|-----------------|----------|
| `paper_id` | - | papers.id (FK) |
| `author_order` | contrib 순서 | 1, 2, 3... |
| `author_name` | surname + given-names | `f"{given} {surname}"` |
| `is_corresponding` | corresp="yes" 또는 email 존재 | boolean |
| `orcid` | contrib-id[@type='orcid'] | 0000-xxxx-xxxx-xxxx |
| `affiliation` | aff 태그 내용 | 소속 기관명 |

---

## 4. 파싱 로직 상세

### 4.1 저자 파싱 (XML 기반)

```python
from lxml import etree
from dataclasses import dataclass

@dataclass
class Author:
    name: str
    order: int
    is_corresponding: bool
    orcid: str | None
    affiliation: str | None

def parse_authors(xml_content: str) -> list[Author]:
    """XML에서 저자 정보 추출"""
    root = etree.fromstring(xml_content.encode())

    # 소속 정보 매핑 (rid -> affiliation text)
    affiliations = {}
    for aff in root.findall(".//aff"):
        aff_id = aff.get("id")
        aff_text = "".join(aff.itertext()).strip()
        if aff_id:
            affiliations[aff_id] = aff_text

    authors = []
    for i, contrib in enumerate(root.findall(".//contrib[@contrib-type='author']"), 1):
        # 이름
        name_elem = contrib.find("name")
        if name_elem is not None:
            surname = name_elem.findtext("surname", "")
            given = name_elem.findtext("given-names", "")
            name = f"{given} {surname}".strip()
        else:
            name = contrib.findtext("string-name", "")

        # ORCID
        orcid_elem = contrib.find("contrib-id[@contrib-id-type='orcid']")
        orcid = orcid_elem.text if orcid_elem is not None else None

        # 교신저자 여부
        is_corresponding = (
            contrib.get("corresp") == "yes" or
            contrib.find("email") is not None
        )

        # 소속
        aff_ref = contrib.find("xref[@ref-type='aff']")
        aff_id = aff_ref.get("rid") if aff_ref is not None else None
        affiliation = affiliations.get(aff_id)

        authors.append(Author(
            name=name,
            order=i,
            is_corresponding=is_corresponding,
            orcid=orcid,
            affiliation=affiliation
        ))

    return authors
```

### 4.2 전문 전처리

```python
import html
import re

def preprocess_fulltext(raw_text: str) -> str:
    """전문 텍스트 전처리"""
    text = raw_text

    # 1. HTML 엔티티 디코딩
    # &#x02010; → - (하이픈)
    # &#x000a9; → © (저작권)
    # &#x000b1; → ± (플러스마이너스)
    text = html.unescape(text)

    # 2. 특수 유니코드 정규화
    replacements = {
        '\u2010': '-',   # 하이픈
        '\u2011': '-',   # non-breaking 하이픈
        '\u2012': '-',   # figure dash
        '\u2013': '-',   # en dash
        '\u2014': '-',   # em dash
        '\u00a0': ' ',   # non-breaking space
    }
    for old, new in replacements.items():
        text = text.replace(old, new)

    # 3. 연속 공백 정규화
    text = re.sub(r'\s+', ' ', text)

    # 4. 참조 번호 정리 (선택적)
    # "1 , 2 , 3" → "[1-3]" 또는 제거
    # text = re.sub(r'\d+\s*,\s*\d+(?:\s*,\s*\d+)*', '', text)

    return text.strip()
```

### 4.3 섹션 추출 (XML 기반 + offset 추적)

```python
from dataclasses import dataclass
from lxml import etree

@dataclass
class Section:
    name: str           # abstract, introduction, methods, results, discussion
    title: str          # 원본 제목
    text: str           # 섹션 텍스트
    offset_start: int   # canonical_text 내 시작 위치
    offset_end: int     # canonical_text 내 끝 위치

def extract_sections_from_xml(xml_content: str) -> tuple[str, list[Section]]:
    """
    XML에서 섹션 추출 + canonical_text 생성 + offset 계산

    Returns:
        (canonical_text, sections)
    """
    root = etree.fromstring(xml_content.encode())

    sections = []
    canonical_parts = []
    current_offset = 0

    # 섹션 타입 매핑
    section_type_map = {
        'abstract': 'abstract',
        'intro': 'introduction',
        'introduction': 'introduction',
        'materials|methods': 'methods',
        'methods': 'methods',
        'results': 'results',
        'discussion': 'discussion',
        'conclusions': 'conclusion',
    }

    # Abstract 추출
    abstract_elem = root.find(".//abstract")
    if abstract_elem is not None:
        abstract_text = " ".join(abstract_elem.itertext()).strip()
        abstract_text = preprocess_fulltext(abstract_text)

        sections.append(Section(
            name="abstract",
            title="Abstract",
            text=abstract_text,
            offset_start=current_offset,
            offset_end=current_offset + len(abstract_text)
        ))
        canonical_parts.append(abstract_text)
        current_offset += len(abstract_text) + 2  # +2 for "\n\n"
        canonical_parts.append("\n\n")

    # Body 섹션 추출
    for sec in root.findall(".//body/sec"):
        sec_type = sec.get("sec-type", "").lower()
        title_elem = sec.find("title")
        title = title_elem.text if title_elem is not None else ""

        # 섹션 이름 결정
        section_name = section_type_map.get(sec_type)
        if not section_name:
            # 제목으로 추론
            title_lower = title.lower()
            for key, name in section_type_map.items():
                if key in title_lower:
                    section_name = name
                    break
            else:
                section_name = "other"

        # 섹션 텍스트 추출
        section_text = " ".join(sec.itertext()).strip()
        section_text = preprocess_fulltext(section_text)

        sections.append(Section(
            name=section_name,
            title=title,
            text=section_text,
            offset_start=current_offset,
            offset_end=current_offset + len(section_text)
        ))
        canonical_parts.append(section_text)
        current_offset += len(section_text) + 2
        canonical_parts.append("\n\n")

    canonical_text = "".join(canonical_parts).strip()

    return canonical_text, sections
```

### 4.4 통합 파서

```python
from dataclasses import dataclass
import hashlib

@dataclass
class ParsedPaper:
    # 식별자
    paper_id: str
    pmid: str | None
    pmcid: str | None
    doi: str | None

    # 메타데이터
    title: str
    abstract: str
    journal: str | None
    year: int | None
    keywords: list[str]
    mesh_terms: list[str]

    # 저자
    authors: list[Author]

    # 전문
    canonical_text: str
    canonical_text_hash: str
    sections: list[Section]

    # 수집 정보
    source: str
    is_open_access: bool

def parse_paper(api_response: dict, xml_fulltext: str | None) -> ParsedPaper:
    """
    Europe PMC 응답을 ParsedPaper로 변환
    """
    # paper_id 결정
    pmcid = api_response.get("pmcid")
    pmid = api_response.get("pmid")
    paper_id = f"pmc:{pmcid}" if pmcid else f"pmid:{pmid}"

    # 저자 파싱 (XML이 있으면 XML에서, 없으면 API에서)
    if xml_fulltext:
        authors = parse_authors(xml_fulltext)
    else:
        # API 응답에서 기본 파싱
        authors = [
            Author(name=name, order=i+1, is_corresponding=False, orcid=None, affiliation=None)
            for i, name in enumerate(api_response.get("authors", []))
        ]

    # 전문 처리
    if xml_fulltext:
        canonical_text, sections = extract_sections_from_xml(xml_fulltext)
    else:
        # Abstract만 사용
        abstract_text = preprocess_fulltext(api_response.get("abstract", ""))
        canonical_text = abstract_text
        sections = [Section(
            name="abstract",
            title="Abstract",
            text=abstract_text,
            offset_start=0,
            offset_end=len(abstract_text)
        )]

    # 해시 계산
    text_hash = hashlib.sha256(canonical_text.encode()).hexdigest()

    # Abstract 전처리 (HTML 태그 제거)
    abstract = api_response.get("abstract", "")
    abstract = re.sub(r'<[^>]+>', ' ', abstract)
    abstract = preprocess_fulltext(abstract)

    return ParsedPaper(
        paper_id=paper_id,
        pmid=pmid,
        pmcid=pmcid,
        doi=api_response.get("doi"),
        title=api_response.get("title", ""),
        abstract=abstract,
        journal=api_response.get("journal"),  # TODO: XML에서 추출 필요
        year=api_response.get("year"),
        keywords=api_response.get("keywords", [])[:20],
        mesh_terms=api_response.get("mesh_terms", []),
        authors=authors,
        canonical_text=canonical_text,
        canonical_text_hash=text_hash,
        sections=sections,
        source="europe_pmc",
        is_open_access=api_response.get("is_open_access", False)
    )
```

---

## 5. 저장 로직

### 5.1 PostgreSQL 저장

```python
import asyncpg

async def save_paper(conn: asyncpg.Connection, paper: ParsedPaper) -> str:
    """논문 메타데이터 PostgreSQL 저장"""

    # 1. papers 테이블 INSERT
    paper_uuid = await conn.fetchval("""
        INSERT INTO papers (
            paper_id, pmcid, pmid, doi,
            title, abstract, journal, year, keywords,
            source, is_open_access,
            canonical_prefix, canonical_text_version,
            canonical_text_hash, canonical_text_length,
            status
        ) VALUES (
            $1, $2, $3, $4,
            $5, $6, $7, $8, $9,
            $10, $11,
            $12, $13,
            $14, $15,
            'collected'
        )
        ON CONFLICT (paper_id) DO UPDATE SET
            updated_at = NOW()
        RETURNING id
    """,
        paper.paper_id, paper.pmcid, paper.pmid, paper.doi,
        paper.title, paper.abstract, paper.journal, paper.year, paper.keywords,
        paper.source, paper.is_open_access,
        f"canonical/{paper.paper_id}/", "v1",
        paper.canonical_text_hash, len(paper.canonical_text)
    )

    # 2. paper_authors 테이블 INSERT
    for author in paper.authors:
        await conn.execute("""
            INSERT INTO paper_authors (
                paper_id, author_order, author_name,
                is_corresponding, orcid, affiliation
            ) VALUES ($1, $2, $3, $4, $5, $6)
            ON CONFLICT (paper_id, author_order) DO UPDATE SET
                author_name = EXCLUDED.author_name
        """,
            paper_uuid, author.order, author.name,
            author.is_corresponding, author.orcid, author.affiliation
        )

    return paper_uuid
```

### 5.2 S3 저장

```python
import boto3

def save_canonical_text(paper: ParsedPaper, bucket: str = "oaria-papers") -> str:
    """canonical_text를 S3에 저장"""
    s3 = boto3.client("s3")

    key = f"canonical/{paper.paper_id}/v1.txt"

    s3.put_object(
        Bucket=bucket,
        Key=key,
        Body=paper.canonical_text.encode("utf-8"),
        ContentType="text/plain; charset=utf-8",
        Metadata={
            "paper_id": paper.paper_id,
            "text_hash": paper.canonical_text_hash,
            "section_count": str(len(paper.sections))
        }
    )

    return key
```

---

## 6. 검증 및 테스트

### 6.1 검증 체크리스트

| 항목 | 검증 방법 |
|------|----------|
| **저자 순서** | XML 순서 == DB author_order |
| **ORCID 형식** | `^\d{4}-\d{4}-\d{4}-\d{4}$` |
| **offset 정확도** | `canonical_text[start:end] == section.text` |
| **HTML 엔티티** | `&#x` 패턴 없음 |
| **해시 일치** | SHA256(S3 text) == DB hash |

### 6.2 테스트 케이스

```python
def test_author_parsing():
    """저자 파싱 테스트"""
    xml = """<contrib contrib-type="author">
        <name><surname>Lin</surname><given-names>Xiaoqi</given-names></name>
        <contrib-id contrib-id-type="orcid">0000-0002-0760-3950</contrib-id>
        <email>xlin@northwestern.edu</email>
    </contrib>"""

    authors = parse_authors(f"<article>{xml}</article>")

    assert len(authors) == 1
    assert authors[0].name == "Xiaoqi Lin"
    assert authors[0].orcid == "0000-0002-0760-3950"
    assert authors[0].is_corresponding == True

def test_offset_accuracy():
    """offset 정확도 테스트"""
    canonical_text, sections = extract_sections_from_xml(sample_xml)

    for section in sections:
        extracted = canonical_text[section.offset_start:section.offset_end]
        assert extracted == section.text, f"Mismatch in {section.name}"

def test_html_entity_decoding():
    """HTML 엔티티 디코딩 테스트"""
    raw = "low&#x02010;grade oncocytic tumor"
    processed = preprocess_fulltext(raw)

    assert "&#x" not in processed
    assert "low-grade" in processed
```

---

## 7. 다음 단계

### Phase 1: 기본 파서 구현
- [ ] XML 기반 저자 파싱 (`parse_authors`)
- [ ] HTML 엔티티 전처리 (`preprocess_fulltext`)
- [ ] 섹션 추출 + offset 계산 (`extract_sections_from_xml`)

### Phase 2: PostgreSQL 연동
- [ ] papers 테이블 INSERT/UPSERT
- [ ] paper_authors 테이블 INSERT
- [ ] 트랜잭션 처리

### Phase 3: S3 연동
- [ ] canonical_text 저장
- [ ] 메타데이터 (hash, section_count)

### Phase 4: 테스트
- [ ] 단위 테스트 (저자, 섹션, offset)
- [ ] 통합 테스트 (API → 파싱 → 저장)
- [ ] 샘플 데이터 100건 검증

---

## 참고

- [OAR-18 Europe PMC 클라이언트](../../OAR-18/yts/src/europe_pmc_client.py)
- [OAR-20 PostgreSQL 스키마](../../OAR-20/yts/docs/postgresql-스키마-설계-v2.3.md)
- [OAR-18 청킹 설계](../../OAR-18/yts/docs/chunking-design.md)
