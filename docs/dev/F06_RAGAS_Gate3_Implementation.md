# F-06: RAGAS Gate 3 Implementation Plan

> **Status**: Planning
> **Feature**: F-06 RAGAS Evaluation (Gate 3)
> **OAR Reference**: OAR-13

---

## Overview

Gate 3는 RAG 파이프라인의 마지막 품질 검증 단계로, 생성된 답변의 품질을 RAGAS 메트릭으로 평가합니다.

```
Query → [Gate 1: Domain] → RAG Search → [Gate 2: Retrieval] → Generate → [Gate 3: RAGAS] → Response
```

---

## 환경 변수 제어

Gate 1, Gate 2와 동일한 패턴으로 환경 변수로 On/Off 제어:

```bash
# .env
GATE3_ENABLED=true   # Gate 3 (RAGAS) 활성화 (기본: false)
```

- `true`: RAGAS 평가 수행, 결과 로깅
- `false`: RAGAS 평가 스킵 (기본값 - 성능 고려)

---

## RAGAS 메트릭

### 핵심 메트릭 (Phase 1)

| 메트릭 | 설명 | 임계값 | 필요 입력 |
|--------|------|--------|-----------|
| **Faithfulness** | 답변이 컨텍스트에 충실한가 | ≥ 0.85 | question, answer, contexts |
| **Answer Relevancy** | 답변이 질문에 관련 있는가 | ≥ 0.80 | question, answer |

### 확장 메트릭 (Phase 2, Optional)

| 메트릭 | 설명 | 필요 입력 |
|--------|------|-----------|
| Context Precision | 검색된 컨텍스트의 정밀도 | question, answer, contexts |
| Context Recall | 검색된 컨텍스트의 재현율 | question, answer, contexts, ground_truth |

---

## 구현 구조

### 디렉토리 구조

```
backend/app/
├── services/gates/
│   ├── __init__.py
│   ├── gate2_retrieval.py     # 기존 Gate 2
│   └── gate3_ragas.py         # 새로 추가 ✅
│
└── rag/evaluators/            # 새로 추가 ✅
    ├── __init__.py
    ├── base.py                # EvaluatorProtocol
    └── ragas.py               # RAGAS 평가기
```

### 1. Gate 3 Service (`gate3_ragas.py`)

Gate 2와 동일한 패턴:

```python
"""Gate 3: RAGAS Quality 검증 (OAR-13)

생성된 답변의 품질을 RAGAS 메트릭으로 평가합니다.

검증 항목:
- Faithfulness: 답변이 컨텍스트에 충실한지 (≥ 0.85)
- Answer Relevancy: 답변이 질문에 관련 있는지 (≥ 0.80)

환경 변수:
- GATE3_ENABLED: true/false (기본 false) - Gate 3 활성화 여부
"""

import logging
import os
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class Gate3FailReason(str, Enum):
    """Gate 3 실패 사유"""
    LOW_FAITHFULNESS = "low_faithfulness"
    LOW_RELEVANCY = "low_relevancy"


@dataclass
class Gate3Result:
    """Gate 3 검증 결과"""
    passed: bool
    reason: Gate3FailReason | None = None
    message: str | None = None
    faithfulness: float | None = None
    answer_relevancy: float | None = None
    overall_score: float | None = None
    details: dict | None = None


class Gate3Service:
    """Gate 3: RAGAS Quality 검증 서비스"""

    DEFAULT_FAITHFULNESS_THRESHOLD = 0.85
    DEFAULT_RELEVANCY_THRESHOLD = 0.80

    _instance: "Gate3Service | None" = None

    def __new__(cls) -> "Gate3Service":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._enabled = (
                os.getenv("GATE3_ENABLED", "false").lower() == "true"
            )
            cls._instance._faithfulness_threshold = cls.DEFAULT_FAITHFULNESS_THRESHOLD
            cls._instance._relevancy_threshold = cls.DEFAULT_RELEVANCY_THRESHOLD
        return cls._instance

    @property
    def is_enabled(self) -> bool:
        """Gate 3 활성화 여부"""
        return self._enabled

    async def evaluate(
        self,
        question: str,
        answer: str,
        contexts: list[str],
    ) -> Gate3Result:
        """답변 품질 평가

        Args:
            question: 사용자 질문
            answer: 생성된 답변
            contexts: RAG 검색 결과 컨텍스트들

        Returns:
            Gate3Result: 평가 결과
        """
        if not self._enabled:
            logger.info("Gate 3 is disabled, auto-passing")
            return Gate3Result(
                passed=True,
                details={"bypassed": True, "reason": "Gate 3 disabled via GATE3_ENABLED=false"}
            )

        # RAGAS 평가 수행
        from app.rag import get_evaluator

        try:
            evaluator = get_evaluator("ragas_v1")
            result = await evaluator.evaluate(question, answer, contexts)

            # 임계값 검증
            if result.faithfulness and result.faithfulness < self._faithfulness_threshold:
                return Gate3Result(
                    passed=False,
                    reason=Gate3FailReason.LOW_FAITHFULNESS,
                    message="답변의 근거가 충분하지 않습니다.",
                    faithfulness=result.faithfulness,
                    answer_relevancy=result.answer_relevancy,
                    overall_score=result.overall_score,
                )

            if result.answer_relevancy and result.answer_relevancy < self._relevancy_threshold:
                return Gate3Result(
                    passed=False,
                    reason=Gate3FailReason.LOW_RELEVANCY,
                    message="답변이 질문과 충분히 관련되지 않습니다.",
                    faithfulness=result.faithfulness,
                    answer_relevancy=result.answer_relevancy,
                    overall_score=result.overall_score,
                )

            return Gate3Result(
                passed=True,
                faithfulness=result.faithfulness,
                answer_relevancy=result.answer_relevancy,
                overall_score=result.overall_score,
            )

        except Exception as e:
            logger.error(f"Gate 3 evaluation failed: {e}")
            # 평가 실패 시 통과 (fail-open)
            return Gate3Result(
                passed=True,
                details={"error": str(e), "reason": "evaluation_failed"}
            )


# 싱글톤 인스턴스
gate3_service = Gate3Service()


def get_gate3_service() -> Gate3Service:
    """Gate 3 서비스 의존성"""
    return gate3_service
```

### 2. RAGAS Evaluator (`rag/evaluators/ragas.py`)

```python
"""RAGAS 기반 품질 평가기"""

from app.rag.registry import register_evaluator
from app.rag.base import EvaluationResult


@register_evaluator
class RAGASEvaluator:
    """RAGAS 메트릭 기반 답변 품질 평가

    Faithfulness와 Answer Relevancy를 측정하여
    RAG 파이프라인의 답변 품질을 평가합니다.

    메트릭:
    - Faithfulness: 답변이 컨텍스트에 충실한 정도
    - Answer Relevancy: 답변이 질문에 관련된 정도
    """

    name = "ragas_v1"

    def __init__(self):
        self._llm = None  # Lazy load

    async def evaluate(
        self,
        question: str,
        answer: str,
        contexts: list[str],
    ) -> EvaluationResult:
        """품질 평가 수행"""
        from ragas import evaluate
        from ragas.metrics import faithfulness, answer_relevancy
        from datasets import Dataset

        # RAGAS 데이터셋 형식으로 변환
        data = {
            "question": [question],
            "answer": [answer],
            "contexts": [contexts],
        }
        dataset = Dataset.from_dict(data)

        # 평가 수행
        result = evaluate(
            dataset,
            metrics=[faithfulness, answer_relevancy],
        )

        faith_score = result["faithfulness"]
        relevancy_score = result["answer_relevancy"]
        overall = (faith_score + relevancy_score) / 2

        return EvaluationResult(
            faithfulness=faith_score,
            answer_relevancy=relevancy_score,
            overall_score=overall,
            passed=faith_score >= 0.85 and relevancy_score >= 0.80,
            details={
                "metrics": {
                    "faithfulness": faith_score,
                    "answer_relevancy": relevancy_score,
                }
            }
        )

    def get_config(self) -> dict:
        return {
            "name": self.name,
            "metrics": ["faithfulness", "answer_relevancy"],
            "thresholds": {
                "faithfulness": 0.85,
                "answer_relevancy": 0.80,
            }
        }
```

