-- OAR-19/95: 논문 메타데이터 파싱용 스키마
-- 기반: OAR-20 PostgreSQL 스키마 설계 v2.3
-- 범위: papers, paper_authors 테이블만 (파싱 테스트용)

-- ============================================================
-- 확장 설치
-- ============================================================
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";  -- 저자 이름 부분 검색용

-- ============================================================
-- 1. papers (논문 메타데이터)
-- ============================================================
CREATE TABLE papers (
    -- 식별자
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    paper_id VARCHAR(100) UNIQUE NOT NULL,  -- pmc:PMC12345678 또는 pmid:12345678
    pmcid VARCHAR(20),
    pmid VARCHAR(20),
    doi VARCHAR(200),

    -- 메타데이터
    title TEXT NOT NULL,
    abstract TEXT,
    journal VARCHAR(500),
    year INTEGER,
    keywords TEXT[],

    -- 원문 관리 (S3 저장 구조)
    canonical_bucket VARCHAR(100) DEFAULT 'oaria-papers',
    canonical_prefix TEXT,        -- canonical/{paper_id}/ (버전 없이 prefix만)
    canonical_text_version VARCHAR(50) DEFAULT 'v1',
    canonical_text_hash VARCHAR(64),  -- SHA256 (canonical_text 기준)
    canonical_text_length INTEGER,

    -- 변경 추적 (v1.1 추가: 원본 변경 vs 파서 변경 구분용)
    raw_xml_hash VARCHAR(64),         -- SHA256 (원본 XML bytes 기준)
    parser_version VARCHAR(20) DEFAULT '1.0.0',  -- 파싱 로직 버전

    -- 수집 정보
    source VARCHAR(50) DEFAULT 'europe_pmc',
    source_url TEXT,
    is_open_access BOOLEAN DEFAULT TRUE,

    -- 처리 상태
    status VARCHAR(20) DEFAULT 'collected',  -- collected, parsed, chunked, indexed
    parsed_at TIMESTAMPTZ,
    chunked_at TIMESTAMPTZ,
    indexed_at TIMESTAMPTZ,

    -- 타임스탬프
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 인덱스
CREATE UNIQUE INDEX idx_papers_pmcid_unique ON papers(pmcid) WHERE pmcid IS NOT NULL;
CREATE UNIQUE INDEX idx_papers_pmid_unique ON papers(pmid) WHERE pmid IS NOT NULL;
CREATE UNIQUE INDEX idx_papers_doi_unique ON papers(doi) WHERE doi IS NOT NULL;
CREATE INDEX idx_papers_year ON papers(year);
CREATE INDEX idx_papers_status ON papers(status);
CREATE INDEX idx_papers_created_at ON papers(created_at);
CREATE INDEX idx_papers_keywords ON papers USING GIN(keywords);

-- ============================================================
-- 2. paper_authors (저자 - 정규화)
-- ============================================================
CREATE TABLE paper_authors (
    paper_id UUID REFERENCES papers(id) ON DELETE CASCADE,
    author_order SMALLINT NOT NULL,       -- 1, 2, 3... (저자 순서)
    author_name TEXT NOT NULL,
    is_corresponding BOOLEAN DEFAULT FALSE,
    orcid VARCHAR(50),
    affiliation TEXT,
    PRIMARY KEY (paper_id, author_order)
);

-- 저자 이름 검색용
CREATE INDEX idx_paper_authors_name ON paper_authors(author_name);
CREATE INDEX idx_paper_authors_name_trgm ON paper_authors USING GIN (author_name gin_trgm_ops);
CREATE INDEX idx_paper_authors_corresponding ON paper_authors(paper_id) WHERE is_corresponding = TRUE;

-- ============================================================
-- 3. paper_sections (섹션 메타데이터 - 청킹용)
-- ============================================================
CREATE TABLE paper_sections (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    paper_id UUID REFERENCES papers(id) ON DELETE CASCADE,

    section_name VARCHAR(50) NOT NULL,    -- abstract, introduction, methods, results, discussion
    section_title TEXT,                    -- 원본 섹션 제목
    section_order SMALLINT NOT NULL,       -- 섹션 순서

    -- offset 정보 (canonical_text 기준)
    offset_start INTEGER NOT NULL,
    offset_end INTEGER NOT NULL,
    char_count INTEGER GENERATED ALWAYS AS (offset_end - offset_start) STORED,

    created_at TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE(paper_id, section_order)  -- section_name은 중복 가능 (서브섹션 등)
);

CREATE INDEX idx_paper_sections_paper_id ON paper_sections(paper_id);

-- ============================================================
-- 4. updated_at 자동 갱신 트리거
-- ============================================================
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER papers_updated_at
    BEFORE UPDATE ON papers
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at();

-- ============================================================
-- 초기 데이터 확인용 뷰
-- ============================================================
CREATE VIEW v_papers_summary AS
SELECT
    p.paper_id,
    p.title,
    p.year,
    p.journal,
    p.status,
    COUNT(pa.author_order) as author_count,
    (SELECT COUNT(*) FROM paper_sections ps WHERE ps.paper_id = p.id) as section_count,
    p.canonical_text_length,
    p.created_at
FROM papers p
LEFT JOIN paper_authors pa ON p.id = pa.paper_id
GROUP BY p.id;

-- ============================================================
-- 완료 메시지
-- ============================================================
DO $$
BEGIN
    RAISE NOTICE '===========================================';
    RAISE NOTICE 'OAR-19 스키마 초기화 완료';
    RAISE NOTICE '테이블: papers, paper_authors, paper_sections';
    RAISE NOTICE '===========================================';
END $$;
