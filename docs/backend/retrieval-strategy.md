# 검색 전략 (Retrieval Strategy)

> **작성일**: 2026-01-01
>
> **기반 스파이크**: OAR-29 (Chunker), OAR-31 (Vector Store), OAR-32 (Retriever)
>
> **상태**: 확정 (MVP)

---

## TL;DR (핵심 결정)

| 항목 | 결정 | 근거 |
|------|------|------|
| **검색 방식** | 벡터 유사도 (HNSW + Cosine) | 의미적 유사도 검색 |
| **임베딩 모델** | OpenAI text-embedding-3-small | API 간편, 저렴, 좋은 성능 |
| **Top-k** | 기본 k=5 (조정 가능) | Parent Retrieval과 조합 |
| **청킹 전략** | Adaptive (1000토큰 기준) | 짧은 섹션 보존, 긴 섹션 분할 |
| **Parent Retrieval** | Weaviate 기반 (섹션 청크 합치기) | 단순/빠름 |

---

## 1. 검색 아키텍처

### 1.1 전체 흐름

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   사용자    │     │   Backend   │     │  Weaviate   │     │    LLM      │
│   질문      │ ──▶ │  (FastAPI)  │ ──▶ │ (Vector DB) │ ──▶ │  (GPT-4o)   │
└─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘
                           │                   │
                           │  1. 질문 임베딩    │
                           │  2. Top-k 검색    │
                           │  3. Parent 조회   │
                           │  4. 컨텍스트 조립  │
                           │  5. LLM 답변 생성  │
                           ▼                   ▼
```

### 1.2 Parent-Child Retrieval 전략

> **핵심**: 검색은 작은 청크로 정밀하게, LLM에는 부모 섹션 전체를 전달

```
검색 시:
┌──────────────────────────────────────────────────────────┐
│  작은 청크 (700토큰)로 검색                               │
│  → 세밀한 의미 매칭                                       │
│  → Top-k 결과에서 paperId + section 추출                  │
└──────────────────────────────────────────────────────────┘
                        ↓
LLM 전달 시:
┌──────────────────────────────────────────────────────────┐
│  해당 섹션의 모든 청크 조회 → 합쳐서 부모 섹션 재구성      │
│  → 충분한 컨텍스트 제공                                   │
│  → 문맥 단절 방지                                         │
└──────────────────────────────────────────────────────────┘
```

**OAR-31 테스트 결과**: Parent Retrieval이 청크만 전달하는 것보다 답변 품질이 높음

---

## 2. 벡터 검색 설정

### 2.1 Weaviate HNSW 인덱스

```python
vector_index_config=wvc.config.Configure.VectorIndex.hnsw(
    distance_metric=wvc.config.VectorDistances.COSINE,  # 코사인 유사도
    ef_construction=128,  # 인덱스 빌드 품질 (높을수록 정확, 느림)
    max_connections=64    # 노드당 연결 수
)
```

| 파라미터 | 값 | 설명 |
|----------|-----|------|
| `distance_metric` | COSINE | 코사인 유사도 (0=동일, 2=반대) |
| `ef_construction` | 128 | 인덱스 빌드 시 탐색 범위 |
| `max_connections` | 64 | HNSW 그래프 연결 수 |

> **코사인 유사도**: 벡터 방향의 유사도 측정. 크기 무관, 방향만 비교.
> - 0에 가까울수록 유사
> - Weaviate는 `distance` 반환 (similarity = 1 - distance)

### 2.2 검색 메서드

```python
# 1. 벡터 검색 (기본)
response = collection.query.near_vector(
    near_vector=query_embedding,
    limit=5,
    return_metadata=MetadataQuery(distance=True),
)

# 2. 하이브리드 검색 (벡터 + 키워드)
response = collection.query.hybrid(
    query="lung cancer immunotherapy",
    vector=query_embedding,
    alpha=0.5,  # 0=키워드(BM25), 1=벡터, 0.5=균형
    limit=5,
)

# 3. 키워드 검색 (BM25)
response = collection.query.bm25(
    query="BRCA1 mutation",
    limit=5,
)
```

### 2.3 필터링

```python
from weaviate.classes.query import Filter

# 연도 필터
filters = Filter.by_property("year").greater_or_equal(2020)

# 섹션 필터
filters = Filter.by_property("section").equal("results")

