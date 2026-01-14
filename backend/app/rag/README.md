# RAG 모듈 개발 가이드

> **이 문서는 Claude Code가 RAG 컴포넌트를 추가/수정할 때 참고하는 가이드입니다.**
>
> **⚠️ 중요**: 전략 추가 전에 아래 "역할 분리" 섹션을 반드시 확인하세요!

---

## 🔴 필독: 역할 분리 (검색 vs 인덱싱)

RAG 전략은 **사용 시점**에 따라 두 곳에서 관리됩니다:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          RAG 전략 관리 구조                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  검색 시점 (User Backend)              인덱싱 시점 (Batch)                    │
│  ─────────────────────────            ────────────────────────               │
│  backend/app/rag/                     batch/src/rag/                         │
│  ├── retrievers/  ✅                  ├── chunkers/  ✅                      │
│  ├── rerankers/   ✅                  └── embedders/ ✅                      │
│  ├── classifiers/ ✅                                                         │
│  └── evaluators/  ✅                                                         │
│                                                                              │
│  사용: 쿼리 요청 시                    사용: 논문 수집/임베딩 시                │
│  실행: FastAPI (동기/비동기)           실행: Celery Worker (비동기)            │
│                                                                              │
│  ⚠️ chunkers/, embedders/는           📌 실제 청킹/임베딩 구현은              │
│     참조/호환성 용도로만 유지            Batch에서만 수행                       │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 어디에 추가해야 하나요?

| 추가할 전략        | 추가 위치                      | 설명                     |
| ------------------ | ------------------------------ | ------------------------ |
| **새 청킹 전략**   | `batch/src/rag/chunkers/`      | 논문 인덱싱 시 사용      |
| **새 임베딩 모델** | `batch/src/rag/embedders/`     | 논문 인덱싱 시 사용      |
| **새 검색 전략**   | `backend/app/rag/retrievers/`  | 쿼리 검색 시 사용        |
| **새 리랭킹 모델** | `backend/app/rag/rerankers/`   | 검색 결과 재정렬 시 사용 |
| **새 분류기**      | `backend/app/rag/classifiers/` | 도메인 분류 시 사용      |
| **새 평가기**      | `backend/app/rag/evaluators/`  | 품질 평가 시 사용        |
| **새 NER 분류기**  | `backend/app/rag/classifiers/` | 엔티티 추출 시 사용      |

---

## 협업 시 주의사항

### 1. 전략 이름 네이밍 컨벤션 (필수!)

**일반적인 이름 사용 금지**. 전략 이름은 구체적이고 고유해야 합니다.

```python
# ❌ 잘못된 예 - 충돌 가능성 높음
name = "semantic"
name = "chunker"
name = "default"

# ✅ 올바른 예 - 구체적인 설명 포함
name = "semantic_section_700t"     # 섹션 기반, 700토큰
name = "fixed_char_1000_200"       # 문자 기준, 1000자, 200 오버랩
name = "hybrid_vector70_bm25_30"   # 벡터 70%, BM25 30%
```

**네이밍 패턴**:

```
{방식}_{주요특성}_{파라미터}

예시:
- semantic_section_700t      (의미 기반 + 섹션 단위 + 700토큰)
- fixed_char_1000_200        (고정 크기 + 문자 단위 + 1000자 + 200 오버랩)
- bge_reranker_v2_m3         (BGE + 리랭커 + v2-m3 모델)
```

### 2. DB 동기화 필수

전략 이름을 변경하면 **반드시** 데이터베이스 `rag_settings` 테이블도 업데이트해야 합니다.

```sql
-- 전략 이름 변경 시 DB도 함께 업데이트
UPDATE rag_settings SET chunker = 'semantic_section_700t' WHERE chunker = 'semantic';
```

### 3. Backend/Batch 이름 동기화

인덱싱 전략(chunker, embedder)의 이름은 **Backend와 Batch 모두 동일**해야 합니다.
Admin UI에서 이름으로 선택 → Batch에서 같은 이름으로 실행

