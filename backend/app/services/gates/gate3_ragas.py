"""Gate 3: RAGAS Quality 검증 (OAR-13)

생성된 답변의 품질을 RAGAS 메트릭으로 평가하는 세 번째 Gate입니다.

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
    """Gate 3 검증 결과

    Attributes:
        passed: 검증 통과 여부
        reason: 실패 사유 (통과 시 None)
        message: 사용자에게 표시할 메시지 (실패 시)
        faithfulness: Faithfulness 점수 (0.0 ~ 1.0)
        answer_relevancy: Answer Relevancy 점수 (0.0 ~ 1.0)
        overall_score: 전체 점수 (평균)
        details: 추가 검증 상세 정보
    """
    passed: bool
    reason: Gate3FailReason | None = None
    message: str | None = None
    faithfulness: float | None = None
    answer_relevancy: float | None = None
    overall_score: float | None = None
    details: dict | None = None


class Gate3Service:
    """Gate 3: RAGAS Quality 검증 서비스

    생성된 답변의 품질을 평가합니다.

    환경 변수:
        GATE3_ENABLED: true/false (기본 false)
    """

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

    @property
    def faithfulness_threshold(self) -> float:
        """Faithfulness 임계값"""
        return self._get_config_value("gate3FaithfulnessThreshold", self._faithfulness_threshold)

    @property
    def relevancy_threshold(self) -> float:
        """Answer Relevancy 임계값"""
        return self._get_config_value("gate3RelevancyThreshold", self._relevancy_threshold)

    def _get_config_value(self, key: str, default: float) -> float:
        """RAGConfigManager에서 설정값 가져오기"""
        try:
            from app.core.rag_config import RAGConfigManager

            if RAGConfigManager.is_loaded():
                config = RAGConfigManager.get()
                value = config.parameters.get(key)
                if value is not None:
                    return float(value)
        except Exception as e:
            logger.warning(f"[Gate3Service] Failed to get config value for {key}: {e}")
        return default

    def get_status(self) -> dict:
        """서비스 상태 반환"""
        return {
            "enabled": self._enabled,
            "faithfulness_threshold": self.faithfulness_threshold,
            "relevancy_threshold": self.relevancy_threshold,
        }

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
            contexts: RAG 검색 결과 컨텍스트들 (snippet 목록)

        Returns:
            Gate3Result: 평가 결과
        """
        # Gate 3 비활성화 시 항상 통과
        if not self._enabled:
            logger.info("Gate 3 is disabled, auto-passing")
            return Gate3Result(
                passed=True,
                details={"bypassed": True, "reason": "Gate 3 disabled via GATE3_ENABLED=false"},
            )

        # 빈 답변 체크
        if not answer or not answer.strip():
            logger.warning("Gate 3: Empty answer")
            return Gate3Result(
                passed=False,
                reason=Gate3FailReason.LOW_RELEVANCY,
                message="답변이 생성되지 않았습니다.",
                faithfulness=0.0,
                answer_relevancy=0.0,
                overall_score=0.0,
            )

        # RAGAS 평가 수행
        try:
            from app.rag import get_evaluator

            evaluator = get_evaluator("ragas_v1")
            result = await evaluator.evaluate(question, answer, contexts)

            faithfulness = result.faithfulness
            relevancy = result.answer_relevancy
            overall = result.overall_score

            details = {
                "faithfulness_threshold": self.faithfulness_threshold,
                "relevancy_threshold": self.relevancy_threshold,
                "evaluation_details": result.details,
            }

            # Faithfulness 검증
            if faithfulness is not None and faithfulness < self.faithfulness_threshold:
                logger.info(
                    f"Gate 3 FAILED: Low faithfulness. "
                    f"score={faithfulness:.3f}, threshold={self.faithfulness_threshold}"
                )
                return Gate3Result(
                    passed=False,
                    reason=Gate3FailReason.LOW_FAITHFULNESS,
                    message="답변의 근거가 충분하지 않습니다. 제공된 논문 내용과 일치하지 않는 부분이 있을 수 있습니다.",
                    faithfulness=faithfulness,
                    answer_relevancy=relevancy,
                    overall_score=overall,
                    details=details,
                )

            # Answer Relevancy 검증
            if relevancy is not None and relevancy < self.relevancy_threshold:
                logger.info(
                    f"Gate 3 FAILED: Low relevancy. "
                    f"score={relevancy:.3f}, threshold={self.relevancy_threshold}"
                )
                return Gate3Result(
                    passed=False,
                    reason=Gate3FailReason.LOW_RELEVANCY,
                    message="답변이 질문과 충분히 관련되지 않습니다.",
                    faithfulness=faithfulness,
                    answer_relevancy=relevancy,
                    overall_score=overall,
                    details=details,
                )

            # 모든 검증 통과
            logger.info(
                f"Gate 3 PASSED: faithfulness={faithfulness:.3f}, "
                f"relevancy={relevancy:.3f}, overall={overall:.3f}"
            )
            return Gate3Result(
                passed=True,
                faithfulness=faithfulness,
                answer_relevancy=relevancy,
                overall_score=overall,
                details=details,
            )

        except Exception as e:
            logger.error(f"Gate 3 evaluation error: {e}")
            # 평가 실패 시 통과 (fail-open)
            return Gate3Result(
                passed=True,
                details={"error": str(e), "reason": "evaluation_failed"},
            )


# 싱글톤 인스턴스
gate3_service = Gate3Service()


def get_gate3_service() -> Gate3Service:
    """Gate 3 서비스 의존성"""
    return gate3_service


def reset_gate3_service() -> None:
    """Gate 3 서비스 리셋 (테스트용)"""
    Gate3Service._instance = None
