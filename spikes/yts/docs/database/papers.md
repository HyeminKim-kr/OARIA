# Papers 테이블 스키마

> **논문 메타데이터 및 관련 테이블**
>
> **Last Updated**: 2026-01-01
>
> **Owner**: Backend (Alembic)

---

## 개요

암 연구 논문의 메타데이터를 저장하고 관리하는 테이블 그룹입니다.

> **마이그레이션**: 모든 테이블은 `backend/alembic`에서 관리됩니다.

| 테이블 | 설명 |
|--------|------|
| `papers` | 논문 메타데이터 (제목, 초록, 저널 등) |
| `paper_authors` | 논문 저자 정보 |
| `paper_sections` | 논문 섹션 오프셋 정보 (청킹용) |
| `paper_relations` | 논문 간 관계 (정정/철회/코멘트) |

---

## papers (논문 메타데이터)

### 컬럼 정의

| 컬럼 | 타입 | Nullable | 기본값 | 설명 |
|------|------|----------|--------|------|
| **id** | `UUID` | NO | `gen_random_uuid()` | Primary Key |
| **paper_id** | `VARCHAR(100)` | NO | - | 고유 식별자 (예: `pmid:12345678`) |
| pmcid | `VARCHAR(20)` | YES | - | PubMed Central ID |
| pmid | `VARCHAR(20)` | YES | - | PubMed ID |
| doi | `VARCHAR(200)` | YES | - | Digital Object Identifier |
| **title** | `TEXT` | NO | - | 논문 제목 |
| abstract | `TEXT` | YES | - | 초록 |
| journal | `VARCHAR(500)` | YES | - | 저널명 |
| year | `INTEGER` | YES | - | 출판 연도 |
| keywords | `TEXT[]` | YES | - | 키워드 배열 |
| canonical_bucket | `VARCHAR(100)` | YES | `'oaria-papers'` | S3 버킷명 |
| canonical_prefix | `TEXT` | YES | - | S3 경로 프리픽스 |
| canonical_text_version | `VARCHAR(50)` | YES | `'v1'` | 정규화 텍스트 버전 |
| canonical_text_hash | `VARCHAR(64)` | YES | - | SHA256 해시 |
| canonical_text_length | `INTEGER` | YES | - | 텍스트 길이 |
| raw_xml_hash | `VARCHAR(64)` | YES | - | 원본 XML 해시 |
| parser_version | `VARCHAR(20)` | YES | `'1.0.0'` | 파서 버전 |
| source | `VARCHAR(50)` | YES | `'europe_pmc'` | 데이터 소스 |
| source_url | `TEXT` | YES | - | 원본 URL |
| is_open_access | `BOOLEAN` | YES | `TRUE` | 오픈액세스 여부 |
| status | `VARCHAR(20)` | YES | `'collected'` | 처리 상태 |
| chunked_at | `TIMESTAMPTZ` | YES | - | 청킹 완료 시각 |
| indexed_at | `TIMESTAMPTZ` | YES | - | 벡터 인덱싱 완료 시각 |
| embedding_status | `VARCHAR(20)` | YES | - | 임베딩 상태 |
| embedding_chunk_count | `INTEGER` | YES | `0` | 생성된 청크 수 |
| embedding_error | `TEXT` | YES | - | 임베딩 에러 메시지 |
| embedding_at | `TIMESTAMPTZ` | YES | - | 임베딩 완료 시각 |
| pub_types | `TEXT[]` | YES | - | 논문 유형 (research-article, review 등) |
| has_correction | `BOOLEAN` | YES | `FALSE` | 정정(Correction) 존재 여부 |
| has_erratum | `BOOLEAN` | YES | `FALSE` | 오류정정(Erratum) 존재 여부 |
| has_retraction | `BOOLEAN` | YES | `FALSE` | 철회(Retraction) 여부 |
| created_at | `TIMESTAMPTZ` | YES | `NOW()` | 생성 시각 |
| updated_at | `TIMESTAMPTZ` | YES | `NOW()` | 수정 시각 |

### 상태 값

#### status

| 값 | 설명 |
|----|------|
| `collected` | 수집 완료 |
| `chunked` | 청킹 완료 |
| `indexed` | 벡터 인덱싱 완료 |

#### embedding_status

| 값 | 설명 |
|----|------|
| `pending` | 임베딩 대기 |
| `processing` | 임베딩 처리 중 |
| `completed` | 임베딩 완료 |
| `failed` | 임베딩 실패 |

### 인덱스

