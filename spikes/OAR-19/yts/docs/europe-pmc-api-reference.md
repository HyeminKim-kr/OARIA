# Europe PMC API 응답 구조 레퍼런스

> **목적**: Europe PMC API 응답 필드를 정확히 이해하고 파싱 로직 검증
>
> **작성일**: 2025-12-26
>
> **API 문서**: https://europepmc.org/RestfulWebService

---

## 1. API 엔드포인트

### 1.1 검색 API (Search)

```
GET https://www.ebi.ac.uk/europepmc/webservices/rest/search
```

| 파라미터 | 필수 | 설명 | 예시 |
|----------|------|------|------|
| `query` | O | 검색 쿼리 | `lung cancer AND OPEN_ACCESS:Y` |
| `format` | O | 응답 형식 | `json` |
| `resultType` | - | 결과 상세도 | `core` (상세), `lite` (간략) |
| `pageSize` | - | 결과 수 (max 1000) | `25` |
| `cursorMark` | - | 페이지네이션 | `*` (첫 페이지) |

### 1.2 전문 API (Full Text XML)

```
GET https://www.ebi.ac.uk/europepmc/webservices/rest/{PMCID}/fullTextXML
```

| 파라미터 | 필수 | 설명 | 예시 |
|----------|------|------|------|
| `PMCID` | O | PMC ID | `PMC12664089` |

---

## 2. Search API 응답 필드 (resultType=core)

### 2.1 전체 필드 목록

```
id                      : str     - 내부 ID (보통 PMID)
source                  : str     - 소스 (MED, PMC, etc.)
pmid                    : str     - PubMed ID
pmcid                   : str     - PMC ID (PMCxxxxxxxx)
fullTextIdList          : dict    - 전문 ID 목록
doi                     : str     - DOI
title                   : str     - 논문 제목
authorString            : str     - 저자 문자열 (간략)
authorList              : dict    - 저자 상세 목록 ★
authorIdList            : dict    - 저자 ID 목록 (ORCID)
journalInfo             : dict    - 저널 정보 ★
pubYear                 : str     - 출판 연도
pageInfo                : str     - 페이지 정보
abstractText            : str     - 초록
affiliation             : str     - 소속 (첫 번째만)
publicationStatus       : str     - 출판 상태
language                : str     - 언어
pubModel                : str     - 출판 모델
pubTypeList             : dict    - 출판 유형
grantsList              : dict    - 연구비 지원 목록
meshHeadingList         : dict    - MeSH 용어 ★
keywordList             : dict    - 키워드 ★
subsetList              : dict    - 서브셋 목록
fullTextUrlList         : dict    - 전문 URL 목록
isOpenAccess            : str     - Open Access 여부 (Y/N)
inEPMC                  : str     - Europe PMC 수록 여부
inPMC                   : str     - PMC 수록 여부
hasPDF                  : str     - PDF 제공 여부
hasBook                 : str     - 도서 여부
hasSuppl                : str     - 보충자료 여부
citedByCount            : int     - 인용 수
hasData                 : str     - 데이터 제공 여부
hasReferences           : str     - 참고문헌 여부
hasTextMinedTerms       : str     - 텍스트 마이닝 용어 여부
hasDbCrossReferences    : str     - DB 교차참조 여부
hasLabsLinks            : str     - Labs 링크 여부
license                 : str     - 라이선스 (cc by, etc.)
hasEvaluations          : str     - 평가 여부
authMan                 : str     - 저자 원고 여부
epmcAuthMan             : str     - EPMC 저자 원고
nihAuthMan              : str     - NIH 저자 원고
hasTMAccessionNumbers   : str     - 등록번호 여부
dateOfCompletion        : str     - 완료일
dateOfCreation          : str     - 생성일
firstIndexDate          : str     - 최초 색인일
fullTextReceivedDate    : str     - 전문 수신일
dateOfRevision          : str     - 수정일
firstPublicationDate    : str     - 최초 출판일
```

---

## 3. 핵심 필드 상세 구조

### 3.1 authorList (저자 목록) ★

