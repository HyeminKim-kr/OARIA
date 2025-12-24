# RAG 청킹 전략 리서치

> **목적**: RAG 시스템에서 사용되는 청킹 전략들을 조사하고 비교
>
> **작성일**: 2025-12-23
>
> **참고**: OAR-18 Europe PMC 논문 수집 스파이크

---

## 왜 청킹이 중요한가?

LLM은 **제한된 컨텍스트 윈도우**를 가지고 있어서 긴 문서를 한 번에 처리할 수 없다.

| 문제 | 설명 |
|------|------|
| 청크가 너무 작으면 | 중요한 컨텍스트 손실 |
| 청크가 너무 크면 | 프롬프트에 안 들어감, 검색 정밀도 저하 |
| 잘못된 분할 | 문장 중간에서 자르면 의미 파괴 |

---

## 주요 청킹 전략

### 1. Fixed-Size Chunking (고정 크기)

가장 단순한 방법. 일정 문자/토큰 수로 분할.

```python
# LangChain CharacterTextSplitter
from langchain.text_splitter import CharacterTextSplitter

splitter = CharacterTextSplitter(
    chunk_size=1000,
    chunk_overlap=200
)
```

**장점**: 빠름, 구현 간단
**단점**: 의미 단위 무시, 문장 중간 분할 가능

---

### 2. Recursive Character Splitting (재귀적 분할) ⭐ 권장

계층적으로 분할: **섹션 → 문단 → 문장 → 단어** 순서로 시도.

```python
# LangChain RecursiveCharacterTextSplitter
from langchain.text_splitter import RecursiveCharacterTextSplitter

splitter = RecursiveCharacterTextSplitter(
    chunk_size=512,
    chunk_overlap=50,
    separators=["\n\n", "\n", " ", ""]  # 우선순위
)
```

**장점**: 문서 구조 보존, 의미 단위 유지
**단점**: 고정 크기보다 약간 느림

> 💡 **NVIDIA 2024 벤치마크**: RecursiveCharacterTextSplitter (400-512 토큰)이 **85-90% recall** 달성. 대부분의 팀에게 권장되는 기본값.

---

### 3. Semantic Chunking (의미 기반 분할)

문장 간 **임베딩 유사도**를 분석하여 의미가 바뀌는 지점에서 분할.

```python
# LangChain SemanticChunker
from langchain_experimental.text_splitter import SemanticChunker
from langchain_openai import OpenAIEmbeddings

splitter = SemanticChunker(
    embeddings=OpenAIEmbeddings(),
    breakpoint_threshold_type="percentile"
)
```

**장점**: 의미 일관성 최고, 주제별 그룹핑
**단점**: 임베딩 계산 비용, 처리 시간 증가

> 💡 **성능**: Semantic chunking이 다른 전략 대비 **recall 최대 9% 향상**. 단, 데이터셋에 따라 효과 상이.

---

### 4. Document Structure-Based (구조 기반)

HTML, Markdown, JSON 등 문서 구조를 활용한 분할.

```python
# LangChain HTMLHeaderTextSplitter
from langchain.text_splitter import HTMLHeaderTextSplitter

headers_to_split_on = [
    ("h1", "Header 1"),
    ("h2", "Header 2"),
]
splitter = HTMLHeaderTextSplitter(headers_to_split_on)
```

**장점**: 구조적으로 관련된 텍스트 그룹핑, 메타데이터 자동 추출
**단점**: 구조화된 문서에만 적용 가능

---

### 5. Page-Level Chunking (페이지 기반)

PDF 등에서 페이지 단위로 분할.

> 💡 **NVIDIA 2024 벤치마크**: Page-level chunking이 **0.648 accuracy**로 1위, 표준편차도 가장 낮음 (0.107). 다양한 문서 유형에서 일관된 성능.

---

### 6. Agentic Chunking (에이전트 기반)

LLM을 사용하여 "이 문장은 어디에 속해야 하는가?" 판단.

**장점**: 가장 정확한 의미 분할
**단점**: 비용 높음, 처리 시간 김

---

### 7. Contextual Retrieval (Anthropic 2024)

청크에 **컨텍스트 설명을 추가**하여 임베딩.

```
원본 청크: "환자 80%에서 반응률을 보였다."
컨텍스트 추가: "[이 논문은 폐암 환자에 대한 오시머티닙 치료 연구임] 환자 80%에서 반응률을 보였다."
```

**장점**: 컨텍스트 손실 문제 해결
**단점**: 전처리 비용 증가

---

### 8. Parent-Child Chunking (부모-자식) ⭐ Advanced

**핵심 아이디어**: 작은 청크로 검색 → 큰 청크(부모)를 LLM에 전달

```
┌─────────────────────────────────────────────────┐
│  Parent Chunk (2048 토큰)                        │
│  ┌───────────┬───────────┬───────────┬────────┐ │
│  │ Child 1   │ Child 2   │ Child 3   │ Child 4│ │
│  │ (512 토큰)│ (512 토큰)│ (512 토큰)│(512토큰)│ │
│  └───────────┴───────────┴───────────┴────────┘ │
└─────────────────────────────────────────────────┘

검색: Child 2 매칭 → 반환: Parent Chunk 전체
```

