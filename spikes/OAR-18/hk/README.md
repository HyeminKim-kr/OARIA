# OAR-18: OpenAlex API Integration

> **Owner**: hk (Hyemin Kim)
>
> **Sub-task**: OAR-94
>
> **Purpose**: Implement OpenAlex API client for cancer research paper collection (F-02)

---

## Why OpenAlex Instead of PubMed? (ADR-001)

OAR-18 originally specified PubMed API. After analysis, we chose **OpenAlex** instead.

### The Decision

| Factor | PubMed | OpenAlex | Winner |
|--------|--------|----------|--------|
| Paper Coverage | 35M (biomedical only) | 250M+ (all academic) | OpenAlex |
| Oncology Papers | Native | Includes ALL PubMed papers | Tie |
| API Key | Recommended for higher limits | Not required | OpenAlex |
| Rate Limit | 3 req/sec (10 with key) | 10 req/sec (polite pool) | OpenAlex |
| Pagination | Offset-based | Cursor-based | OpenAlex |
| Metadata Richness | Basic | Citations, concepts, institutions | OpenAlex |

### Why This Matters for OARIA

1. **OpenAlex includes ALL PubMed papers** - We don't lose any biomedical coverage
2. **Better API design** - Cursor pagination is more efficient for bulk collection (no duplicates, no offset limits)
3. **Richer metadata** - Concepts, citation counts, institutional data enable better filtering
4. **No API key hassle** - Just add email for polite pool (10 req/sec)
5. **Future flexibility** - If OARIA expands beyond oncology, the architecture is ready

### Trade-off: Abstract Format

OpenAlex stores abstracts as "inverted index" (word → positions mapping), not plain text.

```python
# PubMed: "EGFR mutations are common in lung cancer"
# OpenAlex: {"EGFR": [0], "mutations": [1], "are": [2], "common": [3], ...}
```

**Solution**: Implement `_extract_abstract()` to reconstruct plain text. One-time implementation cost, no ongoing impact.

---

## Goal

Implement async OpenAlex API client that:
1. Searches cancer research papers by concept IDs
2. Handles cursor-based pagination efficiently
3. Parses paper metadata (including inverted index abstracts)
4. Respects rate limits (polite pool with email)

---

## Folder Structure

```
OAR-18/hk/
├── README.md                    # This file
├── docs/
│   └── openalex-api-notes.md    # API research notes (if needed)
├── src/
│   └── openalex_client.py       # API client implementation
└── output/                      # Test outputs
```

---

## Key Implementation Points

### OpenAlex Concepts for Oncology

| Concept | ID | Why Included |
|---------|-----|--------------|
| Oncology | C126322002 | Primary oncology concept |
| Cancer | C502942594 | General cancer term |
| Cancer research | C17744445 | Research-focused papers |
| Tumor | C54355233 | Related pathology |
| Chemotherapy | C89423630 | Major treatment modality |
| Immunotherapy | C2777844474 | Emerging treatment modality |

### API Filter Syntax

```
# OR within same field (pipe)
concepts.id:C126322002|C502942594

# AND between different fields (comma)
concepts.id:C126322002,publication_year:>2019,has_abstract:true

# Full example
GET /works?filter=concepts.id:C126322002|C502942594,publication_year:>2019,has_abstract:true&per-page=200&cursor=*
```

### Abstract Reconstruction

```python
def _extract_abstract(self, raw: dict) -> str | None:
    """Reconstruct abstract from OpenAlex inverted index format."""
    inverted = raw.get("abstract_inverted_index")
    if not inverted:
        return None

    words = []
    for word, positions in inverted.items():
        for pos in positions:
            words.append((pos, word))

    words.sort(key=lambda x: x[0])
    return " ".join(word for _, word in words)
```

---

## Progress

- [ ] Implement OpenAlexClient class
- [ ] Add cursor-based pagination
- [ ] Implement abstract reconstruction
- [ ] Add rate limiting (polite pool)
- [ ] Test with sample queries
- [ ] Integration with PostgreSQL (OAR-73 schema)

---

## References

- [OpenAlex API Docs](https://docs.openalex.org/)
- [OpenAlex Works Entity](https://docs.openalex.org/api-entities/works)
- [F-02 Specification](../OAR-20/hk/docs/OARIA_F02_F03_Specification.md)
- [ADR-001 in CLAUDE.md](../../../claude.md)
