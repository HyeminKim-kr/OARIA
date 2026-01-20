-- OARIA Paper Crawler Schema (OAR-73)
-- Automatically runs when PostgreSQL container starts

CREATE TABLE IF NOT EXISTS papers (
    openalex_id VARCHAR(50) PRIMARY KEY,
    title TEXT NOT NULL,
    abstract TEXT,
    doi VARCHAR(200),
    pmid VARCHAR(50),
    publication_date DATE,
    journal VARCHAR(500),
    publisher VARCHAR(500),
    is_open_access BOOLEAN DEFAULT FALSE,
    open_access_url TEXT,
    cited_by_count INTEGER DEFAULT 0,
    collected_at TIMESTAMP DEFAULT NOW(),
    is_embedded BOOLEAN DEFAULT FALSE
);

-- Index for DOI deduplication
CREATE INDEX IF NOT EXISTS idx_papers_doi ON papers(doi) WHERE doi IS NOT NULL;

-- Index for date-based queries
CREATE INDEX IF NOT EXISTS idx_papers_date ON papers(publication_date);

-- Log table to track crawl progress
CREATE TABLE IF NOT EXISTS crawl_log (
    id SERIAL PRIMARY KEY,
    started_at TIMESTAMP DEFAULT NOW(),
    ended_at TIMESTAMP,
    papers_fetched INTEGER DEFAULT 0,
    papers_saved INTEGER DEFAULT 0,
    papers_skipped INTEGER DEFAULT 0,
    status VARCHAR(20) DEFAULT 'running'
);

SELECT 'Schema initialized successfully!' AS message;
