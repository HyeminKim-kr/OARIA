-- ============================================================
-- 암 논문 수집 서비스 스키마
-- 기반: OAR-20 PostgreSQL v2.5 + OAR-21 search_queries
-- ============================================================

-- 확장 활성화
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- ============================================================
-- 1. papers (논문 메타데이터)
-- ============================================================
CREATE TABLE papers (
    -- 식별자
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    paper_id VARCHAR(100) UNIQUE NOT NULL,  -- pmid:12345678 또는 pmc:PMC12345678
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
    canonical_prefix TEXT,                    -- canonical/pmid_12345678/
    canonical_text_version VARCHAR(50) DEFAULT 'v1',
    canonical_text_hash VARCHAR(64),          -- SHA256
    canonical_text_length INTEGER,

    -- 변경 추적
    raw_xml_hash VARCHAR(64),                 -- 원본 XML 해시
    parser_version VARCHAR(20) DEFAULT '1.0.0',

    -- 수집 정보
    source VARCHAR(50) DEFAULT 'europe_pmc',
    source_url TEXT,
    is_open_access BOOLEAN DEFAULT TRUE,

    -- 처리 상태
    status VARCHAR(20) DEFAULT 'collected',   -- collected, chunked, indexed
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
-- 2. paper_authors (저자)
-- ============================================================
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
CREATE INDEX idx_paper_authors_corresponding ON paper_authors(paper_id) WHERE is_corresponding = TRUE;

-- ============================================================
-- 3. paper_sections (섹션 offset 정보)
-- ============================================================
CREATE TABLE paper_sections (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    paper_id UUID REFERENCES papers(id) ON DELETE CASCADE,
    section_order SMALLINT NOT NULL,
    section_name VARCHAR(200) NOT NULL,       -- 섹션 타입 (여유롭게)
    section_title TEXT,                       -- 섹션 제목 (제한 없음)
    offset_start INTEGER NOT NULL,            -- char index (UTF-8 decoded)
    offset_end INTEGER NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(paper_id, section_order)
);

CREATE INDEX idx_paper_sections_paper_id ON paper_sections(paper_id);
CREATE INDEX idx_paper_sections_name ON paper_sections(section_name);

-- ============================================================
-- 4. search_queries (검색 쿼리 관리) - OAR-21
-- ============================================================
CREATE TABLE search_queries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- 쿼리 정보
    name VARCHAR(100) NOT NULL,
    query TEXT NOT NULL,                      -- Europe PMC 검색 쿼리
    description TEXT,

    -- 수집 설정
    is_active BOOLEAN DEFAULT TRUE,
    priority INT DEFAULT 10,                  -- 낮을수록 우선
    max_results INT,                          -- NULL = 무제한
    year_from INT,
    year_to INT,
    open_access_only BOOLEAN DEFAULT TRUE,

    -- 성능 설정
    max_concurrent INT DEFAULT 35,            -- 동시 API 요청 수
    auto_backfill BOOLEAN DEFAULT FALSE,      -- 생성 시 자동 백필 실행

    -- 통계
    total_collected INT DEFAULT 0,
    last_backfill_at TIMESTAMPTZ,
    last_incremental_at TIMESTAMPTZ,

    -- 타임스탬프
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    created_by VARCHAR(100),
    updated_by VARCHAR(100)
);

CREATE INDEX idx_search_queries_active ON search_queries(is_active, priority);

-- ============================================================
-- 5. collection_jobs (배치 작업 큐)
-- ============================================================
CREATE TABLE collection_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- 작업 정보
    job_type VARCHAR(20) NOT NULL,            -- backfill, incremental, repair
    query_id UUID REFERENCES search_queries(id),
    priority INT DEFAULT 10,
    query TEXT NOT NULL,
    params JSONB,
    api_name VARCHAR(50) DEFAULT 'europe_pmc',

    -- 상태 관리
    status VARCHAR(20) DEFAULT 'pending',     -- pending, running, completed, failed, delayed, cancelled
    checkpoint JSONB,                         -- 중단 재개용

    -- 진행률
    total_count INT,
    processed_count INT DEFAULT 0,
    success_count INT DEFAULT 0,
    failed_count INT DEFAULT 0,

    -- 재시도 관리
    attempt_count INT DEFAULT 0,
    max_attempts INT DEFAULT 5,
    next_run_at TIMESTAMPTZ,                  -- delayed 상태일 때

    -- 워커 락
    locked_at TIMESTAMPTZ,
    locked_by VARCHAR(100),

    -- 에러 추적
    last_error_code VARCHAR(20),
    last_error_message TEXT,
    last_error_at TIMESTAMPTZ,

    -- 타임스탬프
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    duration_ms INT
);

-- 인덱스
-- NOTE: NOW()는 IMMUTABLE이 아니므로 partial index에서 사용 불가
-- 쿼리에서 WHERE 조건으로 처리
CREATE INDEX idx_jobs_pending ON collection_jobs (priority, created_at)
    WHERE status IN ('pending', 'delayed');
CREATE INDEX idx_jobs_delayed ON collection_jobs (next_run_at)
    WHERE status = 'delayed';
CREATE INDEX idx_jobs_stale_lock ON collection_jobs (locked_at)
    WHERE status = 'running';
CREATE INDEX idx_jobs_type ON collection_jobs (job_type, status);
CREATE INDEX idx_jobs_query ON collection_jobs (query_id, created_at);