# 복합 필터
filters = (
    Filter.by_property("year").greater_or_equal(2020) &
    Filter.by_property("section").contains_any(["results", "discussion"])
)
```

---

## 3. 청킹 전략

### 3.1 Adaptive Chunking (OAR-31 채택)

| 조건 | 처리 | 이유 |
|------|------|------|
| 섹션 ≤ 1000 토큰 | 분할 없이 통째로 | 의미적 완결성 유지 |
| 섹션 > 1000 토큰 | 700토큰 단위 분할 | 검색 정밀도 확보 |

```python
# 설정값
adaptive_threshold_tokens = 1000  # 분할 기준
chunk_size_tokens = 700           # 분할 시 청크 크기
chunk_overlap_tokens = 100        # 오버랩 (문맥 유지)
```

### 3.2 임베딩 입력 포맷

```python
# Contextual Embedding (검색 품질 향상)
embedding_input = f"""[TITLE] {title}
[SECTION] {section}
[YEAR] {year}
[TEXT] {chunk_text}"""
```

> **주의**: 임베딩 입력에는 prefix 포함, Weaviate 저장은 원문(text)만

---

## 4. Parent Retrieval 구현

### 4.1 Weaviate 기반 (채택)

```python
def get_parent_section(collection, paper_id: str, section: str) -> str:
    """같은 섹션의 모든 청크를 조회하여 합치기"""
    result = collection.query.fetch_objects(
        filters=(
            Filter.by_property("paperId").equal(paper_id) &
            Filter.by_property("section").equal(section)
        ),
        limit=50,
        return_properties=["content", "chunkIndex"],
    )

    if not result.objects:
        return ""

    # chunkIndex 순서로 정렬 후 합치기
    chunks = sorted(
        [(obj.properties["chunkIndex"], obj.properties["content"])
         for obj in result.objects],
        key=lambda x: x[0]
    )

    return "\n\n".join([content for _, content in chunks])
```

### 4.2 검색 → Parent 조회 → LLM 전달

```python
async def search_with_parent(query: str, top_k: int = 5) -> list[dict]:
    # 1. 질문 임베딩
    query_embedding = embedding_client.embed_text(query)

    # 2. Top-k 청크 검색
    search_result = collection.query.near_vector(
        near_vector=query_embedding,
        limit=top_k,
        return_properties=["paperId", "section", "content", "title"],
    )

    # 3. 중복 제거하며 Parent 섹션 조회
    seen = set()
    contexts = []

    for obj in search_result.objects:
        paper_id = obj.properties["paperId"]
        section = obj.properties["section"]
        key = f"{paper_id}|{section}"

        if key in seen:
            continue
        seen.add(key)

        # Parent 섹션 조회
        parent_text = get_parent_section(collection, paper_id, section)
        contexts.append({
            "paper_id": paper_id,
            "section": section,
            "title": obj.properties["title"],
            "content": parent_text,
        })

    return contexts
```

---

## 5. 임베딩 모델

### 5.1 현재 설정 (MVP)

| 항목 | 값 |
|------|-----|
| 모델 | `text-embedding-3-small` |
| 차원 | 1536 |
| 비용 | ~$0.02 / 1M tokens |
| 버전 문자열 | `openai:text-embedding-3-small:v1` |

### 5.2 추후 비교 예정

| 모델 | 특징 | 상태 |
|------|------|------|
| MedCPT | 의료 논문 특화 | 추후 스파이크 |
| text-embedding-3-large | 더 높은 성능 | 비용 6배 |

---

## 6. 평가 방법 (OAR-31)

### 6.1 Synthetic QA

```
청크 → LLM으로 Q/A 쌍 생성 → 해당 청크가 Ground Truth
```

### 6.2 Hit Rate@K

```
생성된 질문으로 검색 → GT 청크가 Top-K에 있는지 측정
```

### 6.3 E2E 답변 비교

```
같은 질문 → 두 전략으로 RAG 답변 생성 → LLM이 품질 평가
```

---

## 7. 구현 체크리스트

### MVP (챗봇 구현 시)

- [ ] `/chat` 엔드포인트 생성
- [ ] 벡터 검색 + Parent Retrieval 통합
- [ ] LLM 답변 생성 (스트리밍)
- [ ] 인용 정보 반환 (paperId, section, title)

### 추후

- [ ] 하이브리드 검색 옵션
- [ ] 필터 UI (연도, 섹션)
- [ ] MedCPT 비교 스파이크
- [ ] Hit Rate 모니터링

---

## 참고

- [OAR-20 Weaviate 스키마](../../OAR-20/yts/docs/weaviate-스키마-설계.md)
- [OAR-29 Chunker 설계](../../OAR-29/yts/docs/chunker-implementation.md)
- [OAR-31 임베딩 모델 결정](../../OAR-31/yts/docs/embedding-model-decision.md)
- [Weaviate HNSW 문서](https://weaviate.io/developers/weaviate/config-refs/schema/vector-index#hnsw-index-parameters)
