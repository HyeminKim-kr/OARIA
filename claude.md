# CLAUDE.md - OARIA (Oncology AI Research Intelligence Assistant)

> **Owner**: 김혜민
> **Project Duration**: 7 weeks
> **Last Updated**: 2025-12-23

---

## 🎯 Project Overview

I am building **OARIA** (Oncology AI Research Intelligence Assistant) - an agentic RAG system that helps researchers query and synthesize oncology/cancer research literature.

### Core Value Proposition
- Answer oncology research questions with **cited evidence** from academic papers
- **Multi-Gate safety system** ensures answer quality and domain relevance
- Agentic task decomposition for complex multi-part questions

---

## 🏗️ Architecture Decision Records (ADR)

This section explains WHY each technology was chosen. Claude Code should follow these decisions.

### ADR-001: OpenAlex over PubMed for Paper API

**Decision:** Use OpenAlex as primary paper source, NOT PubMed.

**Context:** The original OARIA spec suggested PubMed, but we chose OpenAlex instead.

**Reasoning:**
| Factor | OpenAlex | PubMed |
|--------|----------|--------|
| Paper Coverage | 250M+ papers (ALL academic fields) | 35M (biomedical only) |
| Oncology Papers | ✅ Includes ALL PubMed papers | ✅ Native |
| API Design | Cursor pagination, no key needed | Offset pagination, key recommended |
| Metadata Richness | Citations, concepts, institutions, topics | Basic metadata |
| Rate Limits | 10 req/sec (polite pool with email) | 3 req/sec without key |
| Abstract Format | Inverted index (needs reconstruction) | Plain text |

**Why This Matters:**
1. OpenAlex includes ALL PubMed/MEDLINE papers plus more
2. Better API = faster development, simpler pagination
3. Richer metadata = better filtering and analysis
4. The architecture becomes reusable for other domains if needed

**Consequences:**
- Must implement `_extract_abstract()` to reconstruct from inverted index
- Use OpenAlex concept IDs instead of MeSH terms for filtering
- Papers have `openalex_id` (e.g., "W2741809807") as primary key

---

### ADR-002: Qdrant over Pinecone/ChromaDB for Vector Database

**Decision:** Use Qdrant as vector database.

**Context:** Many vector DBs exist (Pinecone, ChromaDB, Weaviate, Milvus, pgvector).

**Reasoning:**
| Factor | Qdrant | Pinecone | ChromaDB | pgvector |
|--------|--------|----------|----------|----------|
| Open Source | ✅ Yes | ❌ No | ✅ Yes | ✅ Yes |
| Hybrid Search | ✅ Native | ❌ No | ❌ No | ❌ No |
| Production Ready | ✅ Yes | ✅ Yes | ⚠️ Limited | ⚠️ Limited |
| Self-Hosted | ✅ Yes | ❌ No | ✅ Yes | ✅ Yes |
| Filtering | ✅ Rich | ✅ Rich | ⚠️ Basic | ⚠️ Basic |

**Why Qdrant Specifically:**
1. **Hybrid Search Native**: Supports dense + sparse vectors out of the box (critical for BGE-M3)
2. **Open Source**: No vendor lock-in, can self-host
3. **Production Grade**: Used by large companies, battle-tested
4. **Rich Filtering**: Can filter by year, journal, citation count during search
5. **RRF Fusion Built-in**: Reciprocal Rank Fusion for combining dense/sparse results

**Consequences:**
- Run via Docker: `docker run -p 6333:6333 qdrant/qdrant`
- Collection needs both `dense` and `sparse` vector configs
- Use `query_points()` with `prefetch` for hybrid search

---

### ADR-003: BGE-M3 over PubMedBERT for Embeddings

**Decision:** Use BGE-M3 for embeddings, NOT domain-specific PubMedBERT.

**Context:** The original OARIA spec suggested PubMedBERT (biomedical-specific). We chose BGE-M3 instead.

**Reasoning:**
| Factor | BGE-M3 | PubMedBERT |
|--------|--------|------------|
| Domain | General (all fields) | Biomedical only |
| Hybrid Support | ✅ Dense + Sparse | ❌ Dense only |
| Multilingual | ✅ 100+ languages | ❌ English only |
| Dimension | 1024 | 768 |
| Korean Support | ✅ Yes | ❌ No |
| Retrieval Performance | State-of-the-art | Good for bio |

