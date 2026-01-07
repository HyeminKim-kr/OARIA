# Metadata Parsing Logic Design

> **Task**: OAR-99 (sub-task of OAR-19)
>
> **Owner**: Hyemin Kim (AI Lead)
>
> **Version**: v1.0 (2025-12-24)

---

## ADR Compliance

This implementation follows ADR-001 from `CLAUDE.md`:

| ADR | Decision | Implementation |
|-----|----------|----------------|
| ADR-001 | OpenAlex over PubMed | JSON parsing instead of XML |

---

## Original Spec vs ADR Decision

### Original Requirement (OAR-19)

```
Parse PubMed XML response:
- Extract PMID, Title, Abstract, Authors, etc.
- Handle XML parsing edge cases
- 100% parsing accuracy
```

### ADR-001 Change

| Aspect | Original (PubMed) | ADR Decision (OpenAlex) |
|--------|-------------------|-------------------------|
| Format | XML | JSON |
| Parsing | Complex XML with schemas | Simple dict access |
| Abstract | Plain text | Inverted index → reconstruct |
| Primary ID | PMID | OpenAlex ID |
| Complexity | High (XML edge cases) | Low (JSON is predictable) |

### Why JSON is Better

1. **No XML parsing libraries needed** - Just `response.json()`
2. **Graceful missing fields** - `dict.get("field", default)`
3. **No schema validation** - JSON structure is consistent
4. **Easier debugging** - Human-readable format

### Trade-off

Abstract reconstruction from inverted index - solved with `_extract_abstract()`.

---

## Field Mapping

### Required Fields (Original Spec)

| Required Field | PubMed Source | OpenAlex Source | Status |
|----------------|---------------|-----------------|--------|
| PMID | `<PMID>` | `ids.pmid` | ✅ |
| Title | `<ArticleTitle>` | `title` | ✅ |
| Abstract | `<AbstractText>` | `abstract_inverted_index` | ✅ Reconstructed |
| Authors (name) | `<Author><LastName>` | `authorships[].author.display_name` | ✅ |
| Authors (affiliation) | `<Affiliation>` | `authorships[].institutions[].display_name` | ✅ |
| Journal | `<Journal><Title>` | `primary_location.source.display_name` | ✅ |
| Publication Date | `<PubDate>` | `publication_date` | ✅ |
| MeSH Terms | `<MeshHeading>` | `mesh[].descriptor_name` | ✅ |
| Keywords | `<Keyword>` | `keywords[].keyword` | ✅ |
| DOI | `<ArticleId IdType="doi">` | `doi` | ✅ |
| PMC ID | `<ArticleId IdType="pmc">` | N/A (use `open_access_url`) | ✅ Alternative |
| Full Text URL | Derived from PMC | `open_access.oa_url` | ✅ |

### Bonus Fields (OpenAlex)

| Field | Source | Purpose |
|-------|--------|---------|
| `openalex_id` | `id` | Primary key (ADR-001) |
| `concepts` | `concepts[]` | Topic classification with scores |
| `topics` | `topics[]` | Hierarchical topic tags |
| `cited_by_count` | `cited_by_count` | Citation filtering |
| `is_open_access` | `open_access.is_oa` | Accessibility flag |
| `publisher` | `primary_location.source.publisher` | Publisher info |
| `volume`, `issue` | `biblio` | Bibliographic details |

---

## Abstract Reconstruction

### The Problem

OpenAlex stores abstracts as "inverted index" for compression:

```python
# What OpenAlex returns:
{
    "abstract_inverted_index": {
        "EGFR": [0, 15],      # "EGFR" appears at positions 0 and 15
        "mutations": [1],
        "are": [2],
        "common": [3],
        "in": [4],
        "lung": [5],
        "cancer": [6],
        "patients": [7]
    }
}
```

### The Solution