```json
{
  "authorList": {
    "author": [
      {
        "fullName": "Zitricky F",
        "firstName": "Frantisek",
        "lastName": "Zitricky",
        "initials": "F",
        "authorId": {
          "type": "ORCID",
          "value": "0000-0001-7600-7143"
        },
        "authorAffiliationDetailsList": {
          "authorAffiliation": [
            {
              "affiliation": "Biomedical Center, Faculty of Medicine..."
            }
          ]
        }
      }
    ]
  }
}
```

| 필드 | 타입 | 설명 | 파싱 참고 |
|------|------|------|----------|
| `fullName` | str | 전체 이름 (약식) | "Kim JS" 형태 |
| `firstName` | str | 이름 | |
| `lastName` | str | 성 | |
| `initials` | str | 이니셜 | |
| `authorId.type` | str | ID 타입 | "ORCID" |
| `authorId.value` | str | ID 값 | "0000-xxxx-xxxx-xxxx" |
| `authorAffiliationDetailsList` | dict | 소속 목록 | 여러 소속 가능 |

**주의**:
- `authorId`는 일부 저자만 가지고 있음
- `authorAffiliationDetailsList`도 없을 수 있음
- 교신저자 정보는 **JSON에 없음** → XML에서만 확인 가능 (`corresp="yes"`)

### 3.2 journalInfo (저널 정보) ★

```json
{
  "journalInfo": {
    "issue": "23",
    "volume": "14",
    "journalIssueId": 4056427,
    "dateOfPublication": "2025 Dec",
    "monthOfPublication": 12,
    "yearOfPublication": 2025,
    "printPublicationDate": "2025-12-01",
    "journal": {
      "title": "Cancer medicine",
      "medlineAbbreviation": "Cancer Med",
      "isoabbreviation": "Cancer Med",
      "nlmid": "101595310",
      "issn": "2045-7634",
      "essn": "2045-7634"
    }
  }
}
```

| 필드 | 타입 | 설명 |
|------|------|------|
| `issue` | str | 호 |
| `volume` | str | 권 |
| `yearOfPublication` | int | 출판 연도 |
| `journal.title` | str | 저널 제목 |
| `journal.issn` | str | ISSN |

**주의**:
- `journalTitle` (최상위)은 없음 → `journalInfo.journal.title` 사용
- OAR-18에서 `item.get("journalTitle")`로 조회하면 `None`

### 3.3 meshHeadingList (MeSH 용어) ★

```json
{
  "meshHeadingList": {
    "meshHeading": [
      {
        "majorTopic_YN": "Y",
        "descriptorName": "Lung Neoplasms",
        "meshQualifierList": {
          "meshQualifier": [
            {
              "abbreviation": "GE",
              "qualifierName": "genetics",
              "majorTopic_YN": "N"
            }
          ]
        }
      }
    ]
  }
}
```

| 필드 | 타입 | 설명 |
|------|------|------|
| `descriptorName` | str | MeSH 용어 이름 |
| `majorTopic_YN` | str | 주요 주제 여부 |
| `meshQualifierList` | dict | 수식어 목록 |

### 3.4 keywordList (키워드)

```json
{
  "keywordList": {
    "keyword": [
      "Adenocarcinoma",
      "Incidence trend",
      "Proband"
    ]
  }
}
```

---

## 4. Full Text XML 구조

### 4.1 문서 구조

```xml
<article>
  <front>
    <journal-meta>...</journal-meta>
    <article-meta>
      <article-id pub-id-type="pmcid">12664089</article-id>
      <article-id pub-id-type="doi">10.1002/cam4.71431</article-id>
      <title-group>
        <article-title>논문 제목</article-title>
      </title-group>
      <contrib-group>
        <!-- 저자 목록 -->
      </contrib-group>
      <aff id="...">
        <!-- 소속 정보 -->
      </aff>
      <abstract>...</abstract>
      <kwd-group>
        <!-- 키워드 -->
      </kwd-group>
    </article-meta>
  </front>
  <body>
    <sec sec-type="intro">
      <title>INTRODUCTION</title>
      <p>...</p>
    </sec>
    <sec sec-type="methods">
      <title>MATERIALS AND METHODS</title>
      <p>...</p>
    </sec>
    <!-- ... -->
  </body>
  <back>
    <ref-list>
      <!-- 참고문헌 -->
    </ref-list>
  </back>
</article>
```

