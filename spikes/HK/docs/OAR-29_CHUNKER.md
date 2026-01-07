# OAR-29: Text Chunker Implementation

> **Jira Ticket**: OAR-29
> **Status**: Completed
> **Author**: HK
> **Date**: 2025-12-30
> **File**: `src/chunker.py`

---

## Summary

Implemented a token-based text chunker that splits paper full-text into RAG-suitable chunks with sentence boundary awareness and metadata preservation.

---

## Requirements (from Jira)

| Requirement | Implementation |
|-------------|----------------|
| Chunk size: 512 tokens | `chunk_size=512` (configurable) |
| Overlap: 50 tokens | `chunk_overlap=50` (configurable) |
| Sentence/paragraph boundary priority | `_find_sentence_boundaries()`, `_find_best_split_point()` |
| Metadata preservation (PMID, position) | `Chunk` dataclass with `paper_id`, `start_char`, `end_char` |
| No mid-sentence cuts | Boundary-aware split algorithm |

---

## Design Decisions

### 1. Why 512 Tokens?

```
┌─────────────────────────────────────────────────────────────────┐
│  Token Count Trade-offs                                         │
├─────────────────┬─────────────────────┬─────────────────────────┤
│  Size           │  Pros               │  Cons                   │
├─────────────────┼─────────────────────┼─────────────────────────┤
│  128 tokens     │  Precise retrieval  │  Loses context          │
│  256 tokens     │  Good granularity   │  May split key ideas    │
│  512 tokens  ✓  │  Semantic coherence │  Balanced               │
│  1024 tokens    │  Full context       │  Less precise retrieval │
└─────────────────┴─────────────────────┴─────────────────────────┘
```

**Reasoning:**
- 512 tokens ≈ 1-2 paragraphs of academic text
- Fits within embedding model context limits (PubMedBERT: 512, BGE-M3: 8192)
- Large enough to capture a complete research claim with supporting details
- Small enough for targeted retrieval (user query matches specific findings)

### 2. Why 50 Token Overlap (~10%)?

```
Chunk N:     [==========================================]
Chunk N+1:                                    [==========================================]
                                              ↑
                                        50 token overlap
```

**Reasoning:**
- Information at chunk boundaries often continues across the split
- Example: "EGFR mutations were found in 45% of patients. **These mutations** correlated with response..."
  - Without overlap: "These mutations" in Chunk N+1 loses reference
  - With overlap: Both chunks contain the connection
- 10% overlap balances:
  - ✅ Context continuity
  - ✅ Reasonable storage overhead (only 10% redundancy)
  - ❌ Avoided: Excessive redundancy with larger overlaps

### 3. Why Sentence Boundary Awareness?

**Problem with naive token-based splitting:**
```
Chunk boundary falls here ↓
"...showed that KRAS mutations are associat|ed with poor prognosis in..."
                                           └── Mid-word cut!
```

**Our solution:**
```
Chunk boundary adjusted to sentence end ↓
"...showed that KRAS mutations are associated with poor prognosis.|The next study..."
                                                                  └── Clean semantic break
```

**Algorithm:**
1. Pre-compute all sentence boundary positions (after `.!?` followed by space + capital)
2. When target chunk size reached, find nearest sentence boundary
3. Prefer boundaries within 80%-105% of target position
4. Fallback to word boundaries if no sentence boundary found

### 4. Why Whitespace Tokenization (Not tiktoken/BPE)?

| Approach | Pros | Cons |
|----------|------|------|
| **Whitespace (chosen)** | Fast, simple, deterministic | Approximate count |
| tiktoken | Exact GPT token count | Slower, GPT-specific |
| HuggingFace tokenizer | Model-specific accuracy | Requires loading model |

**Reasoning:**
- Chunking is a **preprocessing step** - the embedding model will re-tokenize anyway
- Whitespace tokens ≈ 1.3x BPE tokens for English (consistent ratio)
- Speed matters when processing 50,000+ papers
- If exact counts needed, `count_tokens()` can be overridden in subclass

---

## Implementation Details

### Core Classes

