# OAR-30: PubMedBERT Embedder Implementation

> **Jira Ticket**: OAR-30
> **Status**: Completed
> **Author**: HK
> **Date**: 2025-12-30
> **File**: `src/embedder.py`

---

## Summary

Implemented a PubMedBERT-based text embedder that generates 768-dimensional vectors for biomedical text chunks, with batch processing optimization and file-based caching.

---

## Requirements (from Jira)

| Requirement | Implementation |
|-------------|----------------|
| 768-dimensional vector output | PubMedBERT outputs 768-dim by default |
| Batch embedding support | `embed_batch()` with configurable batch size |
| 100+ chunks/second | GPU-accelerated, batched processing |
| Embedding caching | `EmbeddingCache` class with disk + memory caching |

---

## Design Decisions

### 1. Why PubMedBERT?

```
┌────────────────────────────────────────────────────────────────────┐
│  Model Comparison for Biomedical Text                              │
├──────────────────┬──────────────┬──────────────┬───────────────────┤
│  Model           │  Domain      │  Vocabulary  │  Performance      │
├──────────────────┼──────────────┼──────────────┼───────────────────┤
│  BERT-base       │  General     │  General     │  Baseline         │
│  BioBERT         │  Biomedical  │  PubMed      │  +5-10% on bio    │
│  PubMedBERT  ✓   │  Biomedical  │  PubMed+PMC  │  SOTA on bio      │
│  SciBERT         │  Scientific  │  Scientific  │  Good on papers   │
└──────────────────┴──────────────┴──────────────┴───────────────────┘
```

**Why PubMedBERT is optimal for OARIA:**

1. **Pre-training data**: Trained on 14M PubMed abstracts + 3.2B tokens from PMC full-text
2. **Medical vocabulary**: Knows terms like "EGFR", "adenocarcinoma", "pembrolizumab"
3. **Benchmark performance**: SOTA on biomedical NLP benchmarks (BLURB)
4. **Same dimensionality**: 768-dim matches most vector DB defaults

### 2. Why sentence-transformers Library?

**Alternative approaches considered:**

| Approach | Pros | Cons |
|----------|------|------|
| Raw HuggingFace | Full control | Manual pooling, batching |
| **sentence-transformers** ✓ | Optimized, simple API | Slight overhead |
| OpenAI embeddings | Best quality | API cost, privacy |

**Reasoning:**
- sentence-transformers handles pooling strategy (mean pooling)
- Built-in batching with GPU optimization
- Automatic L2 normalization for cosine similarity
- Progress bars for long batches
- Easy model switching

### 3. Why Lazy Loading?

```python
@property
def model(self):
    if self._model is None:
        self._model = SentenceTransformer(self.model_name)  # 5-10 sec load
    return self._model
```

**Problem without lazy loading:**
```python
embedder = PubMedBERTEmbedder()  # Blocks for 10 seconds even if not used
```

**With lazy loading:**
```python
embedder = PubMedBERTEmbedder()  # Instant
# ... other setup code ...
embedder.embed(text)  # Model loads here, only when needed
```

### 4. Why File-Based Caching?

```
┌─────────────────────────────────────────────────────────────────┐
│  Embedding Workflow                                             │
│                                                                 │
│  Text → Hash(text + model) → Check Cache → Hit? Return cached   │
│                                      ↓ Miss                     │
│                            Model.encode(text)                   │
│                                      ↓                          │
│                            Save to cache → Return embedding     │
└─────────────────────────────────────────────────────────────────┘
```

**Cache structure:**
```
.embedding_cache/
├── a3f4b2c1e8d9.npy    # SHA256(model:text)[:16] → numpy array
├── 7d2e9f4a1b6c.npy
└── ...
```

**Why cache?**
- Embedding is expensive: ~50ms per chunk on GPU, ~500ms on CPU
- Same text always produces same embedding (deterministic)
- Re-running pipeline shouldn't re-embed 50,000 chunks
- Disk cache persists across sessions

---

## Implementation Details

### Core Classes

```python
class EmbeddingCache:
    """File-based embedding cache with memory hot cache."""

    def __init__(self, cache_dir=".embedding_cache"):
        self.cache_dir = Path(cache_dir)
        self._memory_cache = {}  # Hot cache for repeated access

    def get(self, text, model_name) -> np.ndarray | None: ...
    def set(self, text, model_name, embedding): ...
```

```python
class PubMedBERTEmbedder:
    """PubMedBERT-based embedder with batch processing."""

    SUPPORTED_MODELS = {
        "pubmedbert": "microsoft/BiomedNLP-PubMedBERT-base-uncased-abstract-fulltext",
        "pubmedbert-retrieval": "pritamdeka/S-PubMedBert-MS-MARCO",
        "bge-base": "BAAI/bge-base-en-v1.5",
        "bge-small": "BAAI/bge-small-en-v1.5",
    }

    def embed(self, text: str) -> np.ndarray: ...
    def embed_batch(self, texts: list[str]) -> np.ndarray: ...
    def embed_chunks(self, chunks: list) -> list[dict]: ...
```

