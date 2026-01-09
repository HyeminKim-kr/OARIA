"""리랭킹 없음 (Passthrough)

벤치마크 및 A/B 테스트를 위해 리랭킹을 적용하지 않는 전략입니다.
검색 결과를 원본 순서 그대로 반환합니다.
"""

from typing import Any
from app.rag.base import RerankResult
from app.rag.registry import register_reranker


@register_reranker
class NoReranker:
    """리랭킹 없음 (Baseline)

    검색 결과를 재정렬하지 않고 벡터 검색 순서 그대로 반환합니다.
    A/B 테스트에서 리랭킹 효과를 비교할 때 baseline으로 사용합니다.
    응답 속도가 빠르지만 관련성 정확도는 낮을 수 있습니다.
    """

    name = "none"

    def __init__(self):
        pass

    def rerank(
        self,
        query: str,
        documents: list[dict[str, Any]],
        top_k: int | None = None,
        **kwargs,
    ) -> list[RerankResult]:
        """원본 순서 그대로 반환

        Args:
            query: 사용자 질문 (사용하지 않음)
            documents: 검색된 문서 리스트
            top_k: 상위 N개만 반환 (None이면 전체)
            **kwargs: 무시됨

        Returns:
            원본 순서대로 결과 리스트
        """
        results = [
            RerankResult(
                index=i,
                score=1.0,  # 고정 점수
                document=doc,
                original_score=doc.get("score"),
            )
            for i, doc in enumerate(documents)
        ]

        if top_k is not None:
            results = results[:top_k]

        return results

    def get_config(self) -> dict[str, Any]:
        """현재 설정 반환"""
        return {
            "name": self.name,
            "description": "No reranking (passthrough)",
        }
