"""하이브리드 검색 전략

기존 weaviate_service를 래핑하여 모듈화된 인터페이스를 제공합니다.
벡터 검색 + 키워드 검색을 결합한 하이브리드 검색을 수행합니다.
"""

from typing import Any
from app.rag.base import SearchResult
from app.rag.registry import register_retriever
from app.services.weaviate_service import weaviate_service


@register_retriever
class HybridAlpha70Retriever:
    """하이브리드 검색 (벡터 70% + 키워드 30%)

    의미적 유사도(벡터)와 정확한 용어 매칭(BM25)을 결합합니다.
    "EGFR mutation"처럼 정확한 의학 용어가 중요한 경우에 효과적입니다.

    설정:
    - alpha: 0.7 (벡터 70%, BM25 30%)
    - alpha 조절 가능: 0=키워드만, 1=벡터만
    """

    name = "hybrid_alpha70"

    def __init__(self, alpha: float = 0.7):
        """
        Args:
            alpha: 벡터/키워드 비중 (기본: 0.7 = 벡터 70%)
        """
        self.alpha = alpha
        self._service = weaviate_service

    def search(
        self,
        query: str,
        query_vector: list[float],
        limit: int = 5,
        **kwargs,
    ) -> list[SearchResult]:
        """하이브리드 검색 수행

        Args:
            query: 검색 쿼리 텍스트
            query_vector: 쿼리 임베딩 벡터
            limit: 반환할 결과 수
            **kwargs:
                - alpha: 벡터/키워드 비중 (기본값 사용 가능)
                - year_from: 연도 필터 (이상)
                - year_to: 연도 필터 (이하)
                - sections: 섹션 필터 리스트

        Returns:
            검색 결과 리스트
        """
        alpha = kwargs.get("alpha", self.alpha)
        year_from = kwargs.get("year_from")
        year_to = kwargs.get("year_to")
        sections = kwargs.get("sections")

        # weaviate_service 호출
        raw_results = self._service.search_hybrid(
            query=query,
            query_vector=query_vector,
            limit=limit,
            alpha=alpha,
            year_from=year_from,
            year_to=year_to,
            sections=sections,
        )

        # SearchResult로 변환
        return [
            SearchResult(
                content=r.get("content", ""),
                score=r.get("score", 0.0),
                paper_id=r.get("paperId", ""),
                chunk_id=r.get("uuid", ""),
                title=r.get("title", ""),
                section=r.get("section", ""),
                metadata={
                    "year": r.get("year"),
                    "chunk_index": r.get("chunkIndex"),
                    "retriever": self.name,
                    "alpha": alpha,
                },
            )
            for r in raw_results
        ]

    def get_config(self) -> dict[str, Any]:
        """현재 설정 반환"""
        return {
            "name": self.name,
            "alpha": self.alpha,
            "search_type": "hybrid",
        }