---

## 통합 지점

### 1. Agent Service 통합

`backend/app/services/agent/service.py`의 `execute_stream()` 또는 일반 RAG 파이프라인에서 답변 생성 후 Gate 3 호출:

```python
# 답변 생성 후
final_answer = "..."
contexts = [ref.snippet for ref in references]

# Gate 3 평가
from app.services.gates.gate3_ragas import get_gate3_service

gate3 = get_gate3_service()
gate3_result = await gate3.evaluate(
    question=query,
    answer=final_answer,
    contexts=contexts,
)

# 결과 로깅
if gate3_result.passed:
    logger.info(f"Gate 3 PASSED: faithfulness={gate3_result.faithfulness}, relevancy={gate3_result.answer_relevancy}")
else:
    logger.warning(f"Gate 3 FAILED: {gate3_result.reason}")
```

### 2. SSE 이벤트 (선택적)

프론트엔드에 Gate 3 결과 전송:

```python
yield AgentEvent(
    event_type="gate3",
    data={
        "passed": gate3_result.passed,
        "faithfulness": gate3_result.faithfulness,
        "answer_relevancy": gate3_result.answer_relevancy,
        "reason": gate3_result.reason,
    },
)
```

### 3. AnswerLog 저장

평가 결과를 DB에 저장하여 분석:

```python
# AnswerLog.evidence에 추가
agent_execution["gate3"] = {
    "passed": gate3_result.passed,
    "faithfulness": gate3_result.faithfulness,
    "answer_relevancy": gate3_result.answer_relevancy,
    "reason": gate3_result.reason,
}
```

---

## 의존성

```toml
# pyproject.toml
[project.dependencies]
ragas = "^0.1.0"
datasets = "^2.0.0"  # RAGAS 데이터셋 형식
```

---

## 성능 고려사항

1. **기본 비활성화**: `GATE3_ENABLED=false` (기본값)
   - RAGAS 평가는 추가 LLM 호출이 필요하여 latency 증가
   - 프로덕션에서는 샘플링으로 평가 권장

2. **비동기 평가**: 답변 반환 후 백그라운드에서 평가 (선택적)
   - 사용자 latency에 영향 없음
   - 결과는 로깅/분석용

3. **캐싱**: 동일 질문-답변 쌍의 평가 결과 캐싱 고려

---

## 구현 순서

### Phase 1: 기본 구현
- [ ] `backend/app/rag/evaluators/` 디렉토리 생성
- [ ] `evaluators/base.py` - EvaluatorProtocol 정의
- [ ] `evaluators/ragas.py` - RAGAS 평가기 구현
- [ ] `evaluators/__init__.py` - 모듈 export
- [ ] `services/gates/gate3_ragas.py` - Gate 3 서비스 구현
- [ ] 환경 변수 `GATE3_ENABLED` 지원
- [ ] 단위 테스트

### Phase 2: 통합
- [ ] Agent Service에 Gate 3 통합
- [ ] SSE 이벤트 추가 (선택적)
- [ ] AnswerLog에 평가 결과 저장

### Phase 3: 모니터링 (선택적)
- [ ] 프론트엔드 Gate 3 결과 표시
- [ ] 대시보드에 품질 메트릭 추가

---

## 테스트 계획

```bash
# 단위 테스트
pytest tests/rag/evaluators/test_ragas.py -v
pytest tests/services/gates/test_gate3.py -v

# 통합 테스트
GATE3_ENABLED=true pytest tests/integration/test_rag_pipeline.py -v
```

---

## 환경 변수 요약

| 변수 | 기본값 | 설명 |
|------|--------|------|
| `GATE1_ENABLED` | `true` | Domain Classifier 활성화 |
| `GATE2_ENABLED` | `true` | Retrieval Confidence 활성화 |
| `GATE3_ENABLED` | `false` | RAGAS Quality 활성화 |

---

## 참고

- [RAGAS Documentation](https://docs.ragas.io/)
- [CLAUDE.md - ADR-006: Three-Gate Safety Architecture](../../CLAUDE.md)
- [Gate 2 구현](../../backend/app/services/gates/gate2_retrieval.py)
