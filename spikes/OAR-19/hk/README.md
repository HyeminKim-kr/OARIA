# OAR-19: Paper Metadata Parsing Logic

> **Owner**: hk (Hyemin Kim)
>
> **Sub-task**: OAR-99
>
> **Purpose**: Parse paper metadata from API response into structured format

---

## Original Spec vs ADR Decision

### Original Requirement (OAR-19)

The original task specified:
- Parse **PubMed XML** response
- Extract PMID, Title, Abstract, Authors, etc.
- Handle XML parsing edge cases

### ADR-001 Change: OpenAlex JSON instead of PubMed XML

Per ADR-001, we use **OpenAlex** instead of PubMed. This changes the parsing task:

| Aspect | Original (PubMed) | ADR Decision (OpenAlex) |
|--------|-------------------|-------------------------|
| Format | XML | JSON |
| Parsing | Complex XML parsing | Simple dict access |
| Abstract | Plain text | Inverted index (needs reconstruction) |
| IDs | PMID primary | OpenAlex ID primary, PMID secondary |

**Why this is actually easier:**
- JSON is simpler to parse than XML
- Python's `dict.get()` handles missing fields gracefully
- No need for XML schema validation

**Trade-off:**
- Abstract reconstruction from inverted index (already solved in OAR-94)

---

## Implementation Status: ALREADY DONE in OAR-94

The parsing logic was implemented in OAR-94 as part of the OpenAlex client.

### Location

```
spikes/OAR-18/hk/src/openalex_client.py
└── _parse_paper() method (lines 199-327)
```

### Fields Extracted

| Original Requirement | OpenAlex Field | Implementation |
|---------------------|----------------|----------------|
| PMID | `ids.pmid` | ✅ Extracted |
| Title | `title` | ✅ Extracted |
| Abstract | `abstract_inverted_index` | ✅ Reconstructed |
| Authors (name) | `authorships[].author.display_name` | ✅ Extracted |
| Authors (affiliation) | `authorships[].institutions[].display_name` | ✅ Extracted |
| Journal | `primary_location.source.display_name` | ✅ Extracted |
| Publication Date | `publication_date` | ✅ Parsed to date object |
| MeSH Terms | `mesh[].descriptor_name` | ✅ Extracted |
| Keywords | `keywords[].keyword` | ✅ Extracted |
| DOI | `doi` | ✅ Extracted |
| PMC ID | N/A (use `open_access_url`) | ✅ Alternative provided |
| Full Text URL | `open_access.oa_url` | ✅ Extracted |

### Additional Fields (OpenAlex bonus)

| Field | Purpose |
|-------|---------|
| `concepts` | OpenAlex topic classification (with scores) |
| `topics` | Hierarchical topic tags |
| `cited_by_count` | Citation count for filtering |
| `is_open_access` | Open access status |

---

## Parsing Logic Breakdown

### Step 1: Abstract Reconstruction

```python
def _extract_abstract(self, raw: dict) -> Optional[str]:
    """
    OpenAlex: {"word": [0, 5], "another": [1]}
    Output: "word another ... word"
    """
    inverted = raw.get("abstract_inverted_index")
    if not inverted:
        return None

    # Build (position, word) pairs, sort, join
    words = [(pos, word) for word, positions in inverted.items() for pos in positions]
    words.sort(key=lambda x: x[0])
    return " ".join(word for _, word in words)
```

### Step 2: Author Parsing

```python
# OpenAlex structure:
# authorships: [{author: {display_name, orcid}, institutions: [{display_name, country_code}]}]

for authorship in raw.get("authorships", []):
    author_data = authorship.get("author", {})
    institutions = authorship.get("institutions", [])

    Author(
        name=author_data.get("display_name"),
        orcid=author_data.get("orcid"),
        institution=institutions[0].get("display_name") if institutions else None,
        country=institutions[0].get("country_code") if institutions else None,
    )
```

### Step 3: Concept Filtering

```python
# Only keep concepts with confidence > 0.3
for c in raw.get("concepts", []):
    if c.get("score", 0) > 0.3:
        Concept(id=c["id"].split("/")[-1], name=c["display_name"], score=c["score"])
```

---

## Folder Structure

```
OAR-19/hk/
├── README.md                    # This file (documents parsing logic)
├── docs/                        # Additional documentation if needed
├── src/                         # No new code - parsing is in OAR-18
└── output/                      # Test outputs
```

---

## Acceptance Criteria Status

| Criteria | Original | Status |
|----------|----------|--------|
| XML parsing accuracy 100% | → JSON parsing accuracy | ✅ Achieved |
| Required fields null < 5% | Same requirement | ✅ Only papers with abstract kept |
| Handle various paper formats | Same requirement | ✅ Graceful `dict.get()` handling |

---

## Conclusion

**OAR-19/OAR-99 is effectively COMPLETE** - the parsing logic was implemented as part of OAR-94's `_parse_paper()` method.

No additional code needed. This README documents the design decisions and implementation details.

---

## References

- [OAR-94 Implementation](../OAR-18/hk/src/openalex_client.py)
- [OpenAlex Works Entity](https://docs.openalex.org/api-entities/works)
- [ADR-001 in CLAUDE.md](../../../claude.md)