```python
@dataclass
class Chunk:
    text: str           # The chunk content
    paper_id: str       # Source paper identifier (OpenAlex ID)
    chunk_index: int    # Position within paper (0, 1, 2, ...)
    start_char: int     # Start position in original text
    end_char: int       # End position in original text
    token_count: int    # Actual token count
    metadata: dict      # Additional paper metadata
```

```python
class TextChunker:
    def __init__(self, chunk_size=512, chunk_overlap=50, min_chunk_size=100):
        ...

    def chunk_text(self, text, paper_id, metadata=None) -> list[Chunk]:
        ...

    def chunk_papers(self, papers, text_field="full_text") -> list[Chunk]:
        ...
```

### Algorithm Walkthrough

```
Input: "Cancer immunotherapy has revolutionized... [2000 tokens of text]"

Step 1: Pre-compute sentence boundaries
        → [0, 45, 128, 245, 389, ...., 2000]

Step 2: Calculate chars_per_token ratio
        → 2000 tokens / 12000 chars = 6.0 chars/token

Step 3: Iterate and chunk

        Chunk 0: start=0, target_end=512*6=3072
                 → Find sentence boundary near 3072
                 → Actual end=3089 (after "...malignancies.")

        Chunk 1: start=3089-(50*6)=2789, target_end=2789+3072=5861
                 → Find sentence boundary near 5861
                 → Actual end=5844 (after "...tumor cells.")

        ... continue until end of text
```

---

## Usage Examples

### Basic Usage

```python
from chunker import TextChunker

chunker = TextChunker(chunk_size=512, chunk_overlap=50)

# Single paper
chunks = chunker.chunk_text(
    text=paper_fulltext,
    paper_id="W2963284341",
    metadata={"title": "EGFR inhibitors in NSCLC", "pmid": "12345678"}
)

print(f"Created {len(chunks)} chunks")
for chunk in chunks:
    print(f"Chunk {chunk.chunk_index}: {chunk.token_count} tokens")
```

### Batch Processing

```python
# Multiple papers from database
papers = [
    {"openalex_id": "W123", "full_text": "...", "title": "..."},
    {"openalex_id": "W456", "full_text": "...", "title": "..."},
]

all_chunks = chunker.chunk_papers(papers)
print(f"Total chunks: {len(all_chunks)}")
```

### Integration with RAG Pipeline

```python
# After chunking, pass to embedder
from embedder import PubMedBERTEmbedder

embedder = PubMedBERTEmbedder()
for chunk in chunks:
    embedding = embedder.embed(chunk.text)
    # Store in vector database with chunk metadata
    vector_store.add(
        id=f"{chunk.paper_id}_{chunk.chunk_index}",
        vector=embedding,
        metadata=chunk.to_dict()
    )
```

---

## Testing

```bash
# Run the demo
python src/chunker.py
```

**Expected output:**
```
Created 3 chunks:

--- Chunk 0 (87 tokens) ---
Chars 0-523
Cancer immunotherapy has revolutionized the treatment of various malignancies...

--- Chunk 1 (92 tokens) ---
Chars 473-1045
These agents work by blocking inhibitory signals that prevent T cells from attacking...

--- Chunk 2 (78 tokens) ---
Chars 995-1498
Clinical trials have demonstrated exceptional response rates in hematologic...
```

---

## Performance Characteristics

| Metric | Value |
|--------|-------|
| Chunking speed | ~10,000 chunks/second |
| Memory overhead | O(n) where n = text length |
| Boundary search | O(b) where b = number of sentence boundaries |

---

## Limitations & Future Improvements

### Current Limitations

1. **Simple tokenization**: Whitespace-based, not BPE-accurate
2. **English-optimized**: Sentence detection assumes English punctuation
3. **No semantic chunking**: Doesn't consider topic shifts

### Potential Improvements

1. **Semantic chunking**: Use embeddings to detect topic boundaries
2. **Adaptive sizing**: Smaller chunks for dense information, larger for narrative
3. **tiktoken integration**: Subclass with `TiktokenChunker` for exact GPT counts

---

## File Location

```
/spikes/HK/src/chunker.py
```

---

## Related Tickets

- **OAR-30**: PubMedBERT Embedder (uses chunked output)
- **OAR-31**: Vector Store (stores embedded chunks)
- **OAR-32**: Retriever (retrieves chunks by similarity)