### Device Selection Logic

```python
if torch.cuda.is_available():
    device = "cuda"      # NVIDIA GPU
elif torch.backends.mps.is_available():
    device = "mps"       # Apple Silicon GPU
else:
    device = "cpu"       # Fallback
```

### Normalization

All embeddings are L2-normalized:
```python
embedding = model.encode(text, normalize_embeddings=True)
# ||embedding|| = 1.0
```

**Why normalize?**
- Cosine similarity = dot product when normalized
- Faster similarity computation: `np.dot(a, b)` instead of `cosine_similarity(a, b)`
- Consistent score range: [-1, 1]

---

## Supported Models

| Key | Model | Dim | Use Case |
|-----|-------|-----|----------|
| `pubmedbert` | microsoft/BiomedNLP-PubMedBERT-base-uncased-abstract-fulltext | 768 | Default, best for biomedical |
| `pubmedbert-retrieval` | pritamdeka/S-PubMedBert-MS-MARCO | 768 | Fine-tuned for retrieval |
| `bge-base` | BAAI/bge-base-en-v1.5 | 768 | General purpose, very good |
| `bge-small` | BAAI/bge-small-en-v1.5 | 384 | Faster, lower quality |

---

## Usage Examples

### Basic Usage

```python
from embedder import PubMedBERTEmbedder

embedder = PubMedBERTEmbedder(model_key="pubmedbert")

# Single text
embedding = embedder.embed("EGFR mutations in lung cancer")
print(embedding.shape)  # (768,)
```

### Batch Processing

```python
texts = [
    "EGFR mutations are common in NSCLC.",
    "Immunotherapy has transformed cancer treatment.",
    "BRCA1 mutations increase breast cancer risk.",
]

embeddings = embedder.embed_batch(texts)
print(embeddings.shape)  # (3, 768)
```

### With Chunks from Chunker

```python
from chunker import TextChunker
from embedder import PubMedBERTEmbedder

# Chunk the text
chunker = TextChunker()
chunks = chunker.chunk_text(paper_text, paper_id="W123")

# Embed chunks
embedder = PubMedBERTEmbedder()
embedded_chunks = embedder.embed_chunks(chunks)

# Each chunk now has 'embedding' field
for chunk in embedded_chunks:
    print(f"Chunk {chunk['chunk_index']}: {len(chunk['embedding'])} dims")
```

### Computing Similarity

```python
import numpy as np

query = embedder.embed("What are EGFR inhibitors?")
doc = embedder.embed("Erlotinib is an EGFR tyrosine kinase inhibitor.")

# Since normalized, dot product = cosine similarity
similarity = np.dot(query, doc)
print(f"Similarity: {similarity:.3f}")  # ~0.85
```

---

## Performance Characteristics

| Metric | GPU (CUDA) | Apple Silicon (MPS) | CPU |
|--------|------------|---------------------|-----|
| Single embed | ~10ms | ~30ms | ~200ms |
| Batch (32) | ~100ms | ~300ms | ~3000ms |
| Throughput | ~300/sec | ~100/sec | ~15/sec |

**Note**: First call includes model loading time (~5-10 seconds).

---

## Cache Statistics

To check cache effectiveness:
```python
# After running pipeline
import os
cache_files = os.listdir(".embedding_cache")
print(f"Cached embeddings: {len(cache_files)}")
print(f"Cache size: {sum(os.path.getsize(f'.embedding_cache/{f}') for f in cache_files) / 1024:.1f} KB")
```

---

## Dependencies

```bash
pip install sentence-transformers torch numpy
```

For GPU acceleration:
```bash
# CUDA (NVIDIA)
pip install torch --index-url https://download.pytorch.org/whl/cu118

# MPS (Apple Silicon) - included in default torch
```

---

## Limitations & Future Improvements

### Current Limitations

1. **Model size**: PubMedBERT is ~400MB download on first use
2. **Memory**: Requires ~2GB GPU memory for efficient batching
3. **Single model**: One model instance per embedder

### Potential Improvements

1. **Async embedding**: Background embedding while processing continues
2. **Model quantization**: INT8 quantization for 2x speed, slight quality loss
3. **Distributed caching**: Redis-based cache for multi-process pipelines
4. **Hybrid models**: Dense + sparse embeddings (like BGE-M3)

---

## File Location

```
/spikes/HK/src/embedder.py
```

---

## Related Tickets

- **OAR-29**: Text Chunker (produces input for embedder)
- **OAR-31**: Vector Store (stores embeddings)
- **OAR-32**: Retriever (uses embeddings for search)
