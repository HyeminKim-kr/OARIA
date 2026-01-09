"""Reranker 서비스

BGE Reranker를 사용한 검색 결과 재정렬
- Cross-Encoder 기반으로 query-document 쌍의 관련성 점수 계산
- 벡터 검색 결과를 더 정확하게 재정렬
- MPS (Apple Silicon) / CUDA GPU 가속 지원
- FP16 반정밀도 추론으로 성능 최적화
"""

import os
import time
from dataclasses import dataclass
from typing import Any

import torch


@dataclass
class RerankResult:
    """재정렬된 결과"""

    index: int  # 원본 인덱스
    score: float  # Reranker 점수 (0~1, 높을수록 관련성 높음)
    document: dict[str, Any]  # 원본 문서


def _get_best_device() -> str:
    """최적의 디바이스 선택 (CUDA > MPS > CPU)"""
    if torch.cuda.is_available():
        return "cuda"
    elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        return "mps"
    return "cpu"


class RerankerService:
    """BGE Reranker 서비스

    Lazy loading으로 모델을 필요할 때만 로드합니다.
    첫 호출 시 모델 다운로드가 발생할 수 있습니다 (~1GB).

    최적화:
    - MPS (Apple Silicon) / CUDA GPU 가속
    - FP16 반정밀도 추론 (GPU 사용 시)
    """

    # 사용 가능한 모델들
    MODELS = {
        "bge-reranker-v2-m3": "BAAI/bge-reranker-v2-m3",  # 다국어, 567M
        "bge-reranker-large": "BAAI/bge-reranker-large",  # 영어 최적화, 560M
        "bge-reranker-base": "BAAI/bge-reranker-base",  # 경량 버전, 278M
    }

    DEFAULT_MODEL = "bge-reranker-v2-m3"

    def __init__(self):
        self._model = None
        self._model_name = None
        self._device = None
        self._use_fp16 = False
        self._enabled = True  # 환경변수로 비활성화 가능

    @property
    def is_enabled(self) -> bool:
        """Reranker 활성화 여부"""
        return self._enabled and os.getenv("RERANKER_ENABLED", "true").lower() == "true"

    @property
    def model_name(self) -> str:
        """현재 사용 중인 모델 이름"""
        return self._model_name or self.DEFAULT_MODEL

    @property
    def device(self) -> str:
        """현재 사용 중인 디바이스"""
        return self._device or "cpu"

    def _load_model(self, model_name: str | None = None):
        """모델 로드 (Lazy loading) with GPU 가속"""
        if self._model is not None and (model_name is None or model_name == self._model_name):
            return

        from sentence_transformers import CrossEncoder

        model_key = model_name or self.DEFAULT_MODEL
        model_path = self.MODELS.get(model_key, model_key)

        # 최적의 디바이스 선택
        self._device = _get_best_device()

        print(f"[Reranker] Loading model: {model_path} on {self._device}")
        start = time.perf_counter()

        # CrossEncoder 로드
        self._model = CrossEncoder(
            model_path,
            max_length=512,
            device=self._device,
        )

        # GPU 사용 시 FP16 변환 시도
        if self._device in ("cuda", "mps"):
            try:
                self._model.model.half()
                self._use_fp16 = True
                print(f"[Reranker] Using FP16 on {self._device}")
            except Exception as e:
                print(f"[Reranker] FP16 failed, using FP32: {e}")
                self._use_fp16 = False

        self._model_name = model_key

        elapsed = time.perf_counter() - start
        print(f"[Reranker] Model loaded in {elapsed:.2f}s on {self._device}")

    def rerank(
        self,
        query: str,
        documents: list[dict[str, Any]],
        content_key: str = "content",
        top_k: int | None = None,
        min_score: float | None = None,
        model_name: str | None = None,
    ) -> list[RerankResult]:
        """검색 결과 재정렬

        Args:
            query: 사용자 질문
            documents: 검색된 문서 리스트
            content_key: 문서에서 텍스트를 가져올 키
            top_k: 상위 N개만 반환 (None이면 전체)
            min_score: 최소 점수 임계값 (None이면 필터링 안 함)
            model_name: 사용할 모델 (None이면 기본 모델)

        Returns:
            점수 순으로 정렬된 결과 리스트
        """
        if not documents:
            return []

        if not self.is_enabled:
            # Reranker 비활성화 시 원본 순서 유지
            return [
                RerankResult(index=i, score=1.0, document=doc)
                for i, doc in enumerate(documents)
            ]

        # 모델 로드
        self._load_model(model_name)

        # Query-Document 쌍 생성
        pairs = []
        for doc in documents:
            content = doc.get(content_key, "")
            if isinstance(content, str) and content.strip():
                pairs.append((query, content))
            else:
                pairs.append((query, ""))

        # 점수 계산
        start = time.perf_counter()
        scores = self._model.predict(pairs)
        elapsed_ms = int((time.perf_counter() - start) * 1000)

        print(f"[Reranker] Scored {len(pairs)} documents in {elapsed_ms}ms")

        # 결과 생성
        results = []
        for i, (doc, score) in enumerate(zip(documents, scores)):
            # score를 0~1 범위로 정규화 (sigmoid 이미 적용됨)
            normalized_score = float(score)

            if min_score is not None and normalized_score < min_score:
                continue

            results.append(RerankResult(
                index=i,
                score=normalized_score,
                document=doc,
            ))

        # 점수 순 정렬 (내림차순)
        results.sort(key=lambda x: x.score, reverse=True)

        # top_k 적용
        if top_k is not None:
            results = results[:top_k]

        return results

    def get_status(self) -> dict[str, Any]:
        """서비스 상태 반환"""
        return {
            "enabled": self.is_enabled,
            "model_loaded": self._model is not None,
            "model_name": self._model_name,
            "device": self._device,
            "use_fp16": self._use_fp16,
            "available_models": list(self.MODELS.keys()),
        }


# 싱글톤 인스턴스
reranker_service = RerankerService()
