# OAR-36: RAG Pipeline Integration API Implementation

> **Jira Ticket**: OAR-36
> **Status**: Completed
> **Author**: HK
> **Date**: 2025-12-30
> **File**: `src/rag_pipeline.py`

---

## Summary

Implemented a unified RAG (Retrieval-Augmented Generation) pipeline that orchestrates all components: Retriever, Reranker, Generator, and Citation Linker into a single, cohesive API.

---

## Requirements (from Jira)

| Requirement | Implementation |
|-------------|----------------|
| POST /api/v1/ask endpoint | `RAGAPIHandler.handle_ask()` ready for FastAPI/Flask |
| Input: { query, top_k, rerank_top_n } | `RAGQuery` dataclass with defaults |
| Output: { answer, evidence[], retrieval_scores, processing_time_ms } | `RAGResponse` dataclass with `to_dict()` |
| Simple query < 3 seconds | Pipeline optimized, streaming available |
| Complex query < 10 seconds | Timeout handling with configurable limit |
| Error handling and timeout | `RAGError` class, async timeout support |

---

## Design Decisions

### 1. Why a Unified Pipeline Class?

```
Without Pipeline:
  User → Retriever → Reranker → Generator → Citation Linker
           ↓            ↓           ↓              ↓
         Error?      Error?      Error?        Error?
         Handle      Handle      Handle        Handle

With Pipeline:
  User → RAGPipeline
              ↓
         (Orchestrates all components internally)
              ↓
         Single error handling point
```

**Benefits:**
- **Single Entry Point**: One class to rule them all
- **Consistent Error Handling**: All errors caught and formatted consistently
- **Timing Breakdown**: Track each stage's performance
- **Easy Testing**: Inject mock components for unit tests
- **API Ready**: Can be exposed as endpoint directly

### 2. Why Lazy Loading?

```python
@property
def retriever(self):
    if self._retriever is None:
        from retriever import Retriever
        self._retriever = Retriever()
    return self._retriever
```

**Reasoning:**
| Component | Model Size | Load Time |
|-----------|-----------|-----------|
| Retriever (PubMedBERT) | ~400MB | ~5s |
| Reranker (Cross-encoder) | ~100MB | ~2s |
| Generator (Claude client) | ~0MB | <1s |
| Citation Linker | ~0MB | <1s |

- Only load what's needed
- Faster startup for testing
- Allows component injection for mocking

### 3. Why Separate Timing for Each Stage?

```python
@dataclass
class RAGResponse:
    processing_time_ms: float      # Total
    retrieval_time_ms: float       # Stage 1
    rerank_time_ms: float          # Stage 2
    generation_time_ms: float      # Stage 3
```

**Use Cases:**
- **Identify Bottlenecks**: Which stage is slow?
- **SLA Monitoring**: Track if stages exceed thresholds
- **Optimization Decisions**: Where to invest effort
- **User Feedback**: Show "searching...", "ranking...", "generating..."

**Typical Timing Breakdown:**
```
┌─────────────────────────────────────────────────────────────┐
│  Total Pipeline: ~2500ms                                    │
├─────────────────────────────────────────────────────────────┤
│  Retrieval:   ████░░░░░░░░░░░░░░░░░░░░░  ~100ms (4%)       │
│  Reranking:   ██████░░░░░░░░░░░░░░░░░░░  ~300ms (12%)      │
│  Generation:  ████████████████████████░  ~2100ms (84%)     │
│  Citation:    ░░░░░░░░░░░░░░░░░░░░░░░░░  <1ms (~0%)        │
└─────────────────────────────────────────────────────────────┘
```

### 4. Why Evidence Dataclass Separate from LinkedCitation?

```python
@dataclass
class Evidence:
    """External API format"""
    paper_id: str
    title: str
    relevance_score: float
    url: str
    citation_number: int
```

vs

```python
@dataclass
class LinkedCitation:
    """Internal citation linker format"""
    citation_number: int
    paper_id: str
    paper_title: str
    # ... more internal fields
```

**Reasoning:**
- **API Contract**: `Evidence` is the public API contract, stable
- **Internal Flexibility**: `LinkedCitation` can change without breaking API
- **Separation of Concerns**: Pipeline owns response format, linker owns linking logic

### 5. Why Async API Handler?

```python
async def handle_ask(self, query, top_k, rerank_top_n) -> dict:
    response = await asyncio.wait_for(
        loop.run_in_executor(None, self.pipeline.query, request),
        timeout=self.timeout,
    )
```

**Reasoning:**
- **Non-Blocking**: Don't block event loop while ML models run
- **Timeout Support**: Kill long-running queries
- **Framework Compatible**: Works with FastAPI, Starlette, etc.
- **Scalable**: Can handle multiple concurrent requests

---

## Pipeline Flow