**Why BGE-M3 Specifically:**
1. **Hybrid Embeddings**: Produces BOTH dense (semantic) AND sparse (lexical) vectors
   - Dense: Understands "lung cancer" ≈ "pulmonary carcinoma"
   - Sparse: Finds exact matches for "EGFR", "TP53"
2. **Better Retrieval**: Outperforms domain-specific models on benchmarks
3. **Korean Support**: Can handle Korean queries and papers
4. **Future Flexibility**: Works for any domain, not locked to biomedical

**Consequences:**
- Model is large (~2GB) - load ONCE at startup, never per-request
- Use `FlagEmbedding` library: `from FlagEmbedding import BGEM3FlagModel`
- Must store both `dense_vecs` and `lexical_weights` in Qdrant
- Reranker: Use `BAAI/bge-reranker-v2-m3` for consistency

---

### ADR-004: BGE-M3 Sparse over Traditional BM25

**Decision:** Use BGE-M3's sparse vectors for lexical search, NOT traditional BM25.

**Context:** BM25 is a classic keyword-based ranking algorithm (used in Elasticsearch).

**What is BM25?**
BM25 (Best Matching 25) is a 1990s keyword ranking algorithm:
```
BM25 scores documents based on:
- Term Frequency (TF): How often do query words appear?
- Inverse Document Frequency (IDF): How rare/important are these words?
- Document Length normalization
```

**Comparison:**
| Aspect | BM25 | BGE-M3 Sparse |
|--------|------|---------------|
| Type | Hand-crafted TF-IDF formula | Learned token weights |
| Speed | ✅ Very fast | ✅ Fast |
| GPU Required | ❌ No | ⚠️ For encoding |
| Exact Match | ✅ Excellent | ✅ Good |
| Learned Weights | ❌ No (static formula) | ✅ Yes (trained) |
| Out-of-vocabulary | ❌ Struggles | ✅ Better handling |
| Setup Complexity | Medium (separate index) | ✅ Already in BGE-M3 |

**Why BGE-M3 Sparse Instead of BM25:**
1. **Already included**: BGE-M3 produces sparse vectors alongside dense - no extra system needed
2. **Learned weights**: Neural model learns better term importance than hand-crafted TF-IDF
3. **Single model**: One embedding model for both semantic AND lexical search
4. **Benchmarks**: BGE-M3 sparse often outperforms BM25 on retrieval tasks
5. **Simpler architecture**: No need for separate Elasticsearch/BM25 index

**Our Hybrid Search Architecture:**
```
Query → BGE-M3 Model
            ├── Dense Vector (semantic similarity)
            └── Sparse Vector (lexical matching) ← This replaces BM25!
                      ↓
              Qdrant Hybrid Search (RRF Fusion)
                      ↓
              Combined Results
```

**When to Reconsider BM25:**
- If BGE-M3 sparse underperforms on exact medical terms (benchmark first)
- If you need CPU-only search without GPU
- If mentor specifically requires traditional BM25 for comparison

**Consequences:**
- No separate BM25/Elasticsearch setup needed
- Sparse vectors stored in Qdrant alongside dense
- Use RRF (Reciprocal Rank Fusion) to combine dense + sparse results

---

### ADR-005: Configuration-Based Domain Architecture

**Decision:** Use config file for all domain-specific settings.

**Context:** Hard-coding "oncology" everywhere would make the system inflexible.

**Implementation:**
```python
# src/config/domain_config.py
DOMAIN_CONFIG = {
    "domain_name": "oncology",
    "openalex_concepts": ["C126322002", "C502942594", ...],
    "classifier_labels": ["oncology", "cardiology", ...],
    "rejection_messages": {...},
    "system_prompt": "...",
}
```

**Why This Matters:**
1. All domain-specific logic in ONE file
2. Easy to test with different configs
3. Clean separation of concerns
4. Can swap domains by changing config (hypothetically)

**Consequences:**
- Never hard-code "oncology" or concept IDs in business logic
- Always read from `DOMAIN_CONFIG`
- Prompts, messages, filters all come from config

---