```sql
-- Unique 인덱스 (Partial)
CREATE UNIQUE INDEX idx_papers_pmcid_unique ON papers(pmcid) WHERE pmcid IS NOT NULL;
CREATE UNIQUE INDEX idx_papers_pmid_unique ON papers(pmid) WHERE pmid IS NOT NULL;
CREATE UNIQUE INDEX idx_papers_doi_unique ON papers(doi) WHERE doi IS NOT NULL;

-- 일반 인덱스
CREATE INDEX idx_papers_year ON papers(year);
CREATE INDEX idx_papers_status ON papers(status);
CREATE INDEX idx_papers_created_at ON papers(created_at);
CREATE INDEX idx_papers_keywords ON papers USING GIN(keywords);
CREATE INDEX idx_papers_embedding_status ON papers(embedding_status);
CREATE INDEX idx_papers_embedding_pending ON papers(created_at)
    WHERE embedding_status IS NULL OR embedding_status = 'pending';
```

### DDL

```sql
CREATE TABLE papers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    paper_id VARCHAR(100) UNIQUE NOT NULL,
    pmcid VARCHAR(20),
    pmid VARCHAR(20),
    doi VARCHAR(200),
    title TEXT NOT NULL,
    abstract TEXT,
    journal VARCHAR(500),
    year INTEGER,
    keywords TEXT[],
    canonical_bucket VARCHAR(100) DEFAULT 'oaria-papers',
    canonical_prefix TEXT,
    canonical_text_version VARCHAR(50) DEFAULT 'v1',
    canonical_text_hash VARCHAR(64),
    canonical_text_length INTEGER,
    raw_xml_hash VARCHAR(64),
    parser_version VARCHAR(20) DEFAULT '1.0.0',
    source VARCHAR(50) DEFAULT 'europe_pmc',
    source_url TEXT,
    is_open_access BOOLEAN DEFAULT TRUE,
    status VARCHAR(20) DEFAULT 'collected',
    chunked_at TIMESTAMPTZ,
    indexed_at TIMESTAMPTZ,
    embedding_status VARCHAR(20),
    embedding_chunk_count INTEGER DEFAULT 0,
    embedding_error TEXT,
    embedding_at TIMESTAMPTZ,
    pub_types TEXT[],
    has_correction BOOLEAN DEFAULT FALSE,
    has_erratum BOOLEAN DEFAULT FALSE,
    has_retraction BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

---

## paper_relations (논문 관계)

논문 간의 관계(정정, 철회, 코멘트 등)를 저장합니다.

### 컬럼 정의

| 컬럼 | 타입 | Nullable | 기본값 | 설명 |
|------|------|----------|--------|------|
| **id** | `UUID` | NO | `gen_random_uuid()` | Primary Key |
| **source_pmid** | `TEXT` | NO | - | 관계 출처 논문 PMID (Correction/Retraction) |
| **target_pmid** | `TEXT` | NO | - | 대상 논문 PMID (원문) |
| **relation_type** | `TEXT` | NO | - | 정규화된 관계 타입 |
| raw_type | `TEXT` | YES | - | 원본 관계 문자열 |
| reference | `TEXT` | YES | - | 참조 문자열 |
| created_at | `TIMESTAMPTZ` | YES | `NOW()` | 생성 시각 |

### relation_type 값

| 값 | 설명 | 플래그 |
|----|------|--------|
| `retraction` | 철회 | has_retraction=true |
| `erratum` | 오류정정 | has_erratum=true |
| `correction` | 정정 | has_correction=true |
| `comment` | 코멘트 | (플래그 없음) |

### 인덱스

```sql
-- 유니크 제약 (멱등성)
CREATE UNIQUE INDEX uq_paper_relations
ON paper_relations(source_pmid, target_pmid, relation_type);

-- 조회용 인덱스
CREATE INDEX idx_paper_relations_target ON paper_relations(target_pmid);
CREATE INDEX idx_paper_relations_source ON paper_relations(source_pmid);
```

### DDL

```sql
CREATE TABLE paper_relations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_pmid TEXT NOT NULL,
    target_pmid TEXT NOT NULL,
    relation_type TEXT NOT NULL,
    raw_type TEXT,
    reference TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE UNIQUE INDEX uq_paper_relations
ON paper_relations(source_pmid, target_pmid, relation_type);

