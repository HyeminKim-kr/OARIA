"""BGE Reranker 모델

기존 reranker_service를 래핑하여 모듈화된 인터페이스를 제공합니다.
"""

from typing import Any
from app.rag.base import RerankResult
from app.rag.registry import register_reranker
from app.services.reranker_service import reranker_service


@register_reranker
class BGERerankerV2M3:
    """BGE Reranker v2-m3 (Cross-Encoder, 다국어, 567M)

    쿼리와 문서를 함께 인코딩하여 더 정확한 관련성 점수를 계산합니다.
    초기 검색 결과를 재정렬하여 관련성 높은 문서를 상위로 올립니다.

    스펙:
    - 모델: bge-reranker-v2-m3
    - 파라미터: 567M
    - 다국어 지원 (한국어 포함)
    - 로컬 GPU 실행, 무료
    """

    name = "bge_reranker_v2m3"

    # 사용 가능한 모델들
    AVAILABLE_MODELS = [
        "bge-reranker-v2-m3",  # 다국어, 567M (기본)
        "bge-reranker-large",  # 영어 최적화, 560M
        "bge-reranker-base",   # 경량 버전, 278M
    ]

    def __init__(self, model_name: str = "bge-reranker-v2-m3"):
        """
        Args:
            model_name: 사용할 모델 이름
        """
        self.model_name = model_name
        self._service = reranker_service

    def rerank(
        self,
        query: str,
        documents: list[dict[str, Any]],
        top_k: int | None = None,
        **kwargs,
    ) -> list[RerankResult]:
        """검색 결과 재정렬

        Args:
            query: 사용자 질문
            documents: 검색된 문서 리스트
            top_k: 상위 N개만 반환 (None이면 전체)
            **kwargs:
                - content_key: 문서에서 텍스트를 가져올 키 (기본: "content")
                - min_score: 최소 점수 임계값

        Returns:
            점수 순으로 정렬된 결과 리스트
        """
        content_key = kwargs.get("content_key", "content")
        min_score = kwargs.get("min_score")

        # reranker_service 호출
        raw_results = self._service.rerank(
            query=query,
            documents=documents,
            content_key=content_key,
            top_k=top_k,
            min_score=min_score,
            model_name=self.model_name,
        )

        # RerankResult로 변환
        return [
            RerankResult(
                index=r.index,
                score=r.score,
                document=r.document,
                original_score=r.document.get("score"),
            )
            for r in raw_results
        ]

    def get_config(self) -> dict[str, Any]:
        """현재 설정 반환"""
        status = self._service.get_status()
        return {
            "name": self.name,
            "model_name": self.model_name,
            "available_models": self.AVAILABLE_MODELS,
            "enabled": status.get("enabled", False),
            "model_loaded": status.get("model_loaded", False),
        }