### ADR-006: Three-Gate Safety Architecture

**Decision:** Implement three sequential quality gates from OARIA spec.

**Flow:**
```
Query → [Gate 1: Domain] → RAG Search → [Gate 2: Retrieval] → Generate → [Gate 3: RAGAS] → Response
```

**Gate Details:**
| Gate | Purpose | Threshold | Failure |
|------|---------|-----------|---------|
| Gate 1 | Is query oncology-related? | confidence ≥ 0.8 | Reject with domain message |
| Gate 2 | Did we find relevant papers? | similarity ≥ 0.7, ≥3 docs | "Insufficient info" |
| Gate 3 | Is answer faithful to sources? | RAGAS ≥ 0.85 | Low confidence warning |

**Why Three Gates:**
1. **Gate 1 (Early Reject)**: Don't waste compute on off-topic queries
2. **Gate 2 (Quality Check)**: Don't hallucinate when no evidence exists
3. **Gate 3 (Faithfulness)**: Ensure answer actually uses retrieved papers

**Implementation Order:**
We build the RAG pipeline first (F-02, F-03, F-05, F-06), then add Gate 1 (F-01) later.
This allows testing the core RAG without domain filtering first.

**Consequences:**
- Every query must pass ALL gates sequentially
- Never skip gates for "simple" queries
- Each gate returns structured result with pass/fail + reason

---

### ADR-007: Async-First Architecture

**Decision:** Use async/await for all I/O operations.

**Reasoning:**
- OpenAlex API calls: Need to fetch thousands of papers
- Database operations: Bulk inserts, queries
- LLM API calls: Claude API is async
- Vector search: Qdrant client supports async

**Implementation Pattern:**
```python
# ✅ Correct
async def search_papers(query: str) -> list[Paper]:
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        return parse(response.json())

# ❌ Wrong - blocks event loop
def search_papers(query: str) -> list[Paper]:
    response = requests.get(url)  # BLOCKING!
    return parse(response.json())
```

**Consequences:**
- Use `httpx` not `requests`
- Use `asyncpg` or `sqlalchemy[asyncio]` for DB
- Use `asyncio.sleep()` for rate limiting
- Entry points need `asyncio.run()`

---

## 🛠 Technology Stack Summary

| Component | Technology | ADR |
|-----------|------------|-----|
| Paper API | **OpenAlex** | ADR-001 |
| Vector DB | **Qdrant** | ADR-002 |
| Embeddings | **BGE-M3** (dense + sparse) | ADR-003 |
| Lexical Search | **BGE-M3 Sparse** (not BM25) | ADR-004 |
| Metadata DB | **PostgreSQL** | Standard choice |
| Orchestration | **LangGraph** | For F-04 agent |
| Evaluation | **RAGAS** | Industry standard |
| LLM | **Claude API** | Anthropic's model |
| HTTP Client | **httpx** | ADR-007 (async) |

---

## 📋 My Responsibilities (Updated Order)

**Priority: Build RAG pipeline first, then add Domain Classifier (Gate 1) later.**

| Week | Feature | Description | Priority |
|------|---------|-------------|----------|
| W1-2 | **F-02 Paper Crawler** | OpenAlex API로 암 논문 자동 수집 | 🔴 First |
| W2-4 | **F-03 Evidence RAG** | BGE-M3 + Qdrant 기반 검색 증강 생성 | 🔴 Core |
| W3-4 | **F-05 Retrieval Confidence** | 검색 결과 신뢰도 검증 (Gate 2) | 🔴 Core |
| W4-5 | **F-06 RAGAS Evaluation** | 답변 품질 자동 평가 (Gate 3) | 🔴 Core |
| W5-6 | **F-01 Domain Classifier** | 입력 쿼리의 oncology 도메인 분류 (Gate 1) | 🟡 Later |
| W5-6 | **F-04 Agent Task Decomposition** | LangGraph 기반 복합 질문 분해 | 🟡 Later |

**Why This Order:**
1. Can test RAG pipeline end-to-end without domain filtering
2. Core value is in retrieval + generation quality
3. Gate 1 is just a filter - easy to add once RAG works
4. Agent (F-04) depends on working RAG pipeline

---

## 📁 Project Structure

