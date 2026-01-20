# OAR-37: Similarity Threshold Validation Implementation

> **Jira Ticket**: OAR-37
> **Status**: Completed
> **Author**: HK
> **Date**: 2025-12-30
> **File**: `src/gate2_retrieval.py`

---

## Summary

Implemented similarity threshold validation as part of Gate 2 (Retrieval Confidence). Checks if the maximum similarity score from retrieval meets a configurable threshold (default ≥ 0.7).

---

## Requirements (from Jira)

| Requirement | Implementation |
|-------------|----------------|
| max(similarity) ≥ 0.7 | `check_similarity_threshold()` |
| Configurable threshold | `Gate2Config.similarity_threshold` |
| Validation result logging | `logger.info("gate2_similarity_check", ...)` |
| Failure message | "관련 논문을 충분히 찾지 못했습니다. 질문을 더 구체적으로 해주세요." |

---

## Design Decisions

### 1. Why Check MAX Similarity (Not Average)?

```
Documents: [0.85, 0.72, 0.65, 0.45, 0.32]

MAX approach (implemented):
  max = 0.85 ≥ 0.7 → PASS ✅
  "At least one highly relevant document found"

AVERAGE approach (rejected):
  avg = 0.598 < 0.7 → FAIL ❌
  "Would reject valid queries with some noise"
```

**Reasoning:**
- One excellent match is often sufficient for RAG
- Average is skewed by noisy lower-ranked results
- Users care most about the best match quality
- More lenient while maintaining quality

### 2. Why 0.7 as Default Threshold?

```
Score Distribution Analysis:

0.9+ : Excellent match (exact topic)
0.8  : Strong match (related topic)
0.7  : Good match (relevant context)  ← THRESHOLD
0.6  : Marginal match (tangentially related)
0.5- : Weak match (likely noise)
```

**Reasoning:**
- 0.7 captures documents with meaningful relevance
- Below 0.7, retrieved docs often miss the query intent
- Empirically tuned on oncology test queries
- Configurable for domain-specific needs

### 3. Why Flexible Score Field Names?

```python
score = doc.get("score") or doc.get("rerank_score") or doc.get("similarity", 0)
```

**Reasoning:**
- Different components use different field names
- Retriever uses "score"
- Reranker uses "rerank_score"
- Some vector stores use "similarity"
- Handles all cases gracefully

---

## Implementation Details

### Function Signature

```python
def check_similarity_threshold(
    documents: list[dict],
    threshold: float = None,
    config: Gate2Config = None,
) -> tuple[bool, float, str]:
    """
    Check if max similarity score meets threshold.

    Args:
        documents: List of retrieved docs with 'score' field
        threshold: Override threshold (default 0.7)
        config: Gate2Config instance

    Returns:
        (passed, max_score, message)
    """
```

### Algorithm

```
Input: documents = [{"score": 0.85}, {"score": 0.72}, ...]
       threshold = 0.7

Step 1: Extract scores from all documents
        scores = [0.85, 0.72, 0.45]

Step 2: Find maximum score
        max_score = 0.85

Step 3: Compare to threshold
        passed = 0.85 >= 0.7 → True

Step 4: Generate message
        if passed: "유사도 검증 통과 (최대 점수: 0.85)"
        else:      "관련 논문을 충분히 찾지 못했습니다..."

Output: (True, 0.85, "유사도 검증 통과 (최대 점수: 0.85)")
```

---

## Usage Examples

### Basic Usage

```python
from gate2_retrieval import check_similarity_threshold

documents = [
    {"id": "doc1", "score": 0.89},
    {"id": "doc2", "score": 0.72},
    {"id": "doc3", "score": 0.45},
]

passed, max_score, message = check_similarity_threshold(documents)
print(f"Passed: {passed}")      # True
print(f"Max score: {max_score}")  # 0.89
print(f"Message: {message}")      # "유사도 검증 통과 (최대 점수: 0.89)"
```

### Custom Threshold

```python
# Stricter threshold for high-precision use cases
passed, score, msg = check_similarity_threshold(
    documents,
    threshold=0.8  # Higher bar
)
```

### With Configuration

```python
from gate2_retrieval import Gate2Config, check_similarity_threshold

config = Gate2Config(similarity_threshold=0.75)
passed, score, msg = check_similarity_threshold(documents, config=config)
```

---

## Test Cases

| Test Case | Documents | Threshold | Expected |
|-----------|-----------|-----------|----------|
| TC-1: High score | [0.92, 0.85, 0.70] | 0.7 | PASS |
| TC-2: Exact threshold | [0.70, 0.60, 0.50] | 0.7 | PASS |
| TC-3: Below threshold | [0.65, 0.55, 0.45] | 0.7 | FAIL |
| TC-4: Empty docs | [] | 0.7 | FAIL |
| TC-5: Single high doc | [0.88] | 0.7 | PASS |
| TC-6: All low scores | [0.30, 0.25, 0.20] | 0.7 | FAIL |

---

## Logging Output

```
2025-12-30 10:00:00 INFO gate2_similarity_check
    max_score=0.89
    threshold=0.7
    passed=True
```

On failure:
```
2025-12-30 10:00:00 WARNING gate2_failed
    reason=low_similarity
    max_similarity=0.55
    query="xyz random text"
```

---

## Performance

| Metric | Value |
|--------|-------|
| Time complexity | O(n) |
| Typical latency | <1ms |
| Memory | O(1) |

---

## Related Tickets

- **OAR-38**: Min Relevant Docs (uses min_doc_score=0.6)
- **OAR-39**: Domain Validation (runs after similarity check)
- **OAR-40**: Gate 2 Integration (combines all checks)
