-- Migration: 001_create_papers
-- Description: Create papers and paper_authors tables for OARIA
-- Author: hk (Hyemin Kim)
-- Date: 2025-12-23
--
-- ADR Compliance:
--   ADR-001: OpenAlex as paper source (openalex_id as PK)
--   ADR-002: Qdrant for vectors (is_embedded flag only)

-- ============================================================
-- UP MIGRATION
-- ============================================================

BEGIN;

-- -----------------------------
-- 1. papers table
-- -----------------------------
CREATE TABLE IF NOT EXISTS papers (
    -- Primary Key (OpenAlex Work ID)
    openalex_id VARCHAR(20) PRIMARY KEY,

    -- Core Metadata
    title TEXT NOT NULL,
    abstract TEXT,

    -- External Identifiers
    doi VARCHAR(100),
    pmid VARCHAR(20),

    -- Publication Info
    publication_date DATE,
    journal VARCHAR(500),
    publisher VARCHAR(500),
    volume VARCHAR(50),
    issue VARCHAR(50),

    -- Classification (JSONB)
    concepts JSONB DEFAULT '[]',
    topics JSONB DEFAULT '[]',
    keywords JSONB DEFAULT '[]',
    mesh_terms JSONB DEFAULT '[]',

    -- Accessibility
    is_open_access BOOLEAN DEFAULT FALSE,
    open_access_url TEXT,
    landing_page_url TEXT,

    -- Impact Metrics
    cited_by_count INTEGER DEFAULT 0,

    -- Processing Status
    collected_at TIMESTAMPTZ DEFAULT NOW(),
    is_embedded BOOLEAN DEFAULT FALSE,
    embedding_error TEXT,

    -- Constraints
    CONSTRAINT abstract_min_length
        CHECK (abstract IS NULL OR LENGTH(abstract) >= 50)
);

-- Table comments
COMMENT ON TABLE papers IS 'Cancer research paper metadata from OpenAlex';
COMMENT ON COLUMN papers.openalex_id IS 'OpenAlex Work ID (e.g., W2741809807)';
COMMENT ON COLUMN papers.abstract IS 'Paper abstract - critical for RAG';
COMMENT ON COLUMN papers.concepts IS 'OpenAlex concepts: [{"id": "C...", "name": "...", "score": 0.9}]';
COMMENT ON COLUMN papers.is_embedded IS 'Whether paper has been indexed in Qdrant';

-- -----------------------------
-- 2. paper_authors table
-- -----------------------------
CREATE TABLE IF NOT EXISTS paper_authors (
    id SERIAL PRIMARY KEY,
    openalex_id VARCHAR(20) NOT NULL
        REFERENCES papers(openalex_id) ON DELETE CASCADE,

    author_position SMALLINT NOT NULL,
    author_name VARCHAR(500) NOT NULL,
    orcid VARCHAR(50),
    institution VARCHAR(500),
    country VARCHAR(10),

    UNIQUE (openalex_id, author_position)
);

COMMENT ON TABLE paper_authors IS 'Paper authors with position order';

-- -----------------------------
-- 3. Indexes
-- -----------------------------

-- External IDs (unique if present)
CREATE UNIQUE INDEX IF NOT EXISTS idx_papers_doi
    ON papers(doi) WHERE doi IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS idx_papers_pmid
    ON papers(pmid) WHERE pmid IS NOT NULL;

-- Date filtering
CREATE INDEX IF NOT EXISTS idx_papers_pub_date
    ON papers(publication_date DESC);

-- Unembedded papers (partial index for F-03 indexer)
CREATE INDEX IF NOT EXISTS idx_papers_not_embedded
    ON papers(openalex_id)
    WHERE is_embedded = FALSE AND abstract IS NOT NULL;

-- JSONB concepts search
CREATE INDEX IF NOT EXISTS idx_papers_concepts
    ON papers USING GIN(concepts);

-- Journal and citation filtering
CREATE INDEX IF NOT EXISTS idx_papers_journal
    ON papers(journal);
CREATE INDEX IF NOT EXISTS idx_papers_cited_by
    ON papers(cited_by_count DESC);

-- Author lookup
CREATE INDEX IF NOT EXISTS idx_authors_openalex
    ON paper_authors(openalex_id);
CREATE INDEX IF NOT EXISTS idx_authors_name
    ON paper_authors(author_name);

COMMIT;

-- ============================================================
-- DOWN MIGRATION (for rollback)
-- ============================================================
-- Run this section manually if rollback is needed:
--
-- BEGIN;
-- DROP TABLE IF EXISTS paper_authors;
-- DROP TABLE IF EXISTS papers;
-- COMMIT;