**왜 효과적인가?**
- **검색**: 작은 청크가 더 정밀 (특정 쿼리에 정확히 매칭)
- **생성**: 큰 청크가 더 풍부한 컨텍스트 제공
- 두 단계를 분리하여 각각 최적화

**구현 (LlamaIndex)**:
```python
from llama_index.core.node_parser import HierarchicalNodeParser

node_parser = HierarchicalNodeParser.from_defaults(
    chunk_sizes=[2048, 512, 128]  # 3단계 계층
)
```

**장점**: 검색 정밀도 + 풍부한 컨텍스트 동시 달성
**단점**: 저장 공간 증가 (여러 단계 저장), 구현 복잡도

---

### 9. Hierarchical Chunking (계층적)

문서의 **전체 구조를 트리로 보존**: 섹션 → 문단 → 문장

```
Document
├── Section 1 (Level 1)
│   ├── Paragraph 1.1 (Level 2)
│   │   ├── Sentence 1.1.1 (Level 3)
│   │   └── Sentence 1.1.2
│   └── Paragraph 1.2
└── Section 2
    └── ...
```

**검색 시 동작**:
- 문장 레벨 매칭 → 위로 확장하여 문단/섹션 컨텍스트 제공
- 섹션 레벨 매칭 → 아래로 드릴다운하여 관련 문장 찾기

**장점**: 정밀도(Precision)와 재현율(Recall) 모두 향상
**단점**: 구현 복잡, 인덱싱 오버헤드

---

### 10. Small-to-Big Retrieval (작은→큰)

Parent-Child의 변형. 두 가지 방식:

**방식 1: Child-to-Parent**
```
1. 작은 청크로 검색
2. 매칭된 청크의 parent_id 조회
3. 부모 청크 반환
```

**방식 2: Sentence Window**
```
1. 단일 문장으로 검색
2. 해당 문장 주변 N개 문장 윈도우 반환
```

```python
# LlamaIndex Sentence Window
from llama_index.core.node_parser import SentenceWindowNodeParser

parser = SentenceWindowNodeParser.from_defaults(
    window_size=3  # 앞뒤 3문장씩
)
```

---

### 11. Auto-Merging Retrieval (자동 병합)

여러 작은 청크가 검색되면 **자동으로 부모로 병합**.

```
검색 결과: Child 1, Child 2, Child 3 (같은 부모의 자식들)
         ↓ 과반수 이상이 관련 있으면
병합 결과: Parent Chunk 반환
```

**장점**: 작은 청크의 검색 효율 + 자동 컨텍스트 확장
**단점**: 병합 로직 구현 필요

---

### 12. Late Chunking (2024-2025 신규) ⭐ Hot

**핵심 아이디어**: 기존 방식의 순서를 뒤집음

```
기존 (Early Chunking):
  Document → [Chunk] → [Embed] → 각 청크별 임베딩

Late Chunking:
  Document → [Embed 전체] → [Chunk] → 토큰 임베딩을 청크로 분할 후 풀링
```

**왜 효과적인가?**
- 전체 문서 컨텍스트가 각 토큰 임베딩에 반영됨
- "Its more than 3.85 million inhabitants..."에서 "Its"가 무엇을 가리키는지 알 수 있음
- 추가 학습 없이 기존 임베딩 모델에 적용 가능

**구현**:
```python
# Jina AI late-chunking 예시
from transformers import AutoModel

model = AutoModel.from_pretrained('jinaai/jina-embeddings-v2-base-en')

# 1. 전체 문서 토큰화 & 임베딩
tokens = tokenizer(full_document, return_tensors='pt')
token_embeddings = model(**tokens).last_hidden_state

# 2. 청크 경계에서 분할 후 mean pooling
chunk_embeddings = [
    token_embeddings[start:end].mean(dim=0)
    for start, end in chunk_boundaries
]
```

**장점**: 컨텍스트 보존, 추가 학습 불필요
**단점**: Long-context 모델 필요, 메모리 사용량

> 💡 **vs Contextual Retrieval**: Late Chunking은 효율적이지만 관련성/완전성에서 약간 손해. Contextual Retrieval은 검색 에러 최대 49% 감소 (리랭킹 포함 시 67%)

---

### 13. Late Interaction (ColBERT 스타일)

Late Chunking과 유사하지만 **풀링 없이** 토큰 임베딩 직접 비교.

```
Query tokens:  [q1, q2, q3]
Document tokens: [d1, d2, d3, d4, d5, ...]

유사도 = MaxSim(qi, dj) for all i, j
```

**장점**: 가장 정확한 관련성 점수
**단점**: 검색 시 계산 비용 높음 (토큰 수 × 토큰 수)

---

### 14. Proposition-Based Chunking

문서를 **독립적인 명제(proposition)** 단위로 분할.

