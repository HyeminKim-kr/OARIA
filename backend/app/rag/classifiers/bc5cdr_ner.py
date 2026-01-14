"""BC5CDR 기반 Chemical/Disease NER 분류기

PubMedBERT를 BC5CDR 데이터셋으로 Fine-tuning한 모델을 사용합니다.
Chemical(화학물질)과 Disease(질병) 엔티티를 추출합니다.

사용법:
    from app.rag import get_classifier
    
    ner = get_classifier("bc5cdr_ner_v1")
    result = ner.extract("Cisplatin treats lung cancer.")
    
    for entity in result.entities:
        print(f"{entity.text}: {entity.label} ({entity.score:.2%})")
    # Cisplatin: Chemical (95.23%)
    # lung cancer: Disease (92.15%)
"""

from __future__ import annotations

import logging
import time
from typing import Any

from app.rag.base import ClassificationResult, NEREntity, NERResult
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
class BC5CDRNERClassifier:
    """BC5CDR 기반 Chemical/Disease NER 분류기

    PubMedBERT를 BC5CDR 데이터셋으로 Fine-tuning한 모델입니다.
    Chemical(화학물질)과 Disease(질병) 엔티티를 추출합니다.

    모델:
    - HuggingFace: vparka/cancer-ner-pubmedbert
    - 엔티티: Chemical, Disease
    - 베이스 모델: microsoft/BiomedNLP-PubMedBERT-base-uncased-abstract

    사용법:
        from app.rag import get_classifier
        ner = get_classifier("bc5cdr_ner_v1")
        result = ner.extract("Cisplatin treats lung cancer.")
        # [NEREntity(text="Cisplatin", label="Chemical", ...),
        #  NEREntity(text="lung cancer", label="Disease", ...)]
    """

    name = "bc5cdr_ner_v1"

    # 지원하는 엔티티 타입
    ENTITY_TYPES = ["Chemical", "Disease"]

    def __init__(
        self,
        model_name: str = "vparka/cancer-ner-pubmedbert",
        device: int | None = None,
        score_threshold: float = 0.5,
    ):
        """분류기 초기화

        Args:
            model_name: HuggingFace 모델 ID
            device: 디바이스 인덱스 (-1=CPU, 0+=GPU). None이면 자동 감지
            score_threshold: 엔티티 추출 최소 신뢰도 (기본 0.5)
        """
        self.model_name = model_name
        self._device = device
        self.score_threshold = score_threshold

        # Lazy loading
        self._pipeline = None

    @property
    def device(self) -> int:
        """디바이스 인덱스"""
        if self._device is None:
            self._device = _get_best_device()
        return self._device

    def _load_pipeline(self) -> None:
        """NER 파이프라인 로드 (Lazy)"""
        if self._pipeline is not None:
            return

        logger.info(f"[BC5CDR-NER] Loading model: {self.model_name}")
        start = time.perf_counter()

        try:
            from transformers import pipeline

            self._pipeline = pipeline(
                "ner",
                model=self.model_name,
                device=self.device,
                aggregation_strategy="simple",  # 토큰을 단어로 병합
            )

            elapsed = time.perf_counter() - start
            device_name = "GPU" if self.device >= 0 else "CPU"
            logger.info(f"[BC5CDR-NER] Model loaded in {elapsed:.2f}s on {device_name}")

        except Exception as e:
            logger.error(f"[BC5CDR-NER] Failed to load model: {e}")
            raise

    def extract(self, text: str) -> NERResult:
        """텍스트에서 Chemical/Disease 엔티티 추출

        Args:
            text: 엔티티를 추출할 텍스트

        Returns:
            NERResult: 추출된 엔티티 리스트와 메타데이터
        """
        if not text or not text.strip():
            return NERResult(
                entities=[],
                model=self.model_name,
                latency_ms=0.0,
            )

        start = time.perf_counter()
        self._load_pipeline()

        try:
            raw_entities = self._pipeline(text)

            # 결과 변환 및 필터링
            entities = []
            for ent in raw_entities:
                score = float(ent.get("score", 0))
                if score < self.score_threshold:
                    continue

                # entity_group 또는 label에서 레이블 추출
                label = ent.get("entity_group", ent.get("label", "Unknown"))
                # B-, I- 접두사 제거
                if label.startswith(("B-", "I-")):
                    label = label[2:]

                entities.append(
                    NEREntity(
                        text=ent.get("word", ""),
                        label=label,
                        score=score,
                        start=ent.get("start", 0),
                        end=ent.get("end", 0),
                    )
                )

            elapsed_ms = (time.perf_counter() - start) * 1000

            return NERResult(
                entities=entities,
                model=self.model_name,
                latency_ms=elapsed_ms,
            )

        except Exception as e:
            logger.error(f"[BC5CDR-NER] Extraction failed: {e}")
            return NERResult(
                entities=[],
                model=self.model_name,
                latency_ms=0.0,
            )

    def classify(self, query: str, **kwargs: Any) -> ClassificationResult:
        """기존 ClassifierProtocol 호환 - 엔티티 존재 여부로 분류

        Args:
            query: 분류할 쿼리 텍스트
            **kwargs: 추가 파라미터

        Returns:
            ClassificationResult: 엔티티가 있으면 bio_entity, 없으면 no_entity
        """
        result = self.extract(query)
        has_entities = len(result.entities) > 0

        if has_entities:
            max_score = max(e.score for e in result.entities)
            entity_summary = ", ".join(
                f"{e.text}({e.label})" for e in result.entities[:5]
            )
            reason = f"Found {len(result.entities)} entities: {entity_summary}"
        else:
            max_score = 0.0
            reason = None

        return ClassificationResult(
            category="bio_entity" if has_entities else "no_entity",
            confidence=max_score,
            is_allowed=True,  # NER은 Gate 역할이 아니므로 항상 허용
            reason=reason,
        )

    def get_config(self) -> dict[str, Any]:
        """현재 설정 반환"""
        return {
            "name": self.name,
            "model_name": self.model_name,
            "device": self.device,
            "score_threshold": self.score_threshold,
            "entity_types": self.ENTITY_TYPES,
        }