```
Admin UI (Backend에서 목록 조회) → "fixed_char_1000_200" 선택
                                          ↓
Batch Celery (실행) → get_chunker("fixed_char_1000_200") 로드
```

---

## 시스템 구조 이해

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  Admin Frontend (Next.js :3001)                                              │
│       │                                                                      │
│       ├─ GET /lab/strategies ──────────────┐                                │
│       │                                     ↓                               │
│       │                              User Backend                           │
│       │                              (검색 전략 목록)                         │
│       │                                                                      │
│       ├─ GET /lab/indexing-strategies ─────┐                                │
│       │                                     ↓                               │
│       │                              User Backend                           │
│       │                                     ↓                               │
│       │                              Batch API                              │
│       │                              (인덱싱 전략 목록)                       │
│       │                                                                      │
│       └─ POST /sample-embeddings ──────────┐                                │
│                                             ↓                               │
│                                      Admin Backend                          │
│                                             ↓                               │
│                                      User Backend                           │
│                                             ↓ (Celery 트리거)               │
│                                      Batch Worker                           │
│                                      (실제 청킹/임베딩)                       │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 디렉토리 구조

### Backend RAG (검색 시점)

```
backend/app/rag/
├── README.md              # 이 파일 (Claude Code 가이드)
├── __init__.py            # 모듈 초기화 및 레지스트리 export
├── registry.py            # 전략 레지스트리 시스템
├── base.py                # 공통 타입 정의
│
├── retrievers/            # 검색 전략 ✅ 여기에 추가
│   ├── __init__.py
│   ├── base.py            # RetrieverProtocol
│   ├── hybrid.py          # 하이브리드 검색 (현재 기본)
│   └── dense.py           # Dense 검색만
│
├── rerankers/             # 리랭킹 모델 ✅ 여기에 추가
│   ├── __init__.py
│   ├── base.py            # RerankerProtocol
│   ├── bge.py             # BGE Reranker (현재 기본)
│   ├── cohere.py          # Cohere Reranker
│   └── none.py            # 리랭킹 없음
│
├── classifiers/           # 도메인 분류기 ✅ 여기에 추가
│   ├── __init__.py
│   ├── base.py            # ClassifierProtocol
│   ├── llm.py             # LLM 기반 분류
│   └── ml.py              # ML 모델 기반 분류
│
├── evaluators/            # 품질 평가 ✅ 여기에 추가
│   ├── __init__.py
│   ├── base.py            # EvaluatorProtocol
│   └── ragas.py           # RAGAS 평가
│
├── chunkers/              # ⚠️ 참조용 - 실제 구현은 Batch에
│   └── ...
│
└── embedders/             # ⚠️ 참조용 - 실제 구현은 Batch에
    └── ...
```

### Batch RAG (인덱싱 시점)

```
batch/src/rag/
├── __init__.py            # 모듈 export
├── registry.py            # 전략 레지스트리
├── base.py                # 공통 타입
│
├── chunkers/              # 청킹 전략 ✅ 여기에 추가
│   ├── __init__.py
│   ├── base.py            # ChunkerProtocol
│   ├── fixed_char.py      # 고정 크기 문자 청킹
│   ├── semantic.py        # 의미 기반 청킹
│   └── section_based.py   # 섹션 기반 청킹
│
└── embedders/             # 임베딩 모델 ✅ 여기에 추가
    ├── __init__.py
    ├── base.py            # EmbedderProtocol
    └── openai.py          # OpenAI text-embedding-3
```

---

## 새 컴포넌트 추가 방법

### 검색 전략 추가 (Retriever, Reranker)

> **추가 위치**: `backend/app/rag/`

#### 1. Protocol 확인

각 컴포넌트 디렉토리의 `base.py`에서 Protocol을 확인합니다.

```python
# 예: rerankers/base.py
from typing import Protocol
from dataclasses import dataclass

@dataclass
class RerankResult:
    document: dict
    score: float
    original_rank: int

class RerankerProtocol(Protocol):
    """리랭킹 전략 인터페이스"""

    name: str  # 레지스트리 등록 이름 (필수)

    def rerank(self, query: str, documents: list[dict], top_k: int = 10) -> list[RerankResult]:
        """문서 재정렬"""
        ...

    def get_config(self) -> dict:
        """현재 설정 반환"""
        ...
```