```
원본: "베를린은 독일의 수도이다. 인구는 385만명이다."

명제 분할:
- "베를린은 독일의 수도이다."
- "베를린의 인구는 385만명이다." (대명사 해소)
```

**장점**: 각 청크가 자체 완결적, 검색 정밀도 높음
**단점**: LLM 전처리 필요, 비용 높음

---

### 15. Neural Chunking (학습 기반)

**신경망으로 최적 청크 경계를 학습**.

- 규칙 기반보다 의미적 일관성과 청크 길이 밸런스 우수
- ACL 2025: "Recursive Semantic Chunking (RSC)"이 기존 방식 대비 우수한 성능

**장점**: 데이터 기반 최적화
**단점**: 학습 데이터 필요, 도메인 특화 어려움

---

## 전략별 비교

| 전략 | 정확도 | 속도 | 비용 | 구현 난이도 | 권장 상황 |
|------|--------|------|------|------------|----------|
| Fixed-Size | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | 쉬움 | 프로토타입, 단순 문서 |
| **Recursive** | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | 쉬움 | **대부분의 경우 (기본값)** |
| Semantic | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐ | 보통 | 고품질 검색 필요 시 |
| Structure-Based | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | 보통 | HTML, Markdown 문서 |
| Page-Level | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | 쉬움 | PDF 문서 |
| Agentic | ⭐⭐⭐⭐⭐ | ⭐ | ⭐ | 어려움 | 정밀도 최우선 |
| **Parent-Child** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | 보통 | **구조화된 긴 문서** |
| Hierarchical | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | 어려움 | 계층 구조 문서 |
| **Late Chunking** | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | 보통 | **컨텍스트 손실 방지** |
| Contextual | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐ | 보통 | 최고 품질 필요 시 |

---

## 청크 크기 가이드라인

### 권장 크기

| 임베딩 모델 | 권장 청크 크기 |
|------------|---------------|
| OpenAI text-embedding-ada-002 | 400-512 토큰 |
| OpenAI text-embedding-3-small | 512-1024 토큰 |
| BGE, E5 (오픈소스) | 256-512 토큰 |

### 오버랩

- **권장**: 청크 크기의 **10-20%**
- 예: 500 토큰 청크 → 50-100 토큰 오버랩

### 쿼리 유형별

| 쿼리 유형 | 청크 크기 |
|----------|----------|
| 사실 기반 (Factual) | 작은 청크 (200-400 토큰) |
| 분석적 (Analytical) | 큰 청크 (500-1000 토큰) |
| 다중 개념 (Multi-concept) | 관련 데이터 그룹핑 |

---

## 콘텐츠 유형별 권장 전략

| 콘텐츠 유형 | 권장 전략 |
|------------|----------|
| 구조화된 텍스트 (리포트, 논문) | Semantic / Recursive |
| 코드, 기술 문서 | Recursive (언어별 분할) |
| 혼합/비구조화 콘텐츠 | AI 기반 또는 Contextual |
| 대규모 시스템 | Recursive + Subdocument |

---

## 베스트 프랙티스

### 1. 실험하라

> "청킹 전략이나 크기를 하드코딩하지 마라. 다양한 전략으로 실험하고 메트릭으로 평가하라."

### 2. 작은 청크부터 시작

- 큰 청크는 컨텍스트가 많지만 검색 정밀도 저하
- 작은 청크부터 시작해서 최적점 찾기

### 3. 메타데이터 활용

청크에 메타데이터 포함:
- 문서 제목, 섹션명
- 위치 정보 (offset)
- 버전 정보

### 4. 평가 메트릭

- **Recall**: 관련 청크를 얼마나 찾았나
- **Precision**: 찾은 청크 중 관련된 것의 비율
- **MRR (Mean Reciprocal Rank)**: 첫 번째 관련 결과의 순위

---

## 참고 자료

- [Databricks - The Ultimate Guide to Chunking Strategies](https://community.databricks.com/t5/technical-blog/the-ultimate-guide-to-chunking-strategies-for-rag-applications/ba-p/113089)
- [Stack Overflow - Breaking up is hard to do: Chunking in RAG](https://stackoverflow.blog/2024/12/27/breaking-up-is-hard-to-do-chunking-in-rag-applications/)
- [Firecrawl - Best Chunking Strategies for RAG 2025](https://www.firecrawl.dev/blog/best-chunking-strategies-rag-2025)
- [Weaviate - Chunking Strategies for RAG](https://weaviate.io/blog/chunking-strategies-for-rag)
- [Unstructured - Chunking for RAG Best Practices](https://unstructured.io/blog/chunking-for-rag-best-practices)
- [Pinecone - Chunking Strategies for LLM Applications](https://www.pinecone.io/learn/chunking-strategies/)
- [LangChain - Text Splitters](https://docs.langchain.com/oss/python/integrations/splitters)
- [LanceDB - Chunking Techniques with LangChain and LlamaIndex](https://blog.lancedb.com/chunking-techniques-with-langchain-and-llamaindex/)
