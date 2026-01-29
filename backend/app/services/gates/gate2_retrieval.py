"""Gate 2: Retrieval Confidence 검증 (OAR-12)

RAG 검색 결과의 품질을 검증하는 두 번째 Gate입니다.
검색된 문서들이 실제로 쿼리와 관련이 있는지 확인합니다.

검증 항목:
- OAR-37: Similarity Threshold (max similarity >= 0.7)
- OAR-38: Min Relevant Docs (similarity >= 0.6인 문서 >= 3개)
- OAR-39: Domain Validation (oncology 문서 비율 >= 80%)

환경 변수:
- GATE2_ENABLED: true/false (기본 true) - Gate 2 활성화 여부
"""

import logging
import os
from dataclasses import dataclass
from enum import Enum

from app.schemas.chat import Reference

logger = logging.getLogger(__name__)


class Gate2FailReason(str, Enum):
    """Gate 2 실패 사유"""
    LOW_SIMILARITY = "low_similarity"
    INSUFFICIENT_DOCS = "insufficient_docs"
    DOMAIN_MISMATCH = "domain_mismatch"


@dataclass
class Gate2Result:
    """Gate 2 검증 결과

    Attributes:
        passed: 검증 통과 여부
        reason: 실패 사유 (통과 시 None)
        message: 사용자에게 표시할 메시지 (실패 시)
        tips: 질문 방향 제안 (메시지 영역에 표시)
        suggestions: 실제 클릭 가능한 질문들 (버튼으로 표시)
        max_similarity: 최대 유사도 점수
        relevant_count: 관련 문서 수 (similarity >= threshold)
        oncology_ratio: oncology 도메인 문서 비율
        details: 추가 검증 상세 정보
    """
    passed: bool
    reason: Gate2FailReason | None = None
    message: str | None = None
    tips: list[str] | None = None
    suggestions: list[str] | None = None
    max_similarity: float = 0.0
    relevant_count: int = 0
    oncology_ratio: float = 1.0
    details: dict | None = None


# Pre-defined tips and clickable questions for each failure type
GATE2_FAILURE_TIPS = {
    Gate2FailReason.LOW_SIMILARITY: [
        "Try using more specific medical terms (e.g., 'EGFR mutation' instead of 'lung cancer')",
        "Include the cancer type, stage, or specific biomarker in your question",
        "Ask about a specific drug or treatment protocol",
    ],
    Gate2FailReason.INSUFFICIENT_DOCS: [
        "Ask about well-studied topics like immunotherapy or targeted therapy",
        "Try questions about common cancer types (breast, lung, colorectal)",
        "Focus on established treatments or biomarkers",
    ],
    Gate2FailReason.DOMAIN_MISMATCH: [
        "This system specializes in oncology and cancer research",
        "Rephrase your question to focus on cancer-related topics",
        "Ask about cancer treatments, biomarkers, or clinical trials",
    ],
}

# Actual clickable questions for each failure type
GATE2_FAILURE_QUESTIONS = {
    Gate2FailReason.LOW_SIMILARITY: [
        "What is the role of EGFR mutations in non-small cell lung cancer treatment?",
        "How does immunotherapy work in melanoma treatment?",
        "What are the mechanisms of resistance to targeted therapy in cancer?",
    ],
    Gate2FailReason.INSUFFICIENT_DOCS: [
        "What are the current standard treatments for breast cancer?",
        "How do checkpoint inhibitors work in cancer immunotherapy?",
        "What biomarkers are used to guide lung cancer treatment decisions?",
    ],
    Gate2FailReason.DOMAIN_MISMATCH: [
        "What are the latest advances in cancer immunotherapy?",
        "How do EGFR inhibitors work in non-small cell lung cancer?",
        "What biomarkers predict response to checkpoint inhibitors?",
    ],
}


