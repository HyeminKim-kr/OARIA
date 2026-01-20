# PostgreSQL Paper Schema Design

> **OAR-73**: PostgreSQL Paper Schema Design and Implementation
>
> **Owner**: hk (Hyemin Kim)
>
> **Version**: v1.0 (2025-12-23)

---

## ADR Compliance

This schema follows the ADR decisions from `CLAUDE.md`:

| ADR | Decision | Implementation |
|-----|----------|----------------|
| ADR-001 | OpenAlex as paper source | `openalex_id` as Primary Key |
| ADR-002 | Qdrant for Vector DB | No embeddings in PostgreSQL (stored in Qdrant) |
| ADR-003 | BGE-M3 embeddings | `is_embedded` flag tracks Qdrant indexing status |
| ADR-007 | Async-first | SQLAlchemy 2.0 async support |

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                    OARIA RAG System                              │
└─────────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
        ▼                     ▼                     ▼
┌─────────────┐       ┌─────────────┐       ┌─────────────┐
│   Qdrant    │       │ PostgreSQL  │       │  OpenAlex   │
│ (Vector DB) │       │   (RDB)     │       │    API      │
├─────────────┤       ├─────────────┤       ├─────────────┤
│ paper_chunks│       │ papers      │       │ Paper source│
│ - dense vec │       │ paper_      │       │ 250M+ papers│
│ - sparse vec│       │   authors   │       │             │
│ - metadata  │       │             │       │             │
└─────────────┘       └─────────────┘       └─────────────┘
   Vector Search        Metadata              Data Source
```

---

## Table Design

### 1. papers (Paper Metadata)

```sql
CREATE TABLE papers (
    -- === Primary Key (OpenAlex ID) ===
    openalex_id VARCHAR(20) PRIMARY KEY,  -- Format: "W2741809807"

    -- === Core Metadata ===
    title TEXT NOT NULL,
    abstract TEXT,  -- Critical for RAG (minimum 50 chars recommended)

    -- === External Identifiers ===
    doi VARCHAR(100),
    pmid VARCHAR(20),

    -- === Publication Info ===
    publication_date DATE,
    journal VARCHAR(500),
    publisher VARCHAR(500),
    volume VARCHAR(50),
    issue VARCHAR(50),

    -- === Classification (JSONB) ===
    concepts JSONB DEFAULT '[]',
    topics JSONB DEFAULT '[]',
    keywords JSONB DEFAULT '[]',
    mesh_terms JSONB DEFAULT '[]',

    -- === Accessibility ===
    is_open_access BOOLEAN DEFAULT FALSE,
    open_access_url TEXT,
    landing_page_url TEXT,

    -- === Impact Metrics ===
    cited_by_count INTEGER DEFAULT 0,

    -- === Processing Status ===
    collected_at TIMESTAMPTZ DEFAULT NOW(),
    is_embedded BOOLEAN DEFAULT FALSE,
    embedding_error TEXT,

    -- === Constraints ===
    CONSTRAINT abstract_min_length
        CHECK (abstract IS NULL OR LENGTH(abstract) >= 50)
);

COMMENT ON TABLE papers IS 'Cancer research paper metadata from OpenAlex';
COMMENT ON COLUMN papers.openalex_id IS 'OpenAlex Work ID (e.g., W2741809807)';
COMMENT ON COLUMN papers.is_embedded IS 'Whether indexed in Qdrant';
```

### 2. paper_authors (Normalized Authors)

```sql
CREATE TABLE paper_authors (
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
```

---

## Index Design

```sql
-- External IDs (unique if present)
CREATE UNIQUE INDEX idx_papers_doi ON papers(doi) WHERE doi IS NOT NULL;
CREATE UNIQUE INDEX idx_papers_pmid ON papers(pmid) WHERE pmid IS NOT NULL;

-- Date filtering
CREATE INDEX idx_papers_pub_date ON papers(publication_date DESC);

-- Unembedded papers (partial index)
CREATE INDEX idx_papers_not_embedded ON papers(openalex_id)
    WHERE is_embedded = FALSE AND abstract IS NOT NULL;

-- JSONB concepts search
CREATE INDEX idx_papers_concepts ON papers USING GIN(concepts);

-- Journal and citation filtering
CREATE INDEX idx_papers_journal ON papers(journal);
CREATE INDEX idx_papers_cited_by ON papers(cited_by_count DESC);

-- Author lookup
CREATE INDEX idx_authors_openalex ON paper_authors(openalex_id);
CREATE INDEX idx_authors_name ON paper_authors(author_name);
```

---

## Data Flow

### Paper Collection (F-02)

```
OpenAlex API → Parse Response → PostgreSQL (is_embedded=FALSE)
```

### Vector Indexing (F-03)

```
PostgreSQL (unembedded) → Chunk → BGE-M3 → Qdrant → PostgreSQL (is_embedded=TRUE)
```

---

## Query Examples

### Get Unembedded Papers

```sql
SELECT openalex_id, title, abstract
FROM papers
WHERE is_embedded = FALSE
  AND abstract IS NOT NULL
ORDER BY collected_at
LIMIT 100;
```

### Get Paper with Authors

```sql
SELECT p.*, ARRAY_AGG(pa.author_name ORDER BY pa.author_position) AS authors
FROM papers p
LEFT JOIN paper_authors pa ON p.openalex_id = pa.openalex_id
WHERE p.openalex_id = 'W2741809807'
GROUP BY p.openalex_id;
```

### Filter by Concept

```sql
SELECT openalex_id, title, cited_by_count
FROM papers
WHERE concepts @> '[{"id": "C126322002"}]'
ORDER BY cited_by_count DESC
LIMIT 20;
```

---

## References

- [OpenAlex API](https://docs.openalex.org/)
- [F-02/F-03 Spec](./OARIA_F02_F03_Specification.md)
- [CLAUDE.md ADRs](../../../../CLAUDE.md)