```
User Query: "What is EGFR inhibitor efficacy in lung cancer?"
           │
           ▼
┌──────────────────────────────────────────────────────────────┐
│ STAGE 1: RETRIEVAL (OAR-32)                                  │
│ Time: ~100ms                                                 │
├──────────────────────────────────────────────────────────────┤
│ 1. Embed query with PubMedBERT → [0.12, -0.34, ...]         │
│ 2. Search vector store for top_k=20 similar chunks           │
│ 3. Return docs with cosine similarity scores                 │
│                                                              │
│ Output: 20 documents, scores [0.89, 0.85, 0.82, ...]        │
└──────────────────────────────────────────────────────────────┘
           │
           ▼
┌──────────────────────────────────────────────────────────────┐
│ STAGE 2: RERANKING (OAR-33)                                  │
│ Time: ~300ms                                                 │
├──────────────────────────────────────────────────────────────┤
│ 1. Cross-encoder scores each (query, document) pair          │
│ 2. Sort by true relevance (not just similarity)              │
│ 3. Keep top_n=5 highest scoring documents                    │
│                                                              │
│ Output: 5 best documents, rerank_scores [0.95, 0.91, ...]   │
└──────────────────────────────────────────────────────────────┘
           │
           ▼
┌──────────────────────────────────────────────────────────────┐
│ STAGE 3: GENERATION (OAR-34)                                 │
│ Time: ~2000ms                                                │
├──────────────────────────────────────────────────────────────┤
│ 1. Format context with [1], [2], [3] numbered sources        │
│ 2. Build prompt with citation requirements                   │
│ 3. Call Claude API                                           │
│ 4. Get answer with inline citations                          │
│                                                              │
│ Output: "EGFR inhibitors show 60-70% response rates [1]..."  │
└──────────────────────────────────────────────────────────────┘
           │
           ▼
┌──────────────────────────────────────────────────────────────┐
│ STAGE 4: CITATION LINKING (OAR-35)                           │
│ Time: <1ms                                                   │
├──────────────────────────────────────────────────────────────┤
│ 1. Extract citation numbers [1], [2], [3] from answer        │
│ 2. Map to paper metadata (title, DOI, PMID)                  │
│ 3. Validate all citations exist in sources                   │
│ 4. Generate clickable URLs                                   │
│                                                              │
│ Output: Evidence list with paper details and URLs            │
└──────────────────────────────────────────────────────────────┘
           │
           ▼
┌──────────────────────────────────────────────────────────────┐
│ RESPONSE                                                     │
│                                                              │
│ {                                                            │
│   "answer": "EGFR inhibitors show 60-70% response...[1]",   │
│   "evidence": [                                              │
│     {"paper_id": "W123", "title": "...", "url": "..."},     │
│   ],                                                         │
│   "retrieval_scores": [0.89, 0.85, ...],                    │
│   "processing_time_ms": 2450                                 │
│ }                                                            │
└──────────────────────────────────────────────────────────────┘
```

---

## Implementation Details

### Data Classes

```python
@dataclass
class RAGQuery:
    """Input for RAG pipeline"""
    query: str                        # User's question
    top_k: int = 20                   # Initial retrieval count
    rerank_top_n: int = 5             # Final docs after reranking
    min_score: float = 0.0            # Minimum similarity threshold
    filter_metadata: dict = None      # Optional metadata filters

@dataclass
class RAGResponse:
    """Complete pipeline output"""
    answer: str                       # Generated answer with citations
    evidence: list[Evidence]          # Cited papers
    retrieval_scores: list[float]     # Similarity scores
    processing_time_ms: float         # Total time
    citations_used: list[int]         # [1, 2, 3]
    citations_valid: bool             # All citations valid?
    # ... timing breakdown

@dataclass
class Evidence:
    """Single cited paper"""
    paper_id: str
    title: str
    text_snippet: str
    relevance_score: float
    doi: str
    pmid: str
    url: str                          # Clickable link
    citation_number: int              # [1], [2], etc.
```

### Error Handling

```python
@dataclass
class RAGError:
    error_type: str      # "retrieval_failed", "timeout", etc.
    message: str         # Human-readable message
    suggestion: str      # How to fix

# Raised at each stage with context
try:
    retrieval_result = self.retriever.retrieve(...)
except Exception as e:
    raise RAGError(
        error_type="retrieval_failed",
        message=f"Failed to retrieve: {e}",
        suggestion="Try different query or check vector store"
    )
```

---

## Usage Examples

### Basic Usage

```python
from rag_pipeline import RAGPipeline, RAGQuery

pipeline = RAGPipeline()

response = pipeline.query(RAGQuery(
    query="What is EGFR inhibitor efficacy in lung cancer?",
    top_k=20,
    rerank_top_n=5,
))

print(response.answer)
print(f"Citations: {response.citations_used}")
print(f"Time: {response.processing_time_ms:.0f}ms")

for evidence in response.evidence:
    print(f"  [{evidence.citation_number}] {evidence.title}")
    print(f"      URL: {evidence.url}")
```

### Simple One-Liner

```python
from rag_pipeline import ask_simple

answer = ask_simple("What are EGFR inhibitors?")
print(answer)
```

### With Streaming