### 4.2 저자 정보 (XML) ★

```xml
<contrib id="cam471431-cr-0006" contrib-type="author" corresp="yes">
  <name>
    <surname>Hemminki</surname>
    <given-names>Kari</given-names>
  </name>
  <contrib-id contrib-id-type="orcid" authenticated="false">
    https://orcid.org/0000-0002-2769-3316
  </contrib-id>
  <xref rid="cam471431-aff-0001" ref-type="aff">
    <sup>1</sup>
  </xref>
  <address>
    <email>k.hemminki@dkfz.de</email>
  </address>
</contrib>
```

| 속성/요소 | 설명 | JSON에 있음? |
|-----------|------|-------------|
| `contrib-type="author"` | 저자 타입 | O |
| `corresp="yes"` | **교신저자 여부** | **X** (XML만) |
| `name/surname` | 성 | O |
| `name/given-names` | 이름 | O |
| `contrib-id[@type='orcid']` | ORCID | O |
| `xref[@ref-type='aff']` | 소속 참조 | O (다른 형태) |
| `email` | 이메일 | **X** (XML만) |

### 4.3 소속 정보 (XML)

```xml
<aff id="cam471431-aff-0001">
  <label><sup>1</sup></label>
  <named-content content-type="organisation-division">
    Biomedical Center, Faculty of Medicine in Pilsen
  </named-content>
  <institution>Charles University</institution>
  <city>Pilsen</city>
  <country country="CZ">Czech Republic</country>
</aff>
```

---

## 5. JSON vs XML 비교

| 정보 | JSON (Search API) | XML (fullTextXML) |
|------|-------------------|-------------------|
| **PMID/PMCID/DOI** | O | O |
| **제목** | O | O |
| **초록** | O | O |
| **저널명** | O (`journalInfo.journal.title`) | O |
| **출판연도** | O (`pubYear`) | O |
| **저자 이름** | O | O |
| **저자 순서** | O (배열 순서) | O |
| **ORCID** | O (`authorId.value`) | O |
| **소속** | O (`authorAffiliationDetailsList`) | O (더 상세) |
| **교신저자** | **X** | O (`corresp="yes"` 또는 `xref[@ref-type='corresp']`) |
| **이메일** | **X** | O |
| **MeSH 용어** | O | **X** (body에 없음) |
| **키워드** | O | O |
| **섹션 구조** | **X** | O |
| **전문 텍스트** | **X** | O |

---

## 6. 파싱 시 주의사항

### 6.1 PMCID pub-id-type 변형 (중요!)

**XML에서 PMCID의 `pub-id-type`이 `pmc` 또는 `pmcid`일 수 있음**

```xml
<!-- 일부 논문 -->
<article-id pub-id-type="pmc">PMC12345678</article-id>

<!-- 대부분의 논문 (실제 API 응답) -->
<article-id pub-id-type="pmcid">12664089</article-id>
```

```python
# 잘못된 예 (한 가지만 체크)
pmcid_elem = root.find(".//article-id[@pub-id-type='pmc']")

# 올바른 예 (둘 다 체크)
pmcid_elem = root.find(".//article-id[@pub-id-type='pmcid']")
if pmcid_elem is None:
    pmcid_elem = root.find(".//article-id[@pub-id-type='pmc']")
```

### 6.2 필드 누락 케이스

```python
# 잘못된 예 (OAR-18)
journal = item.get("journalTitle")  # → None

# 올바른 예
journal_info = item.get("journalInfo", {})
journal = journal_info.get("journal", {}).get("title")
```

### 6.3 교신저자 판별 (중요! - 2가지 형식)

**JSON에서는 교신저자 정보가 없음** → XML 파싱 필수

**⚠️ 실제 API 응답 크로스체크 결과 (2025-12-26)**:
- 일부 논문: `corresp="yes"` 속성 사용
- 대부분의 논문: `<xref ref-type="corresp">` 요소 사용 (더 흔함)

