# OAR-38: Minimum Relevant Documents Validation Implementation

> **Jira Ticket**: OAR-38
> **Status**: Completed
> **Author**: HK
> **Date**: 2025-12-30
> **File**: `src/gate2_retrieval.py`

---

## Summary

Implemented minimum relevant documents validation as part of Gate 2. Ensures that at least 3 documents with similarity ≥ 0.6 are available, providing sufficient evidence for reliable answer generation.

---

## Requirements (from Jira)

| Requirement | Implementation |
|-------------|----------------|
| similarity ≥ 0.6 문서 ≥ 3개 | `check_min_relevant_docs()` |
| Configurable min count | `Gate2Config.min_relevant_docs` |
| Configurable min score | `Gate2Config.min_doc_score` |
| Accurate count | Exact counting with threshold check |
| Failure message | "충분한 근거 논문을 찾지 못했습니다." |

---

## Design Decisions

### 1. Why Require Multiple Documents?

```
Single document answer:
  "EGFR mutations respond to treatment [1]"
  ↓
  Relies entirely on one source
  ↓
  Risk: Source may be biased/wrong

Multiple document answer:
  "EGFR mutations respond to treatment [1][2][3]"
  ↓
  Cross-validated across sources
  ↓
  Benefit: More reliable, less hallucination
```

**Reasoning:**
- Multiple sources increase confidence
- Enables cross-validation of facts
- Reduces risk of single-source bias
- Standard in academic citation practice

### 2. Why 3 Documents as Minimum?

```
Document Count vs Quality:

1 doc:  Insufficient - single point of failure
2 docs: Marginal - limited cross-validation
3 docs: Adequate - basic triangulation  ← CHOSEN
5 docs: Good - strong evidence base
10+ :   Diminishing returns
```

**Reasoning:**
- 3 allows basic triangulation of information
- Balances coverage with availability
- Not too strict for niche queries
- Configurable for different use cases

### 3. Why 0.6 (Not 0.7) as Relevance Threshold?

```
Threshold comparison:

Main similarity threshold (OAR-37): 0.7
  → At least ONE doc must be highly relevant

Document count threshold (OAR-38): 0.6
  → Count docs that are "reasonably relevant"
  → Lower bar catches borderline useful docs
```

**Reasoning:**
- Allows borderline documents to contribute to count
- More lenient than top-doc requirement
- Recognizes that supporting docs may be less directly on-topic
- Still excludes noise (< 0.6)

---

## Implementation Details

### Function Signature

```python
def check_min_relevant_docs(
    documents: list[dict],
    min_count: int = None,
    min_score: float = None,
    config: Gate2Config = None,
) -> tuple[bool, int, str]:
    """
    Check if enough relevant documents were found.

    Args:
        documents: List of retrieved docs
        min_count: Override minimum count (default 3)
        min_score: Override score threshold (default 0.6)
        config: Gate2Config instance

    Returns:
        (passed, relevant_count, message)
    """
```

### Algorithm

```
Input: documents = [
         {"score": 0.85},  # ≥ 0.6 ✓
         {"score": 0.72},  # ≥ 0.6 ✓
         {"score": 0.65},  # ≥ 0.6 ✓
         {"score": 0.45},  # < 0.6 ✗
       ]
       min_count = 3, min_score = 0.6

Step 1: Count documents with score ≥ min_score
        relevant_count = 3

Step 2: Compare to minimum
        passed = 3 >= 3 → True

Step 3: Generate message
        if passed: "관련 문서 수 검증 통과 (3개 문서)"
        else:      "충분한 근거 논문을 찾지 못했습니다."

Output: (True, 3, "관련 문서 수 검증 통과 (3개 문서)")
```

---

## Usage Examples

### Basic Usage

```python
from gate2_retrieval import check_min_relevant_docs

documents = [
    {"id": "doc1", "score": 0.89},
    {"id": "doc2", "score": 0.72},
    {"id": "doc3", "score": 0.65},
    {"id": "doc4", "score": 0.45},
]

passed, count, message = check_min_relevant_docs(documents)
print(f"Passed: {passed}")    # True
print(f"Count: {count}")      # 3
print(f"Message: {message}")  # "관련 문서 수 검증 통과 (3개 문서)"
```

### Custom Thresholds

```python
# Stricter: require 5 docs with score ≥ 0.7
passed, count, msg = check_min_relevant_docs(
    documents,
    min_count=5,
    min_score=0.7
)
```

### For High-Stakes Queries

```python
from gate2_retrieval import Gate2Config, check_min_relevant_docs

# Medical decision support needs more evidence
strict_config = Gate2Config(
    min_relevant_docs=5,
    min_doc_score=0.7
)
passed, count, msg = check_min_relevant_docs(documents, config=strict_config)
```

---

## Test Cases

| Test Case | Docs (scores) | Min Count | Min Score | Expected |
|-----------|---------------|-----------|-----------|----------|
| TC-1: Plenty of docs | [0.9, 0.8, 0.7, 0.65, 0.6] | 3 | 0.6 | PASS (5) |
| TC-2: Exactly 3 | [0.85, 0.72, 0.61, 0.55] | 3 | 0.6 | PASS (3) |
| TC-3: Just under | [0.85, 0.72, 0.55, 0.45] | 3 | 0.6 | FAIL (2) |
| TC-4: All low | [0.55, 0.50, 0.45, 0.40] | 3 | 0.6 | FAIL (0) |
| TC-5: Empty | [] | 3 | 0.6 | FAIL (0) |
| TC-6: High bar | [0.9, 0.8, 0.7, 0.65] | 3 | 0.75 | FAIL (2) |

---

## Interaction with OAR-37

```
Query: "EGFR inhibitors"

OAR-37 Check (Similarity Threshold):
  max(scores) = 0.89 ≥ 0.7 → PASS

OAR-38 Check (Min Relevant Docs):
  count(score ≥ 0.6) = 4 ≥ 3 → PASS

Overall Gate 2: PASS ✅
```

Both checks must pass for Gate 2 to pass.

---

## Edge Cases

### Reranker Scores

```python
# After reranking, use rerank_score
documents = [
    {"score": 0.45, "rerank_score": 0.92},  # Uses rerank_score
    {"score": 0.50, "rerank_score": 0.85},
]
```

The function checks for `score`, `rerank_score`, and `similarity` fields.

### Sparse Results

```python
# Only 2 docs in entire vector store
documents = [
    {"score": 0.95},
    {"score": 0.88},
]
passed, count, msg = check_min_relevant_docs(documents)
# FAIL - only 2 docs even though both are excellent
```

Consider lowering `min_count` for small corpora.

---

## Logging Output

```
2025-12-30 10:00:00 INFO gate2_min_docs_check
    relevant_count=4
    min_count=3
    min_score=0.6
    passed=True
```

On failure:
```
2025-12-30 10:00:00 WARNING gate2_failed
    reason=insufficient_docs
    relevant_count=2
    query="rare disease query"
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

- **OAR-37**: Similarity Threshold (runs before)
- **OAR-39**: Domain Validation (runs after)
- **OAR-40**: Gate 2 Integration (combines all)