-- ============================================================
-- 6. article_jobs (개별 논문 상태 관리) - OAR-21 체크포인트 설계
-- ============================================================
CREATE TABLE article_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    batch_job_id UUID REFERENCES collection_jobs(id) ON DELETE CASCADE,

    -- 논문 식별
    pmcid VARCHAR(20) NOT NULL,
    pmid VARCHAR(20),
    doi VARCHAR(100),

    -- 상태
    status VARCHAR(20) DEFAULT 'pending',
    -- pending → downloading → parsing → saving → completed / failed

    -- 재시도
    attempt_count INT DEFAULT 0,
    max_attempts INT DEFAULT 3,
    next_run_at TIMESTAMPTZ,

    -- 에러
    last_error_code VARCHAR(20),
    last_error TEXT,

    -- 타임스탬프
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE(batch_job_id, pmcid)
);

CREATE INDEX idx_article_jobs_status ON article_jobs (batch_job_id, status);
CREATE INDEX idx_article_jobs_retry ON article_jobs (status, next_run_at)
    WHERE status IN ('pending', 'failed');

-- ============================================================
-- 7. article_errors (아티클 에러 로그)
-- ============================================================
CREATE TABLE article_errors (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id UUID REFERENCES collection_jobs(id) ON DELETE CASCADE,

    -- 논문 식별
    pmcid VARCHAR(20),
    pmid VARCHAR(20),
    doi VARCHAR(100),

    -- 에러 정보
    stage VARCHAR(30) NOT NULL,               -- search, download, parse, save
    error_code VARCHAR(50),                   -- HTTP_429, PARSE_XML, DB_INSERT, etc.
    error_message TEXT NOT NULL,
    error_detail TEXT,                        -- stacktrace 또는 상세 정보

    -- 컨텍스트
    raw_response TEXT,                        -- 디버깅용 원본 응답
    context JSONB,                            -- 추가 컨텍스트 정보

    -- 타임스탬프
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_article_errors_job ON article_errors (job_id, created_at DESC);
CREATE INDEX idx_article_errors_pmcid ON article_errors (pmcid);
CREATE INDEX idx_article_errors_stage ON article_errors (stage);
CREATE INDEX idx_article_errors_code ON article_errors (error_code);

-- ============================================================
-- 8. batch_job_logs (배치 실행 로그)
-- ============================================================
CREATE TABLE batch_job_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id UUID REFERENCES collection_jobs(id) ON DELETE CASCADE,

    -- 로그 정보
    level VARCHAR(10) NOT NULL,               -- info, warn, error
    message TEXT NOT NULL,
    details JSONB,

    -- 타임스탬프
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_job_logs_job ON batch_job_logs (job_id, created_at);
CREATE INDEX idx_job_logs_level ON batch_job_logs (level, created_at);

-- ============================================================
-- 9. batch_failed_items (실패 항목 추적)
-- ============================================================
CREATE TABLE batch_failed_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id UUID REFERENCES collection_jobs(id),

    -- 실패 항목 정보
    item_type VARCHAR(20) NOT NULL,           -- paper, query_page
    item_id VARCHAR(100),                     -- pmcid, doi 등

    -- 에러 정보
    error_code VARCHAR(20),                   -- 429, 500, TIMEOUT, PARSE_ERROR
    error_message TEXT,

    -- 재시도
    retry_count INT DEFAULT 0,
    max_retries INT DEFAULT 3,
    next_retry_at TIMESTAMPTZ,

    -- 상태
    status VARCHAR(20) DEFAULT 'pending',     -- pending, retrying, resolved, abandoned
    resolved_at TIMESTAMPTZ,

    -- 타임스탬프
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_failed_items_status ON batch_failed_items (status, next_retry_at);
CREATE INDEX idx_failed_items_job ON batch_failed_items (job_id);

-- ============================================================
-- 10. watermarks (증분 수집 상태)
-- ============================================================
CREATE TABLE watermarks (
    id VARCHAR(100) PRIMARY KEY,              -- 'incremental:europe_pmc:query_id'

    -- 상태
    last_completed_at TIMESTAMPTZ NOT NULL,
    overlap_days INT DEFAULT 2,               -- 안전 윈도우

    -- 메타데이터
    last_query TEXT,
    last_result_count INT,

    -- 타임스탬프
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- 기본 데이터: 검색 쿼리 예시
-- ============================================================
INSERT INTO search_queries (name, query, description, priority) VALUES
    ('폐암 면역치료', 'lung cancer immunotherapy', '폐암 면역치료 관련 논문', 1),
    ('유방암 BRCA', 'breast cancer BRCA mutation', 'BRCA 변이 유방암 논문', 2),
    ('대장암 표적치료', 'colorectal cancer targeted therapy', '대장암 표적치료 논문', 3);

-- ============================================================
-- 완료 메시지
-- ============================================================
DO $$
BEGIN
    RAISE NOTICE '========================================';
    RAISE NOTICE '암 논문 수집 서비스 스키마 초기화 완료!';
    RAISE NOTICE '========================================';
    RAISE NOTICE '테이블:';
    RAISE NOTICE '  - papers, paper_authors, paper_sections';
    RAISE NOTICE '  - search_queries';
    RAISE NOTICE '  - collection_jobs, article_jobs, article_errors';
    RAISE NOTICE '  - batch_job_logs, batch_failed_items';
    RAISE NOTICE '  - watermarks';
    RAISE NOTICE '========================================';
END $$;
