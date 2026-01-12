"""도메인 분류기 서비스

싱글톤 패턴으로 도메인 분류기 인스턴스를 관리합니다.
Gate 1에서 쿼리 도메인을 분류하는 데 사용됩니다.

사용법:
    from app.services.domain_classifier_service import domain_classifier_service

    result = domain_classifier_service.classify("EGFR mutation treatment")
    if not result.is_allowed:
        # Off-domain 쿼리 처리
        pass
"""

import logging
import os
from typing import TYPE_CHECKING

from app.rag.base import ClassificationResult

if TYPE_CHECKING:
    from app.rag.classifiers.base import ClassifierProtocol

logger = logging.getLogger(__name__)


class DomainClassifierService:
    """도메인 분류기 서비스 (Singleton)

    Lazy Loading으로 분류기 인스턴스를 생성하고 관리합니다.
    환경 변수로 활성화/비활성화 제어 가능합니다.

    환경 변수:
        DOMAIN_CLASSIFIER_ENABLED: true/false (기본 true)
        DOMAIN_CLASSIFIER_MODE: warn/block (기본 warn)
        DOMAIN_CLASSIFIER_THRESHOLD: 0.0~1.0 (기본 0.3)
    """

    _instance: "DomainClassifierService | None" = None

    def __new__(cls) -> "DomainClassifierService":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._classifier = None
            cls._instance._enabled = (
                os.getenv("DOMAIN_CLASSIFIER_ENABLED", "true").lower() == "true"
            )
        return cls._instance

    @property
    def is_enabled(self) -> bool:
        """분류기 활성화 여부"""
        return self._enabled

    def _load_classifier(self) -> "ClassifierProtocol":
        """분류기 인스턴스 로드 (Lazy)"""
        if self._classifier is None:
            from app.rag import get_classifier

            classifier_name = os.getenv(
                "DOMAIN_CLASSIFIER_NAME", "pubmedbert_domain_v1"
            )
            self._classifier = get_classifier(classifier_name)
            logger.info(f"[DomainClassifierService] Loaded classifier: {classifier_name}")

        return self._classifier

    def classify(self, query: str) -> ClassificationResult:
        """쿼리 도메인 분류

        Args:
            query: 분류할 쿼리 텍스트

        Returns:
            ClassificationResult: 분류 결과
        """
        if not self._enabled:
            return ClassificationResult(
                category="oncology",
                confidence=1.0,
                is_allowed=True,
                reason="Domain classifier service disabled",
            )

        try:
            classifier = self._load_classifier()
            return classifier.classify(query)
        except Exception as e:
            logger.error(f"[DomainClassifierService] Classification failed: {e}")
            # 오류 시 허용 (fail-open)
            return ClassificationResult(
                category="error",
                confidence=0.0,
                is_allowed=True,
                reason=f"Service error: {str(e)}",
            )

    def get_status(self) -> dict:
        """서비스 상태 반환"""
        status = {
            "enabled": self._enabled,
            "classifier_loaded": self._classifier is not None,
        }

        if self._classifier is not None:
            status["classifier_config"] = self._classifier.get_config()

        return status


# 싱글톤 인스턴스
domain_classifier_service = DomainClassifierService()
