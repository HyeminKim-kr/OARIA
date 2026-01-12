"""PubMedBERT 기반 Zero-shot 도메인 분류기"""

import logging
import os
import time
from typing import Any

from app.rag.base import ClassificationResult
from app.rag.registry import register_classifier

logger = logging.getLogger(__name__)


def _get_best_device() -> int:
    """최적의 디바이스 선택

    Returns:
        -1: CPU, 0+: GPU 인덱스 (transformers pipeline용)
    """
    try:
        import torch

        if torch.cuda.is_available():
            return 0  # GPU
        elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            return 0  # Apple Silicon (MPS도 0으로)
    except ImportError:
        pass
    return -1  # CPU


@register_classifier
class PubMedBERTDomainClassifier:
    """Zero-shot Oncology 도메인 분류기

    Zero-shot Classification을 사용하여 쿼리가 Oncology 도메인인지 분류합니다.
    Off-domain 쿼리는 경고 로그를 남기고 RAG 파이프라인 진행을 허용합니다.

    스펙:
    - 모델: facebook/bart-large-mnli (Zero-shot Classification)
    - 분류 클래스: oncology, cardiology, neurology, general medicine, non-medical
    - Lazy Loading: 첫 호출 시 모델 로드
    - GPU/MPS/CPU 자동 감지

    사용법:
        from app.rag import get_classifier
        classifier = get_classifier("pubmedbert_domain_v1")
        result = classifier.classify("EGFR mutation lung cancer treatment")
    """

    name = "pubmedbert_domain_v1"

    # 분류 후보 레이블
    # Note: Zero-shot 모델이 키워드 기반으로 분류하므로 관련 용어를 충분히 포함
    CANDIDATE_LABELS = [
        # 종양학: 암 종류 + 치료법 키워드 포함
        "oncology cancer tumor chemotherapy immunotherapy radiation targeted therapy carcinoma lymphoma leukemia melanoma sarcoma",
        # 심장학
        "cardiology heart cardiovascular arrhythmia hypertension coronary",
        # 신경학
        "neurology brain nervous system stroke epilepsy alzheimer parkinson",
        # 일반 의학
        "general medicine healthcare diagnosis symptoms treatment medical",
        # 비의료
        "non-medical unrelated daily life food weather sports entertainment",
    ]

    # 레이블 -> 카테고리 매핑
    LABEL_TO_CATEGORY = {
        "oncology cancer tumor chemotherapy immunotherapy radiation targeted therapy carcinoma lymphoma leukemia melanoma sarcoma": "oncology",
        "cardiology heart cardiovascular arrhythmia hypertension coronary": "cardiology",
        "neurology brain nervous system stroke epilepsy alzheimer parkinson": "neurology",
        "general medicine healthcare diagnosis symptoms treatment medical": "general_medicine",
        "non-medical unrelated daily life food weather sports entertainment": "non_medical",
    }

    # 허용되는 도메인
    ALLOWED_DOMAINS = ["oncology"]

    def __init__(
        self,
        model_name: str = "facebook/bart-large-mnli",
        threshold: float = 0.3,
        device: int | None = None,
    ):
        """분류기 초기화

        Args:
            model_name: Zero-shot 분류 모델 이름
            threshold: 허용 도메인 판정 임계값 (기본 0.3)
            device: 디바이스 인덱스 (-1=CPU, 0+=GPU). None이면 자동 감지
        """
        self.model_name = model_name
        self.threshold = threshold
        self._device = device

        # Lazy loading
        self._pipeline = None
        self._enabled = os.getenv("DOMAIN_CLASSIFIER_ENABLED", "true").lower() == "true"
        self._mode = os.getenv("DOMAIN_CLASSIFIER_MODE", "warn")  # warn | block

    @property
    def device(self) -> int:
        """디바이스 인덱스"""
        if self._device is None:
            self._device = _get_best_device()
        return self._device

    def _load_pipeline(self) -> None:
        """Zero-shot 분류 파이프라인 로드 (Lazy)"""
        if self._pipeline is not None:
            return

        logger.info(f"[DomainClassifier] Loading model: {self.model_name}")
        start = time.perf_counter()

        try:
            from transformers import pipeline

            self._pipeline = pipeline(
                "zero-shot-classification",
                model=self.model_name,
                device=self.device,
            )

            elapsed = time.perf_counter() - start
            device_name = "GPU" if self.device >= 0 else "CPU"
            logger.info(f"[DomainClassifier] Model loaded in {elapsed:.2f}s on {device_name}")

        except Exception as e:
            logger.error(f"[DomainClassifier] Failed to load model: {e}")
            raise

    def classify(self, query: str, **kwargs: Any) -> ClassificationResult:
        """쿼리 도메인 분류

        Args:
            query: 분류할 쿼리 텍스트

        Returns:
            ClassificationResult: 분류 결과
        """
        # 비활성화 시 항상 허용
        if not self._enabled:
            return ClassificationResult(
                category="oncology",
                confidence=1.0,
                is_allowed=True,
                reason="Domain classifier disabled",
            )

        # 빈 쿼리 처리
        if not query or not query.strip():
            return ClassificationResult(
                category="unknown",
                confidence=0.0,
                is_allowed=True,
                reason="Empty query",
            )

        try:
            self._load_pipeline()

            # Zero-shot 분류 실행
            result = self._pipeline(
                query,
                self.CANDIDATE_LABELS,
                multi_label=False,
            )

            # 결과 파싱
            top_label = result["labels"][0]
            top_score = result["scores"][0]

            # 카테고리 변환
            category = self.LABEL_TO_CATEGORY.get(top_label, "unknown")
            confidence = float(top_score)

            # 허용 여부 판단
            is_allowed = category in self.ALLOWED_DOMAINS and confidence >= self.threshold

            # 경고 모드에서는 항상 허용하되 로그 남김
            if self._mode == "warn" and not is_allowed:
                logger.warning(
                    f"[DomainClassifier] Off-domain query detected: "
                    f"category={category}, confidence={confidence:.2%}, "
                    f"query={query[:100]}..."
                )
                is_allowed = True  # 경고 모드에서는 진행 허용

            reason = None
            if not is_allowed:
                reason = (
                    f"Query classified as '{category}' with {confidence:.0%} confidence. "
                    f"This system specializes in oncology (cancer research)."
                )

            return ClassificationResult(
                category=category,
                confidence=confidence,
                is_allowed=is_allowed,
                reason=reason,
            )

        except Exception as e:
            logger.error(f"[DomainClassifier] Classification failed: {e}")
            # 오류 시 허용 (fail-open)
            return ClassificationResult(
                category="error",
                confidence=0.0,
                is_allowed=True,
                reason=f"Classification error: {str(e)}",
            )

    def get_config(self) -> dict[str, Any]:
        """현재 설정 반환"""
        return {
            "name": self.name,
            "model_name": self.model_name,
            "threshold": self.threshold,
            "device": self.device,
            "enabled": self._enabled,
            "mode": self._mode,
            "candidate_labels": list(self.LABEL_TO_CATEGORY.values()),
            "allowed_domains": self.ALLOWED_DOMAINS,
        }
