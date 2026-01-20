# OAR-11: Evidence RAG 시스템 (임시 E2E 데모)

> 발표용 임시 작업. 추후 OAR-11 하위 태스크로 재구현 예정.

## 파이프라인

```
PostgreSQL (수집된 논문)
    ↓
MinIO (fulltext)
    ↓
OAR-29 Chunker (청킹 + offset)
    ↓
OpenAI Embeddings
    ↓
Weaviate (Vector Store)
    ↓
RAG Query → LLM 답변 + Citation
```

## 실행 방법

```bash
# 1. 의존성 설치
uv sync

# 2. 인프라 시작 (spikes/yts에서)
cd ../yts && docker compose up -d

# 3. Weaviate 시작 (OAR-31에서)
cd ../OAR-31/yts && docker compose up -d

# 4. 논문 적재
OPENAI_API_KEY=sk-xxx uv run python src/ingest.py

# 5. RAG 데모
OPENAI_API_KEY=sk-xxx uv run python src/rag_demo.py
```

## 컴포넌트

| 컴포넌트 | 구현 |
|----------|------|
| Chunker | OAR-29 (Section + Recursive) |
| Embedder | OpenAI text-embedding-3-small |
| Vector Store | Weaviate (OAR-31) |
| Retriever | Weaviate hybrid search |
| Generator | OpenAI GPT-4o-mini |
| Citation | offset 기반 근거 재현 |
