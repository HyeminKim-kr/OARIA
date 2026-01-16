# F-05: Retrieval Confidence (Gate 2) Implementation

> **Epic**: OAR-12
> **Status**: Done
> **Implemented**: 2026-01-14
> **Author**: Hyemin Kim

---

## Overview

Gate 2 validates the quality of RAG search results before generating answers. It ensures that:
1. Retrieved documents are sufficiently relevant to the query
2. Enough evidence documents exist to support an answer
3. Documents are within the oncology domain

This prevents the system from generating answers based on low-quality or irrelevant search results.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Agent Workflow                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   Query → Complexity Analysis → Task Decomposition               │
│                                      ↓                           │
│                              ┌───────────────┐                   │
│                              │  RAG Search   │                   │
│                              └───────┬───────┘                   │
│                                      ↓                           │
│                         ┌────────────────────────┐               │
│                         │   ★ GATE 2 ★          │               │
│                         │  Retrieval Confidence  │               │
│                         └────────────┬───────────┘               │
│                                      ↓                           │
│                    ┌─────────────────┴─────────────────┐         │
│                    │                                   │         │
│               [PASSED]                            [FAILED]       │
│                    ↓                                   ↓         │
│             ┌──────────┐                    Return Error Message │
│             │Synthesize│                                         │
│             └──────────┘                                         │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Validation Rules

### OAR-37: Similarity Threshold
| Item | Value |
|------|-------|
| **Condition** | `max(similarity) >= 0.7` |
| **Purpose** | Ensure at least one highly relevant document exists |
| **Failure Message** | "관련 논문을 충분히 찾지 못했습니다. 질문을 더 구체적으로 해주세요." |

### OAR-38: Min Relevant Docs
| Item | Value |
|------|-------|
| **Condition** | `count(similarity >= 0.6) >= 3` |
| **Purpose** | Ensure sufficient evidence for a well-supported answer |
| **Failure Message** | "충분한 근거 논문을 찾지 못했습니다." |

### OAR-39: Domain Validation
| Item | Value |
|------|-------|
| **Condition** | `oncology_ratio >= 0.8` (80%) |
| **Purpose** | Ensure documents are within oncology domain |
| **Failure Message** | "검색 결과가 암 연구와 관련성이 낮습니다." |
| **Method** | Keyword matching in title and snippet |

**Oncology Keywords:**
```python
ONCOLOGY_KEYWORDS = [
    "cancer", "tumor", "tumour", "oncology", "carcinoma", "melanoma",
    "leukemia", "lymphoma", "sarcoma", "neoplasm", "malignant",
    "metastasis", "chemotherapy", "immunotherapy", "radiotherapy",
    "oncogene", "EGFR", "HER2", "BRCA", "PD-1", "PD-L1",
    "암", "종양", "항암", "전이", "악성"
]
```

---

## File Structure

```
backend/app/services/gates/
├── __init__.py              # Package exports
└── gate2_retrieval.py       # Gate 2 implementation
```

---

## API Reference

### Gate2Service

```python
from app.services.gates import gate2_service, Gate2Result

# Validate search results
result: Gate2Result = gate2_service.validate(references)

if result.passed:
    # Proceed to synthesis
    pass
else:
    # Handle failure
    print(f"Gate 2 failed: {result.reason}")
    print(f"Message: {result.message}")
```

### Gate2Result

```python
@dataclass
class Gate2Result:
    passed: bool                      # Whether validation passed
    reason: Gate2FailReason | None    # Failure reason (if failed)
    message: str | None               # User-facing message (if failed)
    max_similarity: float             # Highest similarity score
    relevant_count: int               # Count of docs with score >= 0.6
    oncology_ratio: float             # Ratio of oncology documents
    details: dict | None              # Additional validation details
```

### Gate2FailReason

```python
class Gate2FailReason(str, Enum):
    LOW_SIMILARITY = "low_similarity"
    INSUFFICIENT_DOCS = "insufficient_docs"
    DOMAIN_MISMATCH = "domain_mismatch"
```

---

## Integration Points

### 1. Executor Node (`executor.py`)

Gate 2 is called after RAG search in two places:

**a) Single RAG task execution:**
```python
def _execute_rag_search(task: SubTask) -> TaskResult:
    retrieval_result = rag_service.retrieve(task.query)

    # Gate 2 validation
    gate2_result = gate2_service.validate(retrieval_result.references)

    if not gate2_result.passed:
        return TaskResult(
            task_id=task.id,
            content=gate2_result.message,
            references=retrieval_result.references,
            gate2_passed=False,
            gate2_reason=gate2_result.reason.value,
        )

    return TaskResult(...)
```

**b) Direct RAG for simple queries:**
```python
def execute_direct_rag(state: AgentState) -> AgentState:
    retrieval_result = rag_service.retrieve(query)

    # Gate 2 validation
    gate2_result = gate2_service.validate(retrieval_result.references)

    if not gate2_result.passed:
        # Return early with error
        ...
```

### 2. Synthesizer Node (`synthesizer.py`)

Checks for Gate 2 failures before generating answer:

```python
def synthesize_answer(state: AgentState) -> AgentState:
    # Check for Gate 2 failures
    gate2_failure = _check_gate2_failures(task_results)
    if gate2_failure:
        return {
            "final_answer": gate2_failure,
            "citations": [],
        }

    # Proceed with synthesis...
```

---

## Configuration

Thresholds can be customized when instantiating the service:

```python
from app.services.gates.gate2_retrieval import Gate2Service

# Custom thresholds
custom_gate2 = Gate2Service(
    similarity_threshold=0.75,  # Stricter similarity
    relevant_score=0.65,        # Higher relevance bar
    min_relevant_docs=5,        # Require more docs
    domain_ratio=0.9,           # Stricter domain check
)
```

Default values:
- `similarity_threshold`: 0.7
- `relevant_score`: 0.6
- `min_relevant_docs`: 3
- `domain_ratio`: 0.8

---

## Logging

Gate 2 logs validation results for monitoring:

```
INFO  - Gate 2 PASSED: similarity=0.85, relevant_docs=5, oncology_ratio=100%
WARN  - Gate 2 FAILED: Low similarity. max=0.45, threshold=0.7
WARN  - Gate 2 FAILED: Insufficient docs. count=2, min=3
WARN  - Gate 2 FAILED: Domain mismatch. ratio=60%, threshold=80%
```

---

## Testing

### Unit Test Example

```python
from app.services.gates import gate2_service
from app.schemas.chat import Reference

def test_gate2_passes_with_good_results():
    refs = [
        Reference(paper_id="1", chunk_id="1", title="EGFR Cancer Study",
                  section="Abstract", snippet="Cancer treatment...",
                  distance=0.85, ...),
        Reference(paper_id="2", chunk_id="2", title="Lung Tumor Analysis",
                  section="Methods", snippet="Tumor cells...",
                  distance=0.75, ...),
        Reference(paper_id="3", chunk_id="3", title="Chemotherapy Effects",
                  section="Results", snippet="Chemotherapy response...",
                  distance=0.70, ...),
    ]

    result = gate2_service.validate(refs)

    assert result.passed == True
    assert result.max_similarity == 0.85
    assert result.relevant_count == 3
    assert result.oncology_ratio == 1.0

def test_gate2_fails_low_similarity():
    refs = [
        Reference(paper_id="1", distance=0.5, title="Cancer", ...),
        Reference(paper_id="2", distance=0.4, title="Tumor", ...),
    ]

    result = gate2_service.validate(refs)

    assert result.passed == False
    assert result.reason == Gate2FailReason.LOW_SIMILARITY
```

---

## Related Issues

| Issue | Summary | Status |
|-------|---------|--------|
| OAR-12 | [F-05] Retrieval Confidence 검증 (Gate 2) | Done |
| OAR-37 | Similarity Threshold 검증 로직 구현 | Done |
| OAR-38 | Min Relevant Docs 검증 로직 구현 | Done |
| OAR-39 | Domain Validation 로직 구현 | Done |
| OAR-40 | Gate 2 통합 API 구현 | Done |

---

## Future Improvements

1. **ML-based Domain Classification**: Replace keyword matching with a trained classifier
2. **Adaptive Thresholds**: Adjust thresholds based on query complexity
3. **Partial Pass**: Allow synthesis with warnings for borderline cases
4. **Metrics Dashboard**: Track Gate 2 pass/fail rates in production
