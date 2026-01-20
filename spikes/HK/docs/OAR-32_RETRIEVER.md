# OAR-32: Retriever Implementation

> **Jira Ticket**: OAR-32
> **Status**: Completed
> **Author**: HK
> **Date**: 2025-12-30
> **File**: `src/retriever.py`

---

## Summary

Implemented a semantic retriever that combines the embedder and vector store into a unified search interface. Takes natural language queries and returns relevant document chunks with similarity scores.

---

## Requirements (from Jira)

| Requirement | Implementation |
|-------------|----------------|
| Query embedding generation | Uses `PubMedBERTEmbedder.embed()` |
| Top-k similar chunk retrieval | `retrieve(query, top_k=10)` |
| Similarity score return | `SearchResult.score` in results |
| Search time < 100ms | Timing tracked in `RetrievalResult` |
| Cosine similarity based | Normalized embeddings + vector store |
| Metadata filter support | `filter_dict` parameter |

---

## Design Decisions

### 1. Why Unified Interface?

```
Without Retriever:
┌────────────────────────────────────────────────────────────┐
│  User Code                                                 │
│                                                            │
│  emb = embedder.embed(query)                              │
│  results = vector_store.search(emb.tolist(), top_k=10)    │
│  # Manual timing, filtering, formatting...                 │
└────────────────────────────────────────────────────────────┘

With Retriever:
┌────────────────────────────────────────────────────────────┐
│  User Code                                                 │
│                                                            │
│  result = retriever.retrieve(query, top_k=10)             │
│  # Everything handled: embedding, search, timing          │
└────────────────────────────────────────────────────────────┘
```

**Benefits:**
- Simpler API for downstream components
- Consistent error handling
- Automatic performance tracking
- Single point for configuration

### 2. Why RetrievalResult Dataclass?

```python
@dataclass
class RetrievalResult:
    query: str              # Original query (for logging)
    results: list[SearchResult]  # Retrieved chunks
    query_time_ms: float    # Vector search time
    total_time_ms: float    # Including embedding
    top_k: int              # Requested count
    filter_applied: dict    # Active filters

    @property
    def max_score(self) -> float:  # For Gate 2 threshold
    @property
    def scores(self) -> list[float]  # All scores
```

**Why properties for scores?**
- Gate 2 needs `max_score` for threshold check (OAR-37)
- Gate 2 needs all `scores` for min relevant docs (OAR-38)
- Clean interface without exposing internal structure

### 3. Why Timing Metrics?

```
┌──────────────────────────────────────────────────────────┐
│  Retrieval Timing Breakdown                               │
│                                                          │
│  total_time_ms = embed_time + query_time                 │
│       │              │            │                      │
│       │              │            └── Vector search      │
│       │              └────────────── Query → embedding   │
│       └───────────────────────────── Full roundtrip     │
│                                                          │
│  Target: total_time_ms < 100ms                          │
└──────────────────────────────────────────────────────────┘
```

**Use cases:**
- Performance monitoring
- Bottleneck identification
- SLA compliance checking
- Gate 2 could reject slow queries

### 4. Why `min_score` Parameter?

```python
result = retriever.retrieve(query, min_score=0.5)
# Only returns results with score >= 0.5
```

**Why filter by score?**
- Pre-filter irrelevant results
- Reduce work for reranker
- Gate 2 can use this directly
- User-configurable strictness

---

## Implementation Details

### Retrieval Flow

```
┌───────────────────────────────────────────────────────────────┐
│  Input: "What are EGFR inhibitors?"                           │
└───────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌───────────────────────────────────────────────────────────────┐
│  Step 1: Embed Query                                          │
│  embedder.embed("What are EGFR inhibitors?")                  │
│  → [0.12, -0.34, 0.56, ...] (768 dims)                       │
│  Time: ~10ms (cached) to ~50ms (first time)                  │
└───────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌───────────────────────────────────────────────────────────────┐
│  Step 2: Vector Search                                        │
│  vector_store.search(query_embedding, top_k=10)               │
│  Time: ~2ms (Qdrant) to ~50ms (in-memory brute force)        │
└───────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌───────────────────────────────────────────────────────────────┐
│  Step 3: Filter & Format                                      │
│  - Apply min_score filter if specified                        │
│  - Package into RetrievalResult                               │
└───────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌───────────────────────────────────────────────────────────────┐
│  Output: RetrievalResult                                      │
│  - results: [SearchResult, SearchResult, ...]                │
│  - max_score: 0.89                                           │
│  - total_time_ms: 45.2                                       │
└───────────────────────────────────────────────────────────────┘
```

