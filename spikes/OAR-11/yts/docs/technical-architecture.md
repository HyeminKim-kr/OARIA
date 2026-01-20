# OAR-11 Evidence RAG 시스템 기술 문서

> 작성일: 2025-12-30
> 버전: v0.1.0 (E2E 데모)

## 1. 시스템 아키텍처

```
┌─────────────────────────────────────────────────────────────────────┐
│                         사용자 질문                                  │
└─────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    1. Query Embedding                                │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │  OpenAI text-embedding-3-small                              │    │
│  │  - 차원: 1536                                                │    │
│  │  - 비용: $0.02 / 1M tokens                                   │    │
│  └─────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    2. Hybrid Search (Weaviate)                       │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │  Vector Search (70%) + BM25 Keyword Search (30%)            │    │
│  │  - 유사도: Cosine Similarity                                 │    │
│  │  - 인덱스: HNSW (Hierarchical Navigable Small World)        │    │
│  │  - alpha=0.7 (벡터 가중치)                                   │    │
│  └─────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    3. Context Assembly                               │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │  Top-K 청크 선택 (기본값: 5개)                                │    │
│  │  → LLM 프롬프트에 [1], [2], [3]... 형태로 삽입              │    │
│  └─────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    4. Answer Generation                              │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │  OpenAI GPT-4o-mini                                         │    │
│  │  - Temperature: 0.3 (일관성 중시)                            │    │
│  │  - Max tokens: 1500                                          │    │
│  │  - Streaming 지원                                            │    │
│  └─────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    5. Citation Linking                               │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │  답변 내 [1], [2] 참조 → 실제 논문 URL 매핑                  │    │
│  │  - Europe PMC 링크 제공                                      │    │
│  │  - offset 기반 원문 위치 추적 가능                           │    │
│  └─────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 2. 임베딩 모델

### 현재 사용 모델

| 항목 | 값 |
|------|-----|
| **모델명** | `text-embedding-3-small` |
| **제공사** | OpenAI |
| **차원 수** | 1536 |
| **최대 토큰** | 8191 |
| **비용** | $0.02 / 1M tokens |
| **버전 문자열** | `openai:text-embedding-3-small:v1` |

### 선택 이유

1. **비용 효율성**: 논문 1편당 약 30-50개 청크 → 약 $0.001 미만
2. **품질**: 의료 도메인에서도 준수한 성능
3. **속도**: API 응답 시간 ~500ms
4. **호환성**: 1536차원은 대부분의 벡터 DB와 호환

### 향후 비교 대상

| 모델 | 차원 | 특징 |
|------|------|------|
| MedCPT | 768 | PubMed 특화, 오픈소스 |
| PubMedBERT | 768 | 생의학 논문 특화 |
| text-embedding-3-large | 3072 | 더 높은 정확도 |

---

## 3. 벡터 데이터베이스 (Weaviate)

### 설정

```yaml
# docker-compose.yml
services:
  weaviate:
    image: semitechnologies/weaviate:1.28.0
    environment:
      DEFAULT_VECTORIZER_MODULE: 'none'  # BYOV (Bring Your Own Vectors)
      ENABLE_API_BASED_MODULES: 'false'
```

### 컬렉션 스키마 (PaperChunk)

```python
# 주요 속성
properties = [
    # 식별자
    ("paperId", DataType.TEXT),      # "pmc:PMC12345678"
    ("chunkId", DataType.TEXT),      # "pmc:PMC12345678|abstract|0"

    # 메타데이터
    ("pmcid", DataType.TEXT),        # "PMC12345678"
    ("title", DataType.TEXT),        # 논문 제목
    ("journal", DataType.TEXT),      # 저널명
    ("year", DataType.INT),          # 출판년도

    # 컨텐츠
    ("section", DataType.TEXT),      # "abstract", "introduction", ...
    ("chunkIndex", DataType.INT),    # 섹션 내 청크 순서
    ("content", DataType.TEXT),      # 청크 텍스트

    # 추적
    ("offsetStart", DataType.INT),   # 원문 시작 위치
    ("offsetEnd", DataType.INT),     # 원문 끝 위치
    ("embeddingVersion", DataType.TEXT),  # 임베딩 버전
]
```

### 인덱스 설정

| 설정 | 값 | 설명 |
|------|-----|------|
| **Vector Index** | HNSW | 고차원 벡터 검색에 최적화 |
| **Distance Metric** | Cosine | 텍스트 임베딩에 적합 |
| **ef** | 64 | 검색 정확도 (높을수록 정확) |
| **maxConnections** | 32 | 그래프 연결 수 |

---

## 4. 검색 방식

### Hybrid Search

```python
results = collection.query.hybrid(
    query="lung cancer immunotherapy",  # 키워드 검색용
    vector=query_embedding,              # 벡터 검색용
    alpha=0.7,                           # 벡터 70% + 키워드 30%
    limit=5,                             # Top-5 반환
)
```

### Alpha 값 의미

| alpha | 검색 방식 |
|-------|----------|
| 1.0 | 순수 벡터 검색 (의미적 유사도) |
| 0.7 | 벡터 중심 하이브리드 **(현재 사용)** |
| 0.5 | 균형 잡힌 하이브리드 |
| 0.0 | 순수 키워드 검색 (BM25) |

### 왜 0.7인가?

- 의학 논문은 전문 용어가 많아 키워드 매칭도 중요
- 그러나 의미적 유사도가 더 중요 (예: "immunotherapy" ↔ "immune checkpoint inhibitor")
- 0.7은 의미 검색 우선 + 키워드 보완

---

## 5. 청킹 전략 (OAR-29)

### Section + Recursive Chunking

```
논문 전문
    │
    ├── Abstract (섹션 1)
    │       └── 청크 1, 2, 3...
    │
    ├── Introduction (섹션 2)
    │       └── 청크 1, 2, 3...
    │
    ├── Methods (섹션 3)
    │       └── 청크 1, 2, 3...
    │
    └── Results (섹션 4)
            └── 청크 1, 2, 3...