#### 2. 구현체 작성

> **⚠️ 필수 규칙**:
>
> 1. **name**: 구체적이고 고유한 이름 사용 (위 네이밍 컨벤션 참고)
> 2. **docstring**: Admin Lab UI "설명" 모달에 표시됨. 반드시 작성!
> 3. **첫 줄**: 한 줄 요약 (제목으로 사용됨)
> 4. **본문**: 동작 방식, 파라미터 설명, 적합한 사용 사례

```python
# 예: rerankers/cohere.py
from app.rag.rerankers.base import RerankerProtocol, RerankResult
from app.rag.registry import register_reranker

@register_reranker  # 데코레이터로 자동 등록
class CohereReranker:
    """Cohere Rerank API 기반 리랭커

    Cohere의 rerank-english-v3.0 모델을 사용합니다.
    API 기반으로 빠르고 정확하지만 유료입니다.

    파라미터:
    - model: rerank-english-v3.0
    - top_n: 반환할 결과 수
    """  # ← 이 docstring이 Admin Lab "설명" 모달에 표시됨

    name = "cohere_rerank_v3"  # ⚠️ 구체적인 이름 필수!

    def __init__(self, model: str = "rerank-english-v3.0"):
        self.model = model

    def rerank(self, query: str, documents: list[dict], top_k: int = 10) -> list[RerankResult]:
        # 구현...
        pass

    def get_config(self) -> dict:
        return {"name": self.name, "model": self.model}
```

#### 3. **init**.py에서 import

```python
# rerankers/__init__.py
from .bge import BGEReranker
from .cohere import CohereReranker  # 새로 추가

__all__ = ["BGEReranker", "CohereReranker"]
```

### 인덱싱 전략 추가 (Chunker, Embedder)

> **추가 위치**: `batch/src/rag/`
>
> **참고 문서**: `batch/src/rag/README.md` (별도)

인덱싱 전략은 Batch 모듈에서 관리됩니다. 자세한 내용은 Batch RAG README를 참고하세요.

---

## 레지스트리 시스템

### 데코레이터 종류

| 데코레이터             | 용도               | 위치      |
| ---------------------- | ------------------ | --------- |
| `@register_retriever`  | 검색 전략 등록     | Backend   |
| `@register_reranker`   | 리랭킹 모델 등록   | Backend   |
| `@register_classifier` | 도메인 분류기 등록 | Backend   |
| `@register_evaluator`  | 품질 평가기 등록   | Backend   |
| `@register_chunker`    | 청킹 전략 등록     | **Batch** |
| `@register_embedder`   | 임베딩 모델 등록   | **Batch** |

### 조회 함수 (Backend)

```python
from app.rag import (
    # 리트리버
    get_retriever,
    list_retrievers,

    # 리랭커
    get_reranker,
    list_rerankers,

    # 분류기
    get_classifier,
    list_classifiers,

    # 평가기
    get_evaluator,
    list_evaluators,
)
```

---

## Admin Lab 연동

### API 엔드포인트

```
GET  /api/lab/strategies              # 검색 전략 목록 (retriever, reranker)
GET  /api/lab/indexing-strategies     # 인덱싱 전략 목록 (chunker, embedder)
POST /api/lab/test/search             # 검색 테스트
POST /api/lab/test/generate           # 답변 생성 테스트
POST /api/lab/test/compare            # A/B 비교 테스트
```

### 테스트 요청 예시

```json
{
  "query": "EGFR 변이 폐암 치료제",
  "strategies": {
    "reranker": "bge_reranker_v2_m3",
    "retriever": "hybrid_vector70_bm25"
  },
  "parameters": {
    "limit": 10,
    "alpha": 0.7,
    "use_reranker": true
  }
}
```

---

## Gate 시스템 (품질 관문)

OARIA는 RAG 품질을 보장하기 위해 3개의 Gate를 거칩니다:

