# Batch RAG 모듈

> **인덱싱 시점** 전략을 관리합니다 (청킹, 임베딩)
>
> 검색 시점 전략 (리트리버, 리랭커)는 `backend/app/rag/` 참고

---

## 구조

```
batch/src/rag/
├── __init__.py          # 모듈 진입점
├── registry.py          # Strategy Registry (자동 등록)
├── base.py              # 공통 타입 (Chunk, ChunkingResult)
├── README.md            # 이 문서
│
├── chunkers/            # 청킹 전략
│   ├── __init__.py
│   ├── base.py          # ChunkerProtocol
│   ├── fixed_char.py    # FixedCharChunker
│   └── semantic.py      # SemanticSectionChunker
│
└── embedders/           # 임베딩 전략
    ├── __init__.py
    ├── base.py          # EmbedderProtocol
    └── openai.py        # OpenAI Embedders
```

---

## 사용법

```python
from src.rag import get_chunker, get_embedder, list_chunkers, list_embedders

# 등록된 전략 목록 조회
print(list_chunkers())   # ['fixed_char_1000_200', 'semantic_section_700t']
print(list_embedders())  # ['openai_3small', 'openai_3large']

# 청커 사용
chunker = get_chunker('semantic_section_700t')
result = chunker.chunk(
    fulltext=paper_fulltext,
    sections=sections,
    paper_id="pmid:12345678",
    title="Paper Title",
    year=2024,
)

for chunk in result.chunks:
    print(chunk.chunk_id, chunk.text[:100])

# 임베더 사용
embedder = get_embedder('openai_3small')
texts = [c.embedding_text for c in result.chunks]
vectors = embedder.embed_batch(texts)
```

---

## 새 청킹 전략 추가하기

### 1. 파일 생성

`batch/src/rag/chunkers/my_chunker.py`:

```python
from typing import Any
from ..registry import register_chunker
from ..base import Chunk, ChunkingResult, Section


@register_chunker  # ← 데코레이터 필수!
class MyChunker:
    """내 커스텀 청커 (Admin Lab UI에 표시되는 설명)

    여기에 청커의 특징, 장단점, 파라미터 등을 설명합니다.
    이 docstring이 Admin Lab UI에 표시됩니다.

    파라미터:
    - chunk_size: 1000자
    - overlap: 200자
    """

    name = "my_chunker_v1"  # ← 고유한 이름 필수!

    def __init__(self, chunk_size: int = 1000):
        self.chunk_size = chunk_size

    def chunk(
        self,
        fulltext: str,
        sections: list[dict],
        paper_id: str,
        title: str,
        year: int | None = None,
    ) -> ChunkingResult:
        """논문 전체를 청킹"""
        # 청킹 로직 구현
        ...
        return ChunkingResult(...)

    def get_config(self) -> dict[str, Any]:
        """현재 설정 반환"""
        return {
            "name": self.name,
            "chunk_size": self.chunk_size,
        }
```

### 2. __init__.py에 import 추가

`batch/src/rag/chunkers/__init__.py`:

```python
from .fixed_char import FixedCharChunker
from .semantic import SemanticSectionChunker
from .my_chunker import MyChunker  # ← 추가

__all__ = [
    "FixedCharChunker",
    "SemanticSectionChunker",
    "MyChunker",  # ← 추가
]
```

### 3. 확인

```python
from src.rag import list_chunkers, get_chunker_info

print(list_chunkers())  # [..., 'my_chunker_v1']
print(get_chunker_info('my_chunker_v1'))
# {
#   'name': 'my_chunker_v1',
#   'docstring': '내 커스텀 청커...',
#   'class': 'MyChunker',
#   'module': 'src.rag.chunkers.my_chunker'
# }
```

---

## 새 임베딩 전략 추가하기

### 1. 파일 생성

`batch/src/rag/embedders/my_embedder.py`:

```python
from typing import Any
from ..registry import register_embedder


@register_embedder  # ← 데코레이터 필수!
class MyEmbedder:
    """내 커스텀 임베더 (Admin Lab UI에 표시되는 설명)

    파라미터:
    - model: my-embedding-model
    - dimension: 768
    """

    name = "my_embedder_v1"  # ← 고유한 이름 필수!
    dimension = 768  # ← 임베딩 차원 필수!

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key

    def embed(self, text: str) -> list[float]:
        """단일 텍스트 임베딩"""
        # 임베딩 로직 구현
        return [0.0] * self.dimension

    def embed_batch(
        self,
        texts: list[str],
        batch_size: int = 100,
    ) -> list[list[float]]:
        """배치 텍스트 임베딩"""
        return [self.embed(t) for t in texts]

    def get_config(self) -> dict[str, Any]:
        """현재 설정 반환"""
        return {
            "name": self.name,
            "dimension": self.dimension,
        }
```

### 2. __init__.py에 import 추가

`batch/src/rag/embedders/__init__.py`:

```python
from .openai import OpenAISmallEmbedder, OpenAILargeEmbedder
from .my_embedder import MyEmbedder  # ← 추가

__all__ = [
    "OpenAISmallEmbedder",
    "OpenAILargeEmbedder",
    "MyEmbedder",  # ← 추가
]
```

---

## 현재 등록된 전략들

### 청커 (Chunkers)

| Name | 설명 | 파라미터 |
|------|------|----------|
| `fixed_char_1000_200` | 고정 크기 문자 기반 (baseline) | chunk_size=1000, overlap=200 |
| `semantic_section_700t` | 섹션 기반 시맨틱 (Recursive) | chunk_size_tokens=700, overlap_tokens=100 |

### 임베더 (Embedders)

| Name | 모델 | 차원 | 비용 |
|------|------|------|------|
| `openai_3small` | text-embedding-3-small | 1536 | $0.02/1M tokens |
| `openai_3large` | text-embedding-3-large | 3072 | $0.13/1M tokens |

---

## 주의사항

1. **name 속성은 필수이며 고유해야 합니다**
   - 중복 name은 등록 시 에러 발생

2. **데코레이터 `@register_chunker` 또는 `@register_embedder` 필수**
   - 이 데코레이터가 있어야 레지스트리에 자동 등록됨

3. **__init__.py에 import 추가 필수**
   - import되어야 데코레이터가 실행됨

4. **클래스 docstring은 Admin Lab UI에 표시됨**
   - 사용자가 전략을 선택할 때 참고하는 정보
   - 파라미터, 장단점, 사용 케이스 등을 명시

5. **임베더는 dimension 속성 필수**
   - Weaviate 스키마 생성 시 필요

---

## 역할 분리

```
검색 시점 (User Backend)              인덱싱 시점 (Batch)
backend/app/rag/                     batch/src/rag/
├── retrievers/  ✅                  ├── chunkers/  ✅
└── rerankers/   ✅                  └── embedders/ ✅
```

- **User Backend**: 검색 요청이 올 때 실시간으로 작동
  - Retriever: 벡터 검색 전략
  - Reranker: 검색 결과 재정렬

- **Batch**: Celery 워커에서 비동기로 작동
  - Chunker: 논문 → 청크 분할
  - Embedder: 청크 → 벡터 변환

---

## 관련 문서

- `backend/app/rag/README.md` - 검색 시점 전략 (리트리버, 리랭커)
- `docs/history/batch-09-260108.md` - 아키텍처 설계 히스토리