```

### 청크 파라미터

| 파라미터 | 값 | 설명 |
|----------|-----|------|
| **chunk_size** | 800 토큰 | 청크 최대 크기 |
| **chunk_overlap** | 100 토큰 | 청크 간 겹침 (embedding_input 전용) |
| **separators** | `\n\n`, `\n`, `. `, ` ` | 분할 우선순위 |

### Offset 추적

```python
chunk = {
    "text": "원문 그대로의 텍스트",
    "offset_start": 1234,  # fulltext에서의 시작 위치
    "offset_end": 2056,    # fulltext에서의 끝 위치
}

# 검증: fulltext[offset_start:offset_end] == chunk.text
```

---

## 6. 데이터 흐름

### 적재 파이프라인 (Ingest)

```
1. PostgreSQL 조회
   └── papers 테이블에서 논문 메타데이터 조회
   └── paper_sections 테이블에서 섹션 정보 조회

2. MinIO (S3) 조회
   └── {canonical_prefix}/fulltext.txt 다운로드

3. 청킹 (OAR-29 Chunker)
   └── 섹션별 분리 → 재귀적 분할
   └── offset 정보 보존

4. 임베딩 생성
   └── OpenAI API 배치 호출 (10개씩)

5. Weaviate 저장
   └── UUID: chunk_id 기반 생성
   └── 중복 체크 후 삽입
```

### 검색 파이프라인 (Query)

```
1. 질문 임베딩
   └── OpenAI text-embedding-3-small

2. Weaviate Hybrid Search
   └── alpha=0.7, limit=5

3. 컨텍스트 조립
   └── [1] Title (section)\n{content}
   └── [2] Title (section)\n{content}
   └── ...

4. LLM 호출
   └── GPT-4o-mini (streaming)
   └── System prompt: Citation 포함 답변 요청

5. Citation 매핑
   └── [1] → PMC12345678, URL 생성
```

---

## 7. 성능 지표

### 현재 데이터

| 지표 | 값 |
|------|-----|
| 저장된 논문 수 | 5편 |
| 총 청크 수 | 152개 |
| 평균 청크/논문 | ~30개 |

### 응답 시간 (예상)

| 단계 | 시간 |
|------|------|
| 질문 임베딩 | ~500ms |
| Weaviate 검색 | ~200ms |
| LLM 첫 토큰 | ~1s |
| LLM 전체 응답 | ~5-10s |
| **총 (스트리밍)** | **~2s (첫 응답)** |

---

## 8. 실행 방법

### 환경 변수

```bash
export OPENAI_API_KEY="sk-..."
```

### 적재

```bash
cd spikes/OAR-11/yts
uv run python src/ingest.py --limit 10
```

### 웹 데모

```bash
uv run python src/web_demo.py
# http://localhost:7860
```

### CLI 데모

```bash
uv run python src/rag_demo.py           # 샘플 질문
uv run python src/rag_demo.py -i        # 대화형
```

---

## 9. 의존성

### 인프라

| 컴포넌트 | 버전 | 포트 |
|----------|------|------|
| PostgreSQL | 16 | 15432 |
| MinIO | latest | 19000 |
| Weaviate | 1.28.0 | 8080 |

### Python 패키지

```toml
dependencies = [
    "weaviate-client>=4.9.0",
    "openai>=1.0.0",
    "tiktoken>=0.7.0",
    "psycopg[binary]>=3.1.0",
    "boto3>=1.34.0",
    "gradio>=4.0.0",
]
```

---

## 10. 향후 개선 계획

1. **임베딩 모델 비교**: MedCPT vs OpenAI 스파이크 테스트
2. **Reranker 추가**: Cohere Rerank 또는 Cross-encoder
3. **청크 크기 최적화**: 600 vs 800 vs 1000 토큰 비교
4. **필터링 강화**: 연도, 저널, 섹션별 필터
5. **캐싱**: 자주 묻는 질문 캐싱