```xml
<!-- 방법 1: corresp 속성 (일부 논문) -->
<contrib contrib-type="author" corresp="yes">
  <name><surname>Kim</surname>...</name>
</contrib>

<!-- 방법 2: xref ref-type="corresp" (더 흔함) ★ -->
<contrib contrib-type="author">
  <name><surname>Papavassiliou</surname>...</name>
  <xref rid="c1-biomolecules-15-01525" ref-type="corresp">*</xref>
</contrib>
```

```python
# ❌ 잘못된 예 (한 가지만 체크)
is_corresponding = contrib.get("corresp") == "yes"

# ✅ 올바른 예 (둘 다 체크)
is_corresponding = (
    contrib.get("corresp") == "yes"
    or contrib.find(".//xref[@ref-type='corresp']") is not None
)
```

### 6.4 ORCID 형식

```python
# JSON: 순수 ID
"0000-0001-7600-7143"

# XML: URL 형태
"https://orcid.org/0000-0001-7600-7143"

# 정규화 필요
orcid = orcid.replace("https://orcid.org/", "")
```

### 6.5 소속 정보

```python
# JSON: 단순 문자열
"Biomedical Center, Faculty of Medicine in Pilsen, Charles University, Pilsen, Czech Republic."

# XML: 구조화된 데이터
<named-content>Division</named-content>
<institution>University</institution>
<city>City</city>
<country>Country</country>
```

---

## 7. 권장 파싱 전략

### 7.1 메타데이터 소스 우선순위

| 정보 | 1순위 | 2순위 |
|------|-------|-------|
| 기본 메타데이터 (PMID, DOI, 제목) | JSON | XML |
| 저자 이름, ORCID, 소속 | **JSON** (더 정리됨) | XML |
| **교신저자** | **XML** | - |
| MeSH, 키워드 | JSON | - |
| 섹션, 전문 | **XML** | - |

### 7.2 권장 파싱 흐름

```
1. Search API (JSON) 호출
   → 기본 메타데이터, 저자, MeSH, 키워드 추출

2. fullTextXML 호출 (PMCID 있는 경우)
   → 교신저자 확인 (corresp="yes")
   → 섹션 추출 (body/sec)
   → canonical_text 생성
   → offset 계산
```

---

## 8. 샘플 데이터

### 8.1 Search API 전체 응답 예시

<details>
<summary>펼쳐보기</summary>

```json
{
  "id": "41317095",
  "source": "MED",
  "pmid": "41317095",
  "pmcid": "PMC12664089",
  "doi": "10.1002/cam4.71431",
  "title": "Second Primary Lung Cancer Associated With Family History of Lung Cancer.",
  "authorString": "Zitricky F, Sundquist K, Sundquist J, Försti A, Hemminki A, Hemminki K.",
  "journalInfo": {
    "issue": "23",
    "volume": "14",
    "journal": {
      "title": "Cancer medicine",
      "issn": "2045-7634"
    }
  },
  "pubYear": "2025",
  "abstractText": "BACKGROUND: Second primary lung cancer (SPLC)...",
  "authorList": {
    "author": [
      {
        "fullName": "Zitricky F",
        "firstName": "Frantisek",
        "lastName": "Zitricky",
        "authorId": {
          "type": "ORCID",
          "value": "0000-0001-7600-7143"
        },
        "authorAffiliationDetailsList": {
          "authorAffiliation": [
            {"affiliation": "Biomedical Center..."}
          ]
        }
      }
    ]
  },
  "meshHeadingList": {
    "meshHeading": [
      {"descriptorName": "Lung Neoplasms", "majorTopic_YN": "Y"}
    ]
  },
  "keywordList": {
    "keyword": ["Adenocarcinoma", "Incidence trend"]
  },
  "isOpenAccess": "Y",
  "inEPMC": "Y",
  "license": "cc by"
}
```

</details>

---

## 참고 자료

- [Europe PMC REST API 문서](https://europepmc.org/RestfulWebService)
- [Europe PMC API Reference PDF](https://europepmc.org/docs/EBI_Europe_PMC_Web_Service_Reference.pdf)
- [JATS XML 표준](https://jats.nlm.nih.gov/)