CREATE INDEX idx_paper_relations_target ON paper_relations(target_pmid);
CREATE INDEX idx_paper_relations_source ON paper_relations(source_pmid);
```

---

## paper_authors (저자)

### 컬럼 정의

| 컬럼 | 타입 | Nullable | 기본값 | 설명 |
|------|------|----------|--------|------|
| **paper_id** | `UUID` | NO | - | PK, FK → papers.id |
| **author_order** | `SMALLINT` | NO | - | PK, 저자 순서 |
| **author_name** | `TEXT` | NO | - | 저자명 |
| is_corresponding | `BOOLEAN` | YES | `FALSE` | 교신저자 여부 |
| orcid | `VARCHAR(50)` | YES | - | ORCID ID |
| affiliation | `TEXT` | YES | - | 소속 기관 |

### 인덱스

```sql
CREATE INDEX idx_paper_authors_name ON paper_authors(author_name);
CREATE INDEX idx_paper_authors_name_trgm ON paper_authors USING GIN (author_name gin_trgm_ops);
CREATE INDEX idx_paper_authors_corresponding ON paper_authors(paper_id) WHERE is_corresponding = TRUE;
```

### DDL

```sql
CREATE TABLE paper_authors (
    paper_id UUID REFERENCES papers(id) ON DELETE CASCADE,
    author_order SMALLINT NOT NULL,
    author_name TEXT NOT NULL,
    is_corresponding BOOLEAN DEFAULT FALSE,
    orcid VARCHAR(50),
    affiliation TEXT,
    PRIMARY KEY (paper_id, author_order)
);
```

---

## paper_sections (섹션 오프셋)

논문 원문을 청킹할 때 섹션 경계를 추적하기 위한 테이블입니다.

### 컬럼 정의

| 컬럼 | 타입 | Nullable | 기본값 | 설명 |
|------|------|----------|--------|------|
| **id** | `UUID` | NO | `gen_random_uuid()` | Primary Key |
| **paper_id** | `UUID` | NO | - | FK → papers.id |
| **section_order** | `SMALLINT` | NO | - | 섹션 순서 |
| **section_name** | `VARCHAR(200)` | NO | - | 섹션 타입 (ABSTRACT, INTRO 등) |
| section_title | `TEXT` | YES | - | 섹션 제목 |
| **offset_start** | `INTEGER` | NO | - | 시작 위치 (UTF-8 char index) |
| **offset_end** | `INTEGER` | NO | - | 끝 위치 |
| created_at | `TIMESTAMPTZ` | YES | `NOW()` | 생성 시각 |

### 인덱스

```sql
CREATE INDEX idx_paper_sections_paper_id ON paper_sections(paper_id);
CREATE INDEX idx_paper_sections_name ON paper_sections(section_name);
```

### DDL

```sql
CREATE TABLE paper_sections (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    paper_id UUID REFERENCES papers(id) ON DELETE CASCADE,
    section_order SMALLINT NOT NULL,
    section_name VARCHAR(200) NOT NULL,
    section_title TEXT,
    offset_start INTEGER NOT NULL,
    offset_end INTEGER NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(paper_id, section_order)
);
```

---

## 쿼리 예시

### 임베딩 대기 중인 논문 조회

```sql
SELECT id, paper_id, title, abstract
FROM papers
WHERE (embedding_status IS NULL OR embedding_status = 'pending')
  AND abstract IS NOT NULL
ORDER BY created_at
LIMIT 100;
```

### 논문과 저자 함께 조회

```sql
SELECT
    p.paper_id,
    p.title,
    p.journal,
    p.year,
    ARRAY_AGG(pa.author_name ORDER BY pa.author_order) AS authors
FROM papers p
LEFT JOIN paper_authors pa ON p.id = pa.paper_id
WHERE p.paper_id = 'pmid:12345678'
GROUP BY p.id;
```

### 저자 이름으로 논문 검색

```sql
SELECT DISTINCT p.*
FROM papers p
JOIN paper_authors pa ON p.id = pa.paper_id
WHERE pa.author_name ILIKE '%kim%'
ORDER BY p.year DESC;
```

---

## SQLAlchemy 모델

```python
# app/models/paper.py

class Paper(Base):
    __tablename__ = "papers"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    paper_id: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    # ... (전체 모델은 app/models/paper.py 참조)

    authors: Mapped[list["PaperAuthor"]] = relationship(
        "PaperAuthor", back_populates="paper", order_by="PaperAuthor.author_order"
    )


class PaperAuthor(Base):
    __tablename__ = "paper_authors"

    paper_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("papers.id", ondelete="CASCADE"), primary_key=True
    )
    author_order: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    author_name: Mapped[str] = mapped_column(Text, nullable=False)
    # ...
```

---

## 관련 문서

- [README.md](./README.md) - 데이터베이스 개요
- [batch.md](./batch.md) - 논문 수집 배치 작업 테이블