### Gate 개요

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           OARIA Gate 시스템                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  사용자 질문                                                                  │
│       ↓                                                                      │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  Gate 1: Domain Classifier (OAR-10) ✅                               │    │
│  │  ──────────────────────────────────────                              │    │
│  │  종양학(Oncology) 도메인 여부 분류                                     │    │
│  │  - 종양학 ✓ → 검색 진행                                               │    │
│  │  - Off-domain → 경고 메시지와 함께 답변 생성                           │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│       ↓                                                                      │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  Gate 2: Retrieval Confidence (OAR-12) 🔜                            │    │
│  │  ──────────────────────────────────────                              │    │
│  │  검색 결과 신뢰도 검증                                                 │    │
│  │  - 신뢰도 높음 → LLM 답변 생성                                        │    │
│  │  - 신뢰도 낮음 → "관련 논문을 찾지 못했습니다" 메시지                    │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│       ↓                                                                      │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  Gate 3: RAGAS Quality (OAR-13) 🔜                                   │    │
│  │  ──────────────────────────────────────                              │    │
│  │  생성된 답변 품질 평가 (RAGAS)                                         │    │
│  │  - 품질 점수 로깅                                                     │    │
│  │  - 낮은 품질 답변 피드백 수집                                          │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│       ↓                                                                      │
│  최종 답변 반환                                                              │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Gate 1: Domain Classifier (OAR-10)

현재 구현된 분류기:

| 분류기       | 설명                        | 모델                                 |
| ------------ | --------------------------- | ------------------------------------ |
| `pubmedbert` | PubMedBERT 기반 도메인 분류 | Zero-shot (facebook/bart-large-mnli) |

**Lab에서 테스트 방법**:

1. Admin Lab → RAG 전략 선택 → Classifier 드롭다운에서 `pubmedbert` 선택
2. 쿼리 입력 후 Search 또는 Generate 실행
3. 결과에서 `classification` 필드 확인

```json
// 응답 예시
{
  "classification": {
    "category": "oncology",
    "confidence": 0.92,
    "isOncology": true,
    "warning": null,
    "classifierLatencyMs": 45
  }
}
```

**Off-domain 쿼리 예시**:

- "심근경색 응급 처치" → cardiology
- "당뇨병 인슐린 치료" → endocrinology
- "우울증 약물 치료" → psychiatry

### Gate 테스트 API

```bash
# 분류기 개별 테스트
curl -X POST http://localhost:8000/api/classify \
  -H "Content-Type: application/json" \
  -d '{"query": "폐암 환자의 면역항암제 치료"}'

# Lab 통합 테스트 (classifier 포함)
curl -X POST http://localhost:8000/api/lab/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "폐암 환자의 면역항암제 치료",
    "classifier": "pubmedbert"
  }'
```

---

## NER Classifiers (Entity Extraction)

Bio-Entity 추출을 위한 전용 NER 분류기입니다. (Gate 1 도메인 분류와는 별도)

| 분류기          | 설명          | 엔티티                  | 모델                           |
| --------------- | ------------- | ----------------------- | ------------------------------ |
| `bc5cdr_ner_v1` | BC5CDR 기반   | Chemical, Disease       | `vparka/cancer-ner-pubmedbert` |
| `multiner_v1`   | MultiNER 기반 | Disease, Chemical, Gene | `vparka/pubmedbert-multiner`   |

> **MultiNER 구성**:
>
> - **BC5CDR** (Chemical, Disease)
> - **NCBI-Disease** (Disease)
> - **JNLPBA** (DNA, RNA, Protein → **Gene**으로 통합)
> - 위 3개 데이터셋을 정규화 및 병합하여 학습

**사용법**:

```python
from app.rag import get_classifier

# BC5CDR (Chemical, Disease)
ner = get_classifier("bc5cdr_ner_v1")
result = ner.extract("Cisplatin treats lung cancer.")
# result.entities -> [NEREntity(text="Cisplatin", label="Chemical"), ...]

# MultiNER (Disease, Chemical, Gene)
ner = get_classifier("multiner_v1")
result = ner.extract("EGFR mutation")
# result.entities -> [NEREntity(text="EGFR", label="Gene"), ...]
```