```
OARIA/
├── backend/
│   ├── pyproject.toml
│   ├── src/
│   │   ├── config/
│   │   │   ├── settings.py       # Pydantic settings
│   │   │   └── domain_config.py  # ADR-005
│   │   ├── crawler/              # F-02 (Week 1-2)
│   │   │   ├── openalex_client.py
│   │   │   ├── models.py
│   │   │   └── database.py
│   │   ├── rag/                  # F-03 (Week 2-4)
│   │   │   ├── embedder.py       # BGE-M3 (ADR-003, ADR-004)
│   │   │   ├── chunker.py
│   │   │   ├── indexer.py
│   │   │   ├── retriever.py      # Hybrid search (ADR-002)
│   │   │   ├── reranker.py
│   │   │   └── pipeline.py
│   │   ├── gates/                # F-05, F-06 (Week 3-5)
│   │   │   ├── gate2_retrieval.py
│   │   │   └── gate3_ragas.py
│   │   ├── classifier/           # F-01 (Week 5-6) - LATER
│   │   │   └── gate1_domain.py
│   │   └── agent/                # F-04 (Week 5-6) - LATER
│   ├── scripts/
│   └── tests/
├── frontend/
├── docs/
├── spikes/
│   └── OAR-20/
│       └── hk/
│           └── docs/
│               └── OARIA_F02_F03_Specification.md
└── claude.md                     # This file
```

---

## 💻 Code Conventions

### Always Use Type Hints
```python
from pydantic import BaseModel

class Paper(BaseModel):
    openalex_id: str
    title: str
    abstract: str | None
```

### Async for I/O (ADR-007)
```python
async def fetch_papers() -> list[Paper]:
    async with httpx.AsyncClient() as client:
        ...
```

### Structured Logging
```python
import structlog
logger = structlog.get_logger()
logger.info("papers_fetched", count=100, duration_ms=450)
```

### Load Models Once
```python
# ✅ Good - class attribute, loaded once
class Embedder:
    def __init__(self):
        self.model = BGEM3FlagModel('BAAI/bge-m3')

# ❌ Bad - loads 2GB model every call
def embed(text):
    model = BGEM3FlagModel('BAAI/bge-m3')
```

---

## 🔧 Development Commands

```bash
# Setup
cd backend
uv venv
source .venv/bin/activate
uv pip install -e ".[dev]"

# Docker services
docker run -p 6333:6333 qdrant/qdrant
docker run -p 5432:5432 -e POSTGRES_PASSWORD=password postgres:16

# Scripts
python scripts/init_db.py
python scripts/crawl_papers.py --limit 1000
python scripts/build_index.py

# Tests
pytest tests/ -v
```

---

## 🌐 Environment Variables

```bash
# .env
ANTHROPIC_API_KEY=sk-ant-...
DATABASE_URL=postgresql://postgres:password@localhost:5432/oaria
QDRANT_HOST=localhost
QDRANT_PORT=6333
OPENALEX_EMAIL=your-email@example.com
```

---

## 🎯 Success Metrics

| Metric | Target |
|--------|--------|
| Papers collected | ≥ 50,000 |
| Retrieval Precision@5 | ≥ 80% |
| Citation accuracy | 100% |
| Faithfulness (RAGAS) | ≥ 0.85 |
| Answer Relevancy (RAGAS) | ≥ 0.80 |
| Simple query latency | < 3s |
| Domain classification accuracy | ≥ 95% (later) |

---

## 📚 Key References

- [OpenAlex API Docs](https://docs.openalex.org/)
- [Qdrant Documentation](https://qdrant.tech/documentation/)
- [BGE-M3 on HuggingFace](https://huggingface.co/BAAI/bge-m3)
- [FlagEmbedding GitHub](https://github.com/FlagOpen/FlagEmbedding)
- [LangGraph Docs](https://langchain-ai.github.io/langgraph/)
- [RAGAS Docs](https://docs.ragas.io/)
- Detailed Spec: `spikes/OAR-20/hk/docs/OARIA_F02_F03_Specification.md`

---

*Claude Code: Always follow the ADRs above. They explain WHY we chose each technology.*
*Build order: F-02 → F-03 → F-05 → F-06 → F-01 → F-04*