```python
from rag_pipeline import RAGPipeline, RAGQuery

pipeline = RAGPipeline()
request = RAGQuery(query="What is EGFR?")

print("Answer: ", end="")
for chunk in pipeline.query_stream(request):
    print(chunk, end="", flush=True)
print()
```

### FastAPI Integration

```python
from fastapi import FastAPI
from rag_pipeline import RAGAPIHandler

app = FastAPI()
handler = RAGAPIHandler(timeout_seconds=30.0)

@app.post("/api/v1/ask")
async def ask(query: str, top_k: int = 20, rerank_top_n: int = 5):
    result = await handler.handle_ask(query, top_k, rerank_top_n)
    return result
```

### With Custom Components (Testing)

```python
from rag_pipeline import RAGPipeline
from unittest.mock import Mock

# Mock components for testing
mock_retriever = Mock()
mock_retriever.retrieve.return_value = MockRetrievalResult(...)

pipeline = RAGPipeline(
    retriever=mock_retriever,
    reranker=mock_reranker,
    generator=mock_generator,
    citation_linker=mock_linker,
)

# Now test without actual ML models
response = pipeline.query(RAGQuery(query="test"))
```

---

## API Specification

### POST /api/v1/ask

**Request:**
```json
{
    "query": "What is EGFR inhibitor efficacy in lung cancer?",
    "top_k": 20,
    "rerank_top_n": 5
}
```

**Response (Success):**
```json
{
    "success": true,
    "data": {
        "answer": "EGFR inhibitors demonstrate significant efficacy...[1][2]",
        "evidence": [
            {
                "paper_id": "W2963284341",
                "title": "EGFR TKIs in NSCLC: A Review",
                "text_snippet": "First-generation EGFR TKIs...",
                "relevance_score": 0.92,
                "doi": "10.1016/j.lungcan.2020.01.001",
                "url": "https://doi.org/10.1016/j.lungcan.2020.01.001",
                "citation_number": 1
            }
        ],
        "retrieval_scores": [0.89, 0.85, 0.82, 0.78, 0.75],
        "processing_time_ms": 2450,
        "citations_used": [1, 2],
        "citations_valid": true,
        "metadata": {
            "model": "claude-sonnet-4-20250514",
            "input_tokens": 1500,
            "output_tokens": 400,
            "timings": {
                "retrieval_ms": 100,
                "rerank_ms": 300,
                "generation_ms": 2050
            }
        }
    }
}
```

**Response (Error):**
```json
{
    "success": false,
    "error": {
        "type": "timeout",
        "message": "Query exceeded 30s timeout",
        "suggestion": "Try a simpler query or reduce top_k"
    }
}
```

---

## Performance Targets

| Metric | Target | Typical |
|--------|--------|---------|
| Simple query | < 3 seconds | ~2.5s |
| Complex query | < 10 seconds | ~5-8s |
| Retrieval stage | < 200ms | ~100ms |
| Reranking stage | < 500ms | ~300ms |
| Generation stage | < 3s | ~2s |
| Citation linking | < 10ms | <1ms |

### Optimization Tips

1. **Reduce top_k**: Fewer docs = faster retrieval
2. **Reduce rerank_top_n**: Fewer docs to score
3. **Use streaming**: Better perceived latency
4. **Cache embeddings**: Query embedding can be cached
5. **Model size**: Use smaller reranker for speed

---

## Error Handling Matrix

| Error | Stage | Handling | User Message |
|-------|-------|----------|--------------|
| No results | Retrieval | Return empty | "관련 정보를 찾지 못했습니다" |
| Vector store down | Retrieval | Raise RAGError | "검색 서비스 연결 실패" |
| Reranker OOM | Rerank | Raise RAGError | "문서 정렬 중 오류" |
| API key invalid | Generate | Raise RAGError | "답변 생성 실패" |
| Rate limited | Generate | Retry + backoff | (Internal retry) |
| Timeout | Any | Return error | "시간 초과, 다시 시도해주세요" |

---

## Integration with Gates

The pipeline is designed to work with Gate 2 (Retrieval Confidence):

```python
# Future integration point in query():

# After retrieval, before generation
gate2_result = check_retrieval_confidence(request.query, reranked_docs)
if not gate2_result.passed:
    return RAGResponse(
        answer="",
        evidence=[],
        gate2_passed=False,
        gate2_details={"reason": gate2_result.reason}
    )
```

See OAR-37, OAR-38, OAR-39, OAR-40 for Gate 2 implementation.

---

## File Location

```
/spikes/HK/src/rag_pipeline.py
```

---

## Related Tickets

- **OAR-29**: Chunker (text splitting)
- **OAR-30**: Embedder (PubMedBERT)
- **OAR-31**: Vector Store (ChromaDB/Qdrant)
- **OAR-32**: Retriever (provides input)
- **OAR-33**: Reranker (improves relevance)
- **OAR-34**: Generator (produces answer)
- **OAR-35**: Citation Linker (links citations)
- **OAR-37-40**: Gate 2 components (retrieval confidence)