---

## 기존 서비스와의 관계

현재 `app/services/`의 서비스들은 RAG 모듈로 래핑됩니다:

| 기존 서비스        | RAG 모듈 위치          | 등록 이름                |
| ------------------ | ---------------------- | ------------------------ |
| `reranker_service` | `rerankers/bge.py`     | `"bge_reranker_v2_m3"`   |
| `weaviate_service` | `retrievers/hybrid.py` | `"hybrid_vector70_bm25"` |

---

## 컴포넌트별 구현 가이드

### Retriever (검색 전략)

**입력**: 쿼리 벡터 + 검색 파라미터
**출력**: 검색 결과 리스트

| 전략     | 설명             | 적합한 경우    |
| -------- | ---------------- | -------------- |
| `hybrid` | 벡터 + BM25 결합 | 일반적인 경우  |
| `dense`  | 벡터 검색만      | 의미 검색 중심 |

### Reranker (리랭킹 모델)

**입력**: 쿼리 + 검색 결과
**출력**: 재정렬된 결과 + 점수

| 모델                 | 크기 | 특징                     |
| -------------------- | ---- | ------------------------ |
| `bge_reranker_v2_m3` | 567M | 다국어, 로컬, 무료       |
| `cohere_rerank_v3`   | -    | API, 빠름, 유료          |
| `none`               | -    | 리랭킹 없음 (벤치마크용) |

---

## 테스트 방법

```bash
# 단위 테스트
cd backend
uv run pytest tests/rag/ -v

# 특정 컴포넌트 테스트
uv run pytest tests/rag/test_rerankers.py -v
```

---

## 체크리스트: 검색 전략 추가 시

- [ ] Protocol 인터페이스 준수 확인
- [ ] `@register_*` 데코레이터 추가
- [ ] **`name` 속성 정의** - 구체적이고 고유한 이름 사용
- [ ] **클래스 docstring 작성** - Admin Lab "설명" 모달에 표시
- [ ] `__init__.py`에서 import
- [ ] `get_config()` 메서드 구현
- [ ] **DB rag_settings 업데이트** - 필요 시
- [ ] 단위 테스트 작성
- [ ] 이 README에 설명 추가

## 체크리스트: 인덱싱 전략 추가 시

- [ ] **Batch에 추가** - `batch/src/rag/chunkers/` 또는 `embedders/`
- [ ] **Backend에 참조 추가** (선택) - Admin UI 호환성 용
- [ ] **전략 이름 동기화** - Backend와 Batch 동일 이름
- [ ] `batch/src/rag/README.md` 참고

---

## 트러블슈팅

### "설명이 없습니다" 표시

**원인**: DB의 전략 이름과 코드의 `name` 속성이 불일치

```
DB: reranker = "bge"
코드: name = "bge_reranker_v2_m3"  ← 불일치!
```

**해결**:

1. DB 업데이트: `UPDATE rag_settings SET reranker = 'bge_reranker_v2_m3'`
2. 또는 코드의 name을 DB와 일치시키기

### Admin Lab에서 전략 목록이 안 보임

**확인 사항**:

1. User Backend `/lab/strategies` 엔드포인트 존재 확인
2. Admin Backend `lab.controller.ts`에 프록시 메서드 존재 확인
3. Admin Backend `lab.service.ts`에 User Backend 호출 로직 존재 확인

### 샘플 임베딩이 pending 상태로 유지됨

**원인**: User Backend에서 Celery 트리거 실패

**확인 사항**:

1. User Backend에 `celery` 패키지 설치 확인
2. Redis 연결 확인
3. Batch Celery 워커 실행 확인

---

## 참고 문서

- [Batch RAG 모듈 가이드](../../../batch/src/rag/README.md) - 인덱싱 전략 추가
- [RAG 품질 개선 전략](../../docs/admin/rag-quality-improvement.md)
- [검색 전략 설계](../../docs/backend/retrieval-strategy.md)
- [작업 히스토리: batch-09-260108](../../docs/history/batch-09-260108.md) - 아키텍처 분리 설계
