# OAR-20: PostgreSQL Paper Schema Design

> **Owner**: hk (Hyemin Kim)
>
> **Sub-task**: OAR-73
>
> **Purpose**: Design PostgreSQL schema for cancer research paper metadata (ADR compliant)

---

## Background

OAR-20 requires designing a PostgreSQL schema for storing paper metadata collected from OpenAlex API. This spike implements the schema following the ADR decisions in `CLAUDE.md`.

Related:
- [OAR-73 Jira](https://hyemink.atlassian.net/browse/OAR-73)
- [F-02 & F-03 Specification](./docs/OARIA_F02_F03_Specification.md)

---

## Goal

Answer these questions:
1. What tables are needed for paper metadata?
2. How to integrate with Qdrant (vector DB)?
3. What indexes are needed for efficient querying?

---

## Folder Structure

```
OAR-20/hk/
├── README.md                               # This file
├── docs/
│   ├── postgresql-schema-design.md         # Detailed schema design
│   └── OARIA_F02_F03_Specification.md      # F-02/F-03 spec reference
├── src/
│   ├── models.py                           # Pydantic models
│   └── migrations/
│       └── 001_create_papers.sql           # SQL migration
└── output/                                 # (empty for now)
```

---

## Key Decisions

| Decision | Choice | Reasoning |
|----------|--------|-----------|
| Primary Key | `openalex_id` | ADR-001: OpenAlex as paper source |
| Vector Storage | Qdrant (not PostgreSQL) | ADR-002: Qdrant for vectors |
| Embeddings | `is_embedded` flag only | Track indexing status |
| Classification | JSONB columns | Flexible, GIN indexable |
| Authors | Normalized table | Query by author, preserve order |

---

## Schema Summary

### papers table

| Column | Type | Purpose |
|--------|------|---------|
| `openalex_id` | VARCHAR(20) PK | OpenAlex Work ID (W...) |
| `title` | TEXT | Paper title |
| `abstract` | TEXT | For RAG (min 50 chars) |
| `doi`, `pmid` | VARCHAR | External IDs |
| `concepts` | JSONB | OpenAlex concepts |
| `is_embedded` | BOOLEAN | Qdrant indexed? |

### paper_authors table

| Column | Type | Purpose |
|--------|------|---------|
| `openalex_id` | FK | Reference to papers |
| `author_position` | SMALLINT | 1=first author, 2=second... |
| `author_name` | VARCHAR | Author display name |
| `orcid` | VARCHAR | ORCID ID |

---

## How to Run

### Apply Migration

```bash
# Connect to PostgreSQL
psql -h localhost -U postgres -d oaria

# Run migration
\i src/migrations/001_create_papers.sql
```

### Verify

```sql
-- Check tables created
\dt

-- Check indexes
\di
```

---

## Findings

1. **OpenAlex ID format**: `W` prefix + numeric ID (e.g., `W2741809807`)
2. **Abstract handling**: OpenAlex uses inverted index format - needs reconstruction
3. **JSONB for concepts**: Enables flexible filtering with GIN indexes
4. **Partial index**: `idx_papers_not_embedded` optimizes F-03 indexer queries

---

## Decision

**Status**: In Progress

### Next Steps
- [ ] Test with sample OpenAlex data
- [ ] Implement SQLAlchemy models
- [ ] Create repository layer (async)
- [ ] Integration test with Qdrant

---

## References

- [OpenAlex API](https://docs.openalex.org/)
- [CLAUDE.md ADRs](../../../CLAUDE.md)
- [F-02 & F-03 Spec](./docs/OARIA_F02_F03_Specification.md)
