# OpenAlex API Integration Design

> **Task**: OAR-94 (sub-task of OAR-18)
>
> **Owner**: Hyemin Kim (AI Lead)
>
> **Version**: v1.0 (2025-12-24)

---

## ADR Compliance

This implementation follows ADR-001 from `CLAUDE.md`:

| ADR | Decision | Implementation |
|-----|----------|----------------|
| ADR-001 | OpenAlex over PubMed | `OpenAlexClient` class with OpenAlex API |
| ADR-007 | Async-first | `httpx.AsyncClient`, `async/await` pattern |

---

## Why OpenAlex Instead of PubMed?

### Comparison

| Factor | PubMed | OpenAlex | Winner |
|--------|--------|----------|--------|
| Paper Coverage | 35M (biomedical only) | 250M+ (all academic) | OpenAlex |
| Oncology Papers | Native | Includes ALL PubMed papers | Tie |
| API Key | Recommended for higher limits | Not required | OpenAlex |
| Rate Limit | 3 req/sec (10 with key) | 10 req/sec (polite pool) | OpenAlex |
| Pagination | Offset-based | Cursor-based | OpenAlex |
| Metadata | Basic | Rich (citations, concepts) | OpenAlex |

### Why This Matters for OARIA

1. **OpenAlex includes ALL PubMed papers** - No loss of biomedical coverage
2. **Better API design** - Cursor pagination avoids duplicates and offset limits
3. **Richer metadata** - Concepts, citation counts enable better filtering
4. **No API key hassle** - Just add email for polite pool
5. **Future flexibility** - Works for any domain, not locked to biomedical

### Trade-off: Abstract Format

OpenAlex stores abstracts as "inverted index" for compression:

```python
# PubMed format (plain text):
"EGFR mutations are common in lung cancer"

# OpenAlex format (inverted index):
{"EGFR": [0], "mutations": [1], "are": [2], "common": [3], "in": [4], "lung": [5], "cancer": [6]}
```

**Solution**: `_extract_abstract()` method reconstructs plain text.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     OpenAlexClient                               │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────────┐    ┌─────────────────┐                    │
│  │ __init__        │    │ __aenter__      │                    │
│  │ - store email   │    │ - open HTTP     │                    │
│  │ - init client   │    │   connection    │                    │
│  └─────────────────┘    └─────────────────┘                    │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ search_papers(config) → AsyncGenerator[list[Paper]]     │   │
│  │                                                         │   │
│  │  1. _build_filter_string(config)                        │   │
│  │  2. Loop with cursor pagination:                        │   │
│  │     - GET /works?filter=...&cursor=...                  │   │
│  │     - _parse_paper() for each result                    │   │
│  │     - yield batch of Papers                             │   │
│  │     - rate limit sleep                                  │   │
│  │  3. Log completion stats                                │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  ┌─────────────────┐    ┌─────────────────┐                    │
│  │ _parse_paper()  │    │ _extract_       │                    │
│  │ - validate      │    │  abstract()     │                    │
│  │ - extract fields│    │ - reconstruct   │                    │
│  │ - build Paper   │    │   from inverted │                    │
│  └─────────────────┘    └─────────────────┘                    │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## OpenAlex API Details

### Base URL

```
https://api.openalex.org
```

### Endpoints Used

| Endpoint | Purpose |
|----------|---------|
| `GET /works` | Search papers with filters |

### Filter Syntax

```
# Multiple values for same field (OR): pipe |
concepts.id:C126322002|C502942594

# Multiple fields (AND): comma ,
concepts.id:C126322002,has_abstract:true,publication_year:>2023

# Full example
GET /works?filter=concepts.id:C126322002|C502942594,has_abstract:true,type:journal-article|review&per-page=200&cursor=*
```

### Oncology Concept IDs

| Concept | ID | Description |
|---------|-----|-------------|
| Oncology | C126322002 | Primary oncology concept |
| Cancer | C502942594 | General cancer term |
| Cancer research | C17744445 | Research-focused papers |
| Chemotherapy | C89423630 | Treatment modality |
| Immunotherapy | C2777844474 | Treatment modality |

### Cursor Pagination

```
Request 1: cursor=*           → Response: next_cursor="abc123"
Request 2: cursor=abc123      → Response: next_cursor="def456"
Request 3: cursor=def456      → Response: next_cursor=null (done!)
```

**Why cursor > offset?**
- Offset: New papers can cause duplicates or skips
- Cursor: Stable position, consistent traversal

### Rate Limiting

| Pool | Rate | How to Access |
|------|------|---------------|
| Default | 1 req/sec | No email |
| Polite | 10 req/sec | Add `mailto` param |

```python
params["mailto"] = "your-email@example.com"
```

---

## Implementation Details

### File Structure

```
spikes/OAR-18/hk/src/
├── models.py              # Pydantic models (from OAR-20)
└── openalex_client.py     # API client (this implementation)
```

### Key Methods

#### 1. `_build_filter_string(config)`

Converts `CrawlerConfig` to OpenAlex filter syntax:

```python
# Input
CrawlerConfig(
    concept_ids=["C126322002", "C502942594"],
    from_date=date(2024, 1, 1),
)

# Output
"concepts.id:C126322002|C502942594,publication_year:>2023,has_abstract:true,type:journal-article|review"
```

#### 2. `_extract_abstract(raw)`

Reconstructs abstract from inverted index:

```python
# Input
{"EGFR": [0], "mutations": [1], "are": [2]}

# Process
[(0, "EGFR"), (1, "mutations"), (2, "are")]  # build pairs
[(0, "EGFR"), (1, "mutations"), (2, "are")]  # sort by position

# Output
"EGFR mutations are"
```

#### 3. `_parse_paper(raw)`

Converts API JSON to `Paper` model:

1. Validate abstract (skip if < 50 chars)
2. Extract OpenAlex ID from URL
3. Parse authors with institutions
4. Parse concepts (filter score > 0.3)
5. Extract publication info
6. Build `Paper` object

#### 4. `search_papers(config)`

Main search with pagination:

```python
async with OpenAlexClient(email="...") as client:
    async for batch in client.search_papers(config):
        for paper in batch:
            # process paper
```

---

## Test Results

```
Papers fetched from API: 10
Papers successfully parsed: 4
Papers skipped (no/short abstract): 6
Time: ~3 seconds
```

Sample papers retrieved with 500-1800+ citations.

---

## References

- [OpenAlex API Docs](https://docs.openalex.org/)
- [OpenAlex Works Entity](https://docs.openalex.org/api-entities/works)
- [OpenAlex Concepts](https://docs.openalex.org/api-entities/concepts)
- [ADR-001 in CLAUDE.md](../../../../claude.md)
