# OAR-35: Citation Linker Implementation

> **Jira Ticket**: OAR-35
> **Status**: Completed
> **Author**: HK
> **Date**: 2025-12-30
> **File**: `src/citation_linker.py`

---

## Summary

Implemented a citation linking system that extracts citations from generated text, maps them to source paper metadata, validates citation accuracy, and generates clickable reference links.

---

## Requirements (from Jira)

| Requirement | Implementation |
|-------------|----------------|
| [PMID:number] pattern extraction | Changed to [1], [2] format; mapped to paper_id |
| Paper metadata lookup | `link_citations()` maps to full metadata |
| Citation snippet mapping | `text_snippet` field in LinkedCitation |
| 100% citation accuracy | `validate_citations()` catches invalid refs |
| Detect invalid PMIDs | Invalid citations flagged in validation |
| Paper detail link on click | `url` field with DOI/PubMed/OpenAlex links |

---

## Design Decisions

### 1. Why [1], [2] Format Instead of [PMID:...]?

**Original requirement**: `[PMID:12345678]`

**Changed to**: `[1]`, `[2]`, `[3]`

| Aspect | [PMID:...] | [1], [2] |
|--------|------------|----------|
| PMID availability | Many papers lack PMIDs | Always works |
| Token cost | ~15 tokens per citation | ~3 tokens |
| LLM compliance | Less reliable | Very reliable |
| Post-processing | Parse PMID from text | Simple index lookup |

**Reasoning:**
- OpenAlex papers often have only DOI or OpenAlex ID
- Numbered citations are standard academic format
- LLMs follow numbered references more consistently
- Citation Linker resolves [1] → actual paper metadata

### 2. Why Validation Matters?

```
Generated text with hallucination:
"EGFR inhibitors show 95% response rate [5]"
                                        ↑
                        Only 3 sources provided!

Without validation:
  User sees [5], clicks, nothing happens, loses trust

With validation:
  CitationValidation.invalid_citations = [5]
  Can warn user or regenerate
```

**Validation catches:**
- Citations to non-existent sources (hallucination)
- Unused sources (may indicate incomplete answer)
- Total citation count (for analytics)

### 3. Why URL Generation Priority?

```
Priority order for paper URLs:
1. DOI    → doi.org/{doi}         Most universal resolver
2. PMID   → pubmed.ncbi.nlm.nih.gov/{pmid}  For PubMed papers
3. OpenAlex → openalex.org/{id}   Fallback for any paper
```

**Why this order?**
- DOI is the universal academic identifier
- PubMed is familiar to medical researchers
- OpenAlex always has data (since we crawled from there)

### 4. Why Multiple Output Formats?

```python
# Markdown for chat interfaces
format_citations_as_footnotes(linked) → "## References\n[1] **Title**..."

# HTML for web apps
format_citations_as_html(linked) → "<div class='citation-list'>..."

# Enhanced text with clickable links
enhance_text_with_links(text, linked) → "...response [<a href='...'>1</a>]..."
```

**Use cases:**
- Markdown: CLI, Jupyter, Discord bots
- HTML: Streamlit, web frontend
- Enhanced: Interactive web display

---

## Implementation Details

### Data Classes

```python
@dataclass
class LinkedCitation:
    citation_number: int      # [1], [2], etc.
    paper_id: str            # OpenAlex ID
    paper_title: Optional[str]
    doi: Optional[str]
    pmid: Optional[str]
    journal: Optional[str]
    publication_date: Optional[str]
    text_snippet: str        # Relevant excerpt
    relevance_score: float   # From retriever/reranker
    url: Optional[str]       # Click-through link
```

```python
@dataclass
class CitationValidation:
    total_citations: int
    valid_citations: list[int]     # [1, 2, 3]
    invalid_citations: list[int]   # [5] (hallucinated)
    unused_sources: list[int]      # Sources not cited
    is_valid: bool
    error_message: Optional[str]
```

### Citation Extraction Flow

```
Input: "EGFR inhibitors show response [1]. Studies confirm [2][3]."

Step 1: Extract with regex \[(\d+)\]
  → matches: ["1", "2", "3"]

Step 2: Deduplicate and sort
  → [1, 2, 3]

Step 3: Link to sources
  [1] → sources[0] → {"paper_id": "W123", "doi": "10.1016/..."}
  [2] → sources[1] → {"paper_id": "W456", ...}
  [3] → sources[2] → {"paper_id": "W789", ...}

Output: [LinkedCitation(1, ...), LinkedCitation(2, ...), LinkedCitation(3, ...)]
```

### Validation Flow

```
Input:
  text: "Claims are supported [1][2][5]"
  sources: 3 sources available

Step 1: Extract citations → [1, 2, 5]

Step 2: Check each:
  [1] → source[0] exists ✅
  [2] → source[1] exists ✅
  [5] → source[4] doesn't exist ❌

Step 3: Find unused sources:
  sources[2] (number 3) not cited

Output:
  CitationValidation(
    valid_citations=[1, 2],
    invalid_citations=[5],
    unused_sources=[3],
    is_valid=False,
    error_message="Invalid citations: [5]. Only 3 sources available."
  )
```

