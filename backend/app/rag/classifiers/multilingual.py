"""Multilingual Zero-shot 도메인 분류기

다국어 mDeBERTa 모델을 사용하여 한국어/영어 모두 잘 처리합니다.
PubMedBERT 분류기의 한국어 한계를 극복하기 위한 대안입니다.

스펙:
- 모델: MoritzLaurer/mDeBERTa-v3-base-xnli-multilingual-nli-2mil7
- 지원 언어: 100+ (한국어, 영어, 일본어, 중국어 등)
- 분류 클래스: oncology, cardiology, neurology, general medicine, non-medical
- 키워드 프리필터: 빠른 oncology 탐지

사용법:
    from app.rag import get_classifier
    classifier = get_classifier("multilingual_v1")
    result = classifier.classify("EGFR 변이 폐암 치료")
"""

import logging
import os
import time
from typing import Any

from app.rag.base import ClassificationResult
from app.rag.registry import register_classifier

logger = logging.getLogger(__name__)


def _get_best_device() -> int:
    """최적의 디바이스 선택"""
    try:
        import torch

        if torch.cuda.is_available():
            return 0  # GPU
        elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            return 0  # Apple Silicon
    except ImportError:
        pass
    return -1  # CPU


@register_classifier
class MultilingualDomainClassifier:
    """다국어 Zero-shot Oncology 도메인 분류기

    MoritzLaurer/mDeBERTa-v3-base-xnli-multilingual-nli-2mil7 모델을 사용하여
    한국어와 영어 모두 정확하게 분류합니다.

    장점:
    - 한국어 쿼리를 정확하게 oncology로 분류
    - 100+ 언어 지원
    - 키워드 프리필터로 빠른 분류

    단점:
    - 첫 로딩 시 모델 다운로드 필요 (~860MB)
    - bart-large-mnli보다 약간 느림

    사용법:
        from app.rag import get_classifier
        classifier = get_classifier("multilingual_v1")
        result = classifier.classify("면역항암제의 부작용")
    """

    name = "multilingual_v1"

    # 분류 후보 레이블 - 더 명확하게 구분되도록 설계
    CANDIDATE_LABELS = [
        # Oncology - cancer specific terms
        "oncology cancer tumor chemotherapy immunotherapy radiation targeted therapy carcinoma lymphoma leukemia melanoma sarcoma metastasis",
        # Cardiology - heart specific
        "cardiology heart cardiac cardiovascular arrhythmia hypertension coronary myocardial infarction",
        # Neurology - brain/nerve specific
        "neurology brain nervous system stroke epilepsy alzheimer parkinson dementia seizure",
        # General medicine - actual medical topics
        "general medicine doctor hospital patient diagnosis symptoms prescription medication clinic",
        # Non-medical - everyday life, NOT medicine at all
        "not medical question about daily life cooking recipe food weather sports movie music travel shopping pizza restaurant",
    ]

    # 레이블 -> 카테고리 매핑
    LABEL_TO_CATEGORY = {
        "oncology cancer tumor chemotherapy immunotherapy radiation targeted therapy carcinoma lymphoma leukemia melanoma sarcoma metastasis": "oncology",
        "cardiology heart cardiac cardiovascular arrhythmia hypertension coronary myocardial infarction": "cardiology",
        "neurology brain nervous system stroke epilepsy alzheimer parkinson dementia seizure": "neurology",
        "general medicine doctor hospital patient diagnosis symptoms prescription medication clinic": "general_medicine",
        "not medical question about daily life cooking recipe food weather sports movie music travel shopping pizza restaurant": "non_medical",
    }

    # 허용되는 도메인
    ALLOWED_DOMAINS = ["oncology"]

    # Oncology 키워드 (한국어 + 영어) - 키워드 매칭으로 빠른 분류
    ONCOLOGY_KEYWORDS = [
        # Korean cancer types
        "암", "종양", "악성", "양성", "전이", "재발",
        "폐암", "유방암", "대장암", "위암", "간암", "췌장암", "난소암", "전립선암",
        "백혈병", "림프종", "골수종", "육종", "흑색종", "뇌종양", "갑상선암",
        # Korean treatments
        "항암", "화학요법", "방사선", "면역요법", "면역항암", "표적치료", "세포치료",
        "수술", "절제", "생검", "조직검사",
        # Korean biomarkers & terms
        "종양표지자", "암표지자", "병기", "스테이징",
        # English cancer types
        "cancer", "tumor", "tumour", "carcinoma", "adenocarcinoma",
        "lymphoma", "leukemia", "leukaemia", "melanoma", "sarcoma",
        "neoplasm", "malignant", "metastasis", "metastatic",
        # English treatments
        "chemotherapy", "radiotherapy", "immunotherapy", "targeted therapy",
        "oncology", "oncologist",
        # Biomarkers
        "egfr", "kras", "braf", "her2", "brca", "pd-1", "pd-l1", "alk", "ros1",
        "tp53", "pik3ca", "msi", "tmb",
    ]

    def __init__(
        self,
        model_name: str = "MoritzLaurer/mDeBERTa-v3-base-xnli-multilingual-nli-2mil7",
        threshold: float = 0.3,
        device: int | None = None,
    ):
        """분류기 초기화

        Args:
            model_name: 다국어 Zero-shot 분류 모델
            threshold: 허용 도메인 판정 임계값 (기본 0.3)
            device: 디바이스 인덱스 (-1=CPU, 0+=GPU). None이면 자동 감지
        """
        self.model_name = model_name
        self.threshold = threshold
        self._device = device

        # Lazy loading
        self._pipeline = None
        self._enabled = os.getenv("DOMAIN_CLASSIFIER_ENABLED", "true").lower() == "true"
        self._mode = os.getenv("DOMAIN_CLASSIFIER_MODE", "warn")

    @property
    def device(self) -> int:
        """디바이스 인덱스"""
        if self._device is None:
            self._device = _get_best_device()
        return self._device

    def _check_oncology_keywords(self, query: str) -> bool:
        """Fast keyword-based oncology detection (Korean + English)."""
        query_lower = query.lower()
        for keyword in self.ONCOLOGY_KEYWORDS:
            if keyword.lower() in query_lower:
                return True
        return False

    def _load_pipeline(self) -> None:
        """Zero-shot 분류 파이프라인 로드 (Lazy)"""
        if self._pipeline is not None:
            return

        logger.info(f"[MultilingualClassifier] Loading model: {self.model_name}")
        start = time.perf_counter()

        try:
            from transformers import pipeline

            self._pipeline = pipeline(
                "zero-shot-classification",
                model=self.model_name,
                device=self.device,
            )

            elapsed = time.perf_counter() - start
            device_name = "GPU/MPS" if self.device >= 0 else "CPU"
            logger.info(f"[MultilingualClassifier] Model loaded in {elapsed:.2f}s on {device_name}")

        except Exception as e:
            logger.error(f"[MultilingualClassifier] Failed to load model: {e}")
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

        # Fast path: 키워드 기반 oncology 탐지
        if self._check_oncology_keywords(query):
            logger.debug(f"[MultilingualClassifier] Oncology keyword detected: {query[:50]}...")
            return ClassificationResult(
                category="oncology",
                confidence=0.95,
                is_allowed=True,
                reason="Oncology keyword detected",
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
                    f"[MultilingualClassifier] Off-domain query: "
                    f"category={category}, confidence={confidence:.2%}, "
                    f"query={query[:100]}..."
                )
                is_allowed = True

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
            logger.error(f"[MultilingualClassifier] Classification failed: {e}")
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