### Context Formatting for RAG

```python
context, results = retriever.get_context_for_generation(
    query="What causes lung cancer?",
    top_k=5,
    max_context_chars=8000,
)
```

Output format:
```
[1] (score: 0.89, paper: W001)
EGFR mutations are found in approximately 15% of non-small cell lung cancer...

[2] (score: 0.85, paper: W002)
Smoking is the leading cause of lung cancer, responsible for approximately 85%...

[3] (score: 0.78, paper: W001)
Other risk factors include radon exposure, asbestos, and air pollution...
```

**Why this format?**
- Numbered for citation tracking (`[1]`, `[2]`, etc.)
- Score visible for transparency
- Paper ID for provenance
- Easy to parse in prompts

---

## Usage Examples

### Basic Retrieval

```python
from retriever import Retriever, create_retriever

# Quick setup
retriever = create_retriever(
    vector_backend="qdrant",
    embedder_model="pubmedbert",
)

# Search
result = retriever.retrieve("EGFR inhibitors in lung cancer", top_k=10)

print(f"Found {len(result.results)} results")
print(f"Best match score: {result.max_score:.3f}")
print(f"Search time: {result.total_time_ms:.1f}ms")

for r in result.results:
    print(f"  [{r.score:.2f}] {r.text[:100]}...")
```

### Filtered Retrieval

```python
# Only search within specific paper
result = retriever.retrieve(
    query="treatment response",
    top_k=5,
    filter_dict={"paper_id": "W123456"}
)

# Only high-confidence results
result = retriever.retrieve(
    query="EGFR mutations",
    top_k=20,
    min_score=0.7,  # Only scores >= 0.7
)
```

### Indexing Documents

```python
# Prepare chunks (from chunker)
chunks = [
    {"text": "...", "paper_id": "W1", "chunk_index": 0},
    {"text": "...", "paper_id": "W1", "chunk_index": 1},
    ...
]

# Index into retriever
count = retriever.index_chunks(chunks)
print(f"Indexed {count} chunks")

# Now searchable
result = retriever.retrieve("my query")
```

### Full Pipeline Integration

```python
from chunker import TextChunker
from retriever import create_retriever

# Initialize
chunker = TextChunker(chunk_size=512, chunk_overlap=50)
retriever = create_retriever(vector_backend="qdrant")

# Process and index papers
for paper in papers:
    chunks = chunker.chunk_text(paper["full_text"], paper["id"])
    chunk_dicts = [c.to_dict() for c in chunks]
    retriever.index_chunks(chunk_dicts)

# Query
result = retriever.retrieve("What are the side effects of immunotherapy?")
```

---

## Performance Characteristics

| Component | Typical Time | Notes |
|-----------|-------------|-------|
| Query embedding | 10-50ms | Cached after first call |
| Vector search (Qdrant) | 2-10ms | HNSW ANN |
| Vector search (ChromaDB) | 5-20ms | HNSW |
| Vector search (InMemory) | 50-200ms | Brute force O(n) |
| **Total (Qdrant)** | **15-60ms** | ✅ Under 100ms target |

---

## Integration with Gate 2

The `RetrievalResult` provides all data needed for Gate 2 validation:

```python
result = retriever.retrieve(query)

# OAR-37: Similarity Threshold
if result.max_score < 0.7:
    return "Insufficient similarity"

# OAR-38: Min Relevant Docs
relevant = sum(1 for s in result.scores if s >= 0.6)
if relevant < 3:
    return "Not enough relevant documents"

# Pass to reranker/generator
```

---

## Limitations & Future Improvements

### Current Limitations

1. **Sequential batch**: `retrieve_batch` is sequential (could parallelize)
2. **Single embedding model**: Fixed at initialization
3. **No query expansion**: No synonym/related term expansion

### Potential Improvements

1. **Hybrid search**: Combine semantic + keyword (BM25)
2. **Query rewriting**: LLM-based query enhancement
3. **Async retrieval**: Non-blocking for web APIs
4. **Multi-model ensemble**: Average multiple embeddings

---

## File Location

```
/spikes/HK/src/retriever.py
```

---

## Related Tickets

- **OAR-30**: Embedder (used for query embedding)
- **OAR-31**: Vector Store (used for search)
- **OAR-33**: Reranker (next in pipeline)
- **OAR-37**: Gate 2 threshold check (uses max_score)
- **OAR-38**: Gate 2 min docs (uses scores)