---

## Usage Examples

### Basic Linking

```python
from citation_linker import CitationLinker

linker = CitationLinker()

text = "EGFR mutations predict response [1]. Resistance develops [2]."
sources = [
    {"paper_id": "W123", "score": 0.9, "metadata": {"title": "EGFR Review", "doi": "10.1016/..."}},
    {"paper_id": "W456", "score": 0.8, "metadata": {"title": "Resistance Study", "pmid": "12345"}},
]

linked = linker.link_citations(text, sources)

for cite in linked:
    print(f"[{cite.citation_number}] {cite.paper_title} - {cite.url}")
```

### Validation

```python
validation = linker.validate_citations(text, sources)

if not validation.is_valid:
    print(f"Warning: {validation.error_message}")

if validation.unused_sources:
    print(f"Sources not cited: {validation.unused_sources}")
```

### Full Pipeline Integration

```python
from generator import LLMGenerator
from citation_linker import CitationLinker

generator = LLMGenerator()
linker = CitationLinker()

# Generate answer
output = generator.generate(question, sources)

# Link and validate citations
linked = linker.link_citations(output.answer, output.context_sources)
validation = linker.validate_citations(output.answer, output.context_sources)

# Format output
answer_with_refs = output.answer + linker.format_citations_as_footnotes(linked)

# Or for web display
html_answer = linker.enhance_text_with_links(output.answer, linked)
html_refs = linker.format_citations_as_html(linked)
```

---

## Output Formats

### Markdown Footnotes

```markdown
---
## References

[1] **EGFR TKIs in NSCLC**. _Lung Cancer_ (2020-03) [Link](https://doi.org/10.1016/...)
[2] **Epidemiology of EGFR Mutations**. _JCO_ (2019-06) [Link](https://pubmed.ncbi.nlm.nih.gov/31234567/)
[3] **FLAURA Trial Results**. _NEJM_ (2020-01) [Link](https://doi.org/10.1056/...)
```

### HTML Output

```html
<div class="citation-list">
  <h3>References</h3>
  <ol>
    <li id="cite-1">
      <strong>EGFR TKIs in NSCLC</strong>
      <em>Lung Cancer</em> (2020-03)
      <a href="https://doi.org/10.1016/..." target="_blank">[Link]</a>
    </li>
    ...
  </ol>
</div>
```

### Enhanced Text (Clickable Citations)

```html
EGFR inhibitors show response rates of 60-70%
<a href="https://doi.org/10.1016/..." class="citation-link">[1]</a>.
```

---

## Handling Invalid Citations

When LLM hallucinates a citation:

```python
# Example: LLM cites [4] but only 3 sources exist
validation = linker.validate_citations(text, sources)

if validation.invalid_citations:
    # Option 1: Warn user
    print(f"⚠️ Citations {validation.invalid_citations} not found in sources")

    # Option 2: Regenerate with stricter prompt
    # Option 3: Remove invalid citations from display

# Invalid citations in linked list have special marker
for cite in linked:
    if cite.paper_id.startswith("INVALID"):
        print(f"[{cite.citation_number}] is hallucinated!")
```

---

## Integration Points

### With Generator Output

```python
# generator.generate() returns:
output.context_sources = [
    {"number": 1, "paper_id": "W123", "score": 0.9, "metadata": {...}},
    {"number": 2, "paper_id": "W456", "score": 0.8, "metadata": {...}},
]

# These map directly to citation linker input
linked = linker.link_citations(output.answer, output.context_sources)
```

### With Streamlit Display

```python
import streamlit as st

# Display answer with HTML citations
st.markdown(linker.enhance_text_with_links(answer, linked), unsafe_allow_html=True)

# Display reference list
st.markdown(linker.format_citations_as_footnotes(linked))
```

---

## Performance Characteristics

| Operation | Time |
|-----------|------|
| Extract citations | <1ms |
| Link citations | <1ms |
| Validate citations | <1ms |
| Format output | <1ms |

**Overhead**: Negligible compared to LLM generation

---

## Limitations & Future Improvements

### Current Limitations

1. **No fuzzy matching**: Citation must exactly match [n] format
2. **Single format**: Only supports [n] style
3. **No nested citations**: Can't handle [1a], [1b] style

### Potential Improvements

1. **Multiple formats**: Support APA, IEEE, etc.
2. **Citation context**: Extract the sentence containing each citation
3. **Citation grouping**: Group multiple citations to same paper
4. **Verification**: Check if citation actually supports the claim

---

## File Location

```
/spikes/HK/src/citation_linker.py
```

---

## Related Tickets

- **OAR-34**: Generator (produces text with citations)
- **OAR-36**: RAG Pipeline (uses citation linker for output)
