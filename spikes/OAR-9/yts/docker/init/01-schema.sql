-- OAR-9: 논문 수집 파이프라인 스키마
-- 기반: OAR-20 PostgreSQL 스키마 v2.5

-- 확장 활성화
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- ================================================================
-- 1. papers (논문 메타데이터)
-- ================================================================
CREATE TABLE papers (
    -- 식별자
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    paper_id VARCHAR(100) UNIQUE NOT NULL,  -- pmid:12345678 형식
    pmcid VARCHAR(20),
    pmid VARCHAR(20),
    doi VARCHAR(200),

    -- 메타데이터
    title TEXT NOT NULL,
    abstract TEXT,
    journal VARCHAR(500),
    year INTEGER,
    keywords TEXT[],

    -- 원문 관리 (S3)
    canonical_bucket VARCHAR(100) DEFAULT 'oaria-papers',
    canonical_prefix TEXT,
    canonical_text_version VARCHAR(50) DEFAULT 'v1',
    canonical_text_hash VARCHAR(64),
    canonical_text_length INTEGER,

    -- 변경 추적
    raw_xml_hash VARCHAR(64),
    parser_version VARCHAR(20) DEFAULT '1.0.0',

    -- 수집 정보
    source VARCHAR(50) DEFAULT 'europe_pmc',
    source_url TEXT,
    is_open_access BOOLEAN DEFAULT TRUE,

    -- 처리 상태
    status VARCHAR(20) DEFAULT 'collected',
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

-- ================================================================
-- 2. paper_authors (저자)
-- ================================================================
CREATE TABLE paper_authors (
    paper_id UUID REFERENCES papers(id) ON DELETE CASCADE,
    author_order SMALLINT NOT NULL,
    author_name TEXT NOT NULL,
    is_corresponding BOOLEAN DEFAULT FALSE,
    orcid VARCHAR(50),
    affiliation TEXT,
    PRIMARY KEY (paper_id, author_order)
);

CREATE INDEX idx_paper_authors_name ON paper_authors(author_name);
CREATE INDEX idx_paper_authors_name_trgm ON paper_authors USING GIN (author_name gin_trgm_ops);

-- ================================================================
-- 3. paper_sections (섹션 offset 정보)
-- ================================================================
CREATE TABLE paper_sections (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    paper_id UUID REFERENCES papers(id) ON DELETE CASCADE,
    section_order SMALLINT NOT NULL,
    section_name VARCHAR(50) NOT NULL,
    section_title VARCHAR(500),
    offset_start INTEGER NOT NULL,
    offset_end INTEGER NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(paper_id, section_order)
);

CREATE INDEX idx_paper_sections_paper_id ON paper_sections(paper_id);
CREATE INDEX idx_paper_sections_name ON paper_sections(section_name);

-- ================================================================
-- 4. collection_jobs (수집 작업 큐) - 배치용
-- ================================================================
CREATE TABLE collection_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_type VARCHAR(20) NOT NULL,
    priority INT DEFAULT 10,
    query TEXT NOT NULL,
    params JSONB,
    api_name VARCHAR(50) DEFAULT 'europe_pmc',
    status VARCHAR(20) DEFAULT 'pending',
    checkpoint JSONB,
    attempt_count INT DEFAULT 0,
    max_attempts INT DEFAULT 5,
    next_run_at TIMESTAMPTZ,
    locked_at TIMESTAMPTZ,
    locked_by VARCHAR(100),
    last_error_code VARCHAR(10),
    last_error_message TEXT,
    last_error_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ
);

CREATE INDEX idx_jobs_pending ON collection_jobs (priority, created_at)
    WHERE status IN ('pending', 'delayed') AND (next_run_at IS NULL OR next_run_at <= NOW());

-- ================================================================
-- 5. watermarks (증분 수집 상태)
-- ================================================================
CREATE TABLE watermarks (
    id VARCHAR(100) PRIMARY KEY,
    last_completed_at TIMESTAMPTZ NOT NULL,
    overlap_days INT DEFAULT 2,
    last_query TEXT,
    last_result_count INT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ================================================================
-- 완료 메시지
-- ================================================================
DO $$
BEGIN
    RAISE NOTICE 'OAR-9 스키마 초기화 완료!';
    RAISE NOTICE '테이블: papers, paper_authors, paper_sections, collection_jobs, watermarks';
END $$;