class Gate2Service:
    """Gate 2: Retrieval Confidence 검증 서비스

    검색 결과의 품질을 검증합니다.

    설정 우선순위:
        1. DB (rag_settings.parameters 내 gate2_* 값)
        2. 기본값

    환경 변수:
        GATE2_ENABLED: true/false (기본 true)
    """

    # 기본 임계값 설정 (완화된 값 - 2026-01-30)
    # 원래 값: 0.7, 0.6, 3, 0.8 → 일상 쿼리가 모두 실패함
    DEFAULT_SIMILARITY_THRESHOLD = 0.4  # OAR-37: max similarity >= 0.4 (was 0.7)
    DEFAULT_RELEVANT_SCORE = 0.4        # OAR-38: 관련 문서 판정 기준 (was 0.6)
    DEFAULT_MIN_RELEVANT_DOCS = 1       # OAR-38: 최소 관련 문서 수 (was 3)
    DEFAULT_DOMAIN_RATIO = 0.5          # OAR-39: oncology 비율 >= 50% (was 80%)

    # Oncology 관련 키워드 (Domain Validation용)
    ONCOLOGY_KEYWORDS = [
        "cancer", "tumor", "tumour", "oncology", "carcinoma", "melanoma",
        "leukemia", "lymphoma", "sarcoma", "neoplasm", "malignant",
        "metastasis", "chemotherapy", "immunotherapy", "radiotherapy",
        "oncogene", "EGFR", "HER2", "BRCA", "PD-1", "PD-L1",
        "암", "종양", "항암", "전이", "악성"
    ]

    _instance: "Gate2Service | None" = None

    def __new__(cls) -> "Gate2Service":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._enabled = (
                os.getenv("GATE2_ENABLED", "true").lower() == "true"
            )
            # 기본값으로 초기화 (DB 로드 전 사용)
            cls._instance._similarity_threshold = cls.DEFAULT_SIMILARITY_THRESHOLD
            cls._instance._relevant_score = cls.DEFAULT_RELEVANT_SCORE
            cls._instance._min_relevant_docs = cls.DEFAULT_MIN_RELEVANT_DOCS
            cls._instance._domain_ratio = cls.DEFAULT_DOMAIN_RATIO
        return cls._instance

    @property
    def is_enabled(self) -> bool:
        """Gate 2 활성화 여부"""
        return self._enabled

    @property
    def similarity_threshold(self) -> float:
        """최대 유사도 임계값 (DB 설정 우선)"""
        return self._get_config_value("gate2SimilarityThreshold", self._similarity_threshold)

    @property
    def relevant_score(self) -> float:
        """관련 문서 판정 기준 점수 (DB 설정 우선)"""
        return self._get_config_value("gate2RelevantScore", self._relevant_score)

    @property
    def min_relevant_docs(self) -> int:
        """최소 관련 문서 수 (DB 설정 우선)"""
        return int(self._get_config_value("gate2MinRelevantDocs", self._min_relevant_docs))

    @property
    def domain_ratio(self) -> float:
        """oncology 도메인 비율 임계값 (DB 설정 우선)"""
        return self._get_config_value("gate2DomainRatio", self._domain_ratio)

    def _get_config_value(self, key: str, default: float | int) -> float | int:
        """RAGConfigManager에서 설정값 가져오기"""
        try:
            from app.core.rag_config import RAGConfigManager

            if RAGConfigManager.is_loaded():
                config = RAGConfigManager.get()
                value = config.parameters.get(key)
                if value is not None:
                    return value
        except Exception as e:
            logger.warning(f"[Gate2Service] Failed to get config value for {key}: {e}")
        return default

    def get_status(self) -> dict:
        """서비스 상태 반환"""
        return {
            "enabled": self._enabled,
            "similarity_threshold": self.similarity_threshold,
            "relevant_score": self.relevant_score,
            "min_relevant_docs": self.min_relevant_docs,
            "domain_ratio": self.domain_ratio,
        }

    def validate(self, references: list[Reference]) -> Gate2Result:
        """검색 결과 품질 검증 (OAR-40)

        모든 검증 항목을 순차적으로 수행하고 결과를 반환합니다.

        Args:
            references: RAG 검색 결과 참조 목록

        Returns:
            Gate2Result: 검증 결과
        """
        # Gate 2 비활성화 시 항상 통과
        if not self._enabled:
            logger.info("Gate 2 is disabled, auto-passing")
            return Gate2Result(
                passed=True,
                max_similarity=1.0,
                relevant_count=len(references) if references else 0,
                oncology_ratio=1.0,
                details={"bypassed": True, "reason": "Gate 2 disabled via GATE2_ENABLED=false"},
            )

        if not references:
            logger.warning("Gate 2: No references to validate")
            return Gate2Result(
                passed=False,
                reason=Gate2FailReason.INSUFFICIENT_DOCS,
                message="검색 결과가 없습니다. 다른 질문을 시도해 주세요.",
                tips=GATE2_FAILURE_TIPS[Gate2FailReason.INSUFFICIENT_DOCS],
                suggestions=GATE2_FAILURE_QUESTIONS[Gate2FailReason.INSUFFICIENT_DOCS],
                max_similarity=0.0,
                relevant_count=0,
                oncology_ratio=0.0,
            )

        # 메트릭 계산
        max_similarity = self._calculate_max_similarity(references)
        relevant_count = self._count_relevant_docs(references)
        oncology_ratio = self._calculate_oncology_ratio(references)

        details = {
            "total_docs": len(references),
            "similarity_threshold": self.similarity_threshold,
            "relevant_score_threshold": self.relevant_score,
            "min_relevant_docs": self.min_relevant_docs,
            "domain_ratio_threshold": self.domain_ratio,
        }

        # OAR-37: Similarity Threshold 검증
        if not self._check_similarity_threshold(max_similarity):
            logger.info(
                f"Gate 2 FAILED: Low similarity. "
                f"max={max_similarity:.3f}, threshold={self.similarity_threshold}"
            )
            return Gate2Result(
                passed=False,
                reason=Gate2FailReason.LOW_SIMILARITY,
                message="관련 논문을 충분히 찾지 못했습니다. 질문을 더 구체적으로 해주세요.",
                tips=GATE2_FAILURE_TIPS[Gate2FailReason.LOW_SIMILARITY],
                suggestions=GATE2_FAILURE_QUESTIONS[Gate2FailReason.LOW_SIMILARITY],
                max_similarity=max_similarity,
                relevant_count=relevant_count,
                oncology_ratio=oncology_ratio,
                details=details,
            )

        # OAR-38: Min Relevant Docs 검증
        if not self._check_min_relevant_docs(relevant_count):
            logger.info(
                f"Gate 2 FAILED: Insufficient docs. "
                f"count={relevant_count}, min={self.min_relevant_docs}"
            )
            return Gate2Result(
                passed=False,
                reason=Gate2FailReason.INSUFFICIENT_DOCS,
                message="충분한 근거 논문을 찾지 못했습니다.",
                tips=GATE2_FAILURE_TIPS[Gate2FailReason.INSUFFICIENT_DOCS],
                suggestions=GATE2_FAILURE_QUESTIONS[Gate2FailReason.INSUFFICIENT_DOCS],
                max_similarity=max_similarity,
                relevant_count=relevant_count,
                oncology_ratio=oncology_ratio,
                details=details,
            )

        # OAR-39: Domain Validation 검증
        if not self._check_domain_validation(oncology_ratio):
            logger.info(
                f"Gate 2 FAILED: Domain mismatch. "
                f"ratio={oncology_ratio:.2%}, threshold={self.domain_ratio:.2%}"
            )
            return Gate2Result(
                passed=False,
                reason=Gate2FailReason.DOMAIN_MISMATCH,
                message="검색 결과가 암 연구와 관련성이 낮습니다.",
                tips=GATE2_FAILURE_TIPS[Gate2FailReason.DOMAIN_MISMATCH],
                suggestions=GATE2_FAILURE_QUESTIONS[Gate2FailReason.DOMAIN_MISMATCH],
                max_similarity=max_similarity,
                relevant_count=relevant_count,
                oncology_ratio=oncology_ratio,
                details=details,
            )

        # 모든 검증 통과
        logger.info(
            f"Gate 2 PASSED: similarity={max_similarity:.3f}, "
            f"relevant_docs={relevant_count}, oncology_ratio={oncology_ratio:.2%}"
        )
        return Gate2Result(
            passed=True,
            max_similarity=max_similarity,
            relevant_count=relevant_count,
            oncology_ratio=oncology_ratio,
            details=details,
        )

    # ─────────────────────────────────────────────────────────────
    # OAR-37: Similarity Threshold
    # ─────────────────────────────────────────────────────────────

    def _calculate_max_similarity(self, references: list[Reference]) -> float:
        """최대 유사도 점수 계산"""
        if not references:
            return 0.0
        return max(ref.distance for ref in references)

    def _check_similarity_threshold(self, max_similarity: float) -> bool:
        """OAR-37: max(similarity) >= threshold"""
        return max_similarity >= self.similarity_threshold

    # ─────────────────────────────────────────────────────────────
    # OAR-38: Min Relevant Docs
    # ─────────────────────────────────────────────────────────────

    def _count_relevant_docs(self, references: list[Reference]) -> int:
        """관련 문서 수 계산 (similarity >= relevant_score)"""
        return sum(1 for ref in references if ref.distance >= self.relevant_score)

    def _check_min_relevant_docs(self, relevant_count: int) -> bool:
        """OAR-38: relevant_count >= min_relevant_docs"""
        return relevant_count >= self.min_relevant_docs

    # ─────────────────────────────────────────────────────────────
    # OAR-39: Domain Validation
    # ─────────────────────────────────────────────────────────────

    def _calculate_oncology_ratio(self, references: list[Reference]) -> float:
        """Oncology 도메인 문서 비율 계산

        논문 제목과 snippet에서 oncology 관련 키워드를 찾아 비율을 계산합니다.
        """
        if not references:
            return 0.0

        oncology_count = 0
        for ref in references:
            if self._is_oncology_document(ref):
                oncology_count += 1

        return oncology_count / len(references)

    def _is_oncology_document(self, ref: Reference) -> bool:
        """문서가 oncology 도메인인지 확인

        제목과 snippet에서 oncology 관련 키워드를 검색합니다.
        """
        # 검색 대상 텍스트
        text_to_check = f"{ref.title} {ref.snippet}".lower()

        # 키워드 매칭
        for keyword in self.ONCOLOGY_KEYWORDS:
            if keyword.lower() in text_to_check:
                return True

        return False

    def _check_domain_validation(self, oncology_ratio: float) -> bool:
        """OAR-39: oncology_ratio >= domain_ratio"""
        return oncology_ratio >= self.domain_ratio


# 싱글톤 인스턴스
gate2_service = Gate2Service()


def get_gate2_service() -> Gate2Service:
    """Gate 2 서비스 의존성"""
    return gate2_service


def reset_gate2_service() -> None:
    """Gate 2 서비스 리셋 (테스트용)"""
    Gate2Service._instance = None