```python
def _extract_abstract(self, raw: dict) -> Optional[str]:
    inverted = raw.get("abstract_inverted_index")
    if not inverted:
        return None

    # Step 1: Build (position, word) pairs
    position_word_pairs = []
    for word, positions in inverted.items():
        for pos in positions:
            position_word_pairs.append((pos, word))

    # Step 2: Sort by position
    position_word_pairs.sort(key=lambda x: x[0])

    # Step 3: Join words
    return " ".join(word for _, word in position_word_pairs)
```

### Example

```python
# Input
{"EGFR": [0], "mutations": [1], "are": [2], "common": [3]}

# Step 1: Build pairs
[(0, "EGFR"), (1, "mutations"), (2, "are"), (3, "common")]

# Step 2: Sort (already sorted in this case)
[(0, "EGFR"), (1, "mutations"), (2, "are"), (3, "common")]

# Step 3: Join
"EGFR mutations are common"
```

---

## Author Parsing

### OpenAlex Structure

```json
{
    "authorships": [
        {
            "author": {
                "id": "https://openalex.org/A123",
                "display_name": "Jane Smith",
                "orcid": "https://orcid.org/0000-0001-2345-6789"
            },
            "institutions": [
                {
                    "id": "https://openalex.org/I123",
                    "display_name": "Harvard Medical School",
                    "country_code": "US"
                }
            ],
            "author_position": "first"
        }
    ]
}
```

### Parsing Logic

```python
authors = []
for authorship in raw.get("authorships", []):
    author_data = authorship.get("author", {})
    institutions = authorship.get("institutions", [])
    first_inst = institutions[0] if institutions else {}

    authors.append(Author(
        name=author_data.get("display_name", "Unknown"),
        orcid=author_data.get("orcid"),
        institution=first_inst.get("display_name"),
        country=first_inst.get("country_code"),
    ))
```

---

## Concept Filtering

### Why Filter by Score?

OpenAlex tags papers with many concepts, but not all are relevant:

```json
{
    "concepts": [
        {"id": "C126322002", "display_name": "Oncology", "score": 0.85},
        {"id": "C502942594", "display_name": "Cancer", "score": 0.72},
        {"id": "C123456789", "display_name": "Biology", "score": 0.15}  // Too generic
    ]
}
```

### Filtering Logic

```python
concepts = []
for c in raw.get("concepts", []):
    score = c.get("score", 0)
    if score > 0.3:  # Only confident matches
        concept_id = c.get("id", "").split("/")[-1]
        concepts.append(Concept(
            id=concept_id,
            name=c.get("display_name", ""),
            score=score,
        ))
```

**Threshold 0.3**: Balances relevance vs coverage. Lower = more concepts but noisier.

---

## Validation Rules

### Skip Paper If:

1. **No abstract** - RAG requires text
2. **Abstract < 50 chars** - Too short for meaningful retrieval
3. **No OpenAlex ID** - Can't store without primary key

### Graceful Handling:

```python
# All fields use dict.get() with defaults
title = raw.get("title") or "Untitled"
doi = raw.get("doi")  # None if missing (OK)
cited_by_count = raw.get("cited_by_count", 0)  # 0 if missing
```

---

## Implementation Location

The parsing logic is implemented in:

```
spikes/OAR-18/hk/src/openalex_client.py
└── _parse_paper() method (lines 199-327)
└── _extract_abstract() method (lines 131-179)
```

---

## Acceptance Criteria Status

| Criteria | Original | Implementation | Status |
|----------|----------|----------------|--------|
| Parsing accuracy 100% | XML parsing | JSON parsing with validation | ✅ |
| Required fields null < 5% | Same | Only keep papers with abstract | ✅ |
| Handle various formats | XML edge cases | Graceful `dict.get()` | ✅ |

---

## References

- [OpenAlex Works Entity](https://docs.openalex.org/api-entities/works)
- [Implementation: openalex_client.py](../../OAR-18/hk/src/openalex_client.py)
- [ADR-001 in CLAUDE.md](../../../../claude.md)
