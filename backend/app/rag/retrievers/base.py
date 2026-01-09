"""검색 전략 기본 인터페이스"""

from typing import Protocol, runtime_checkable, Any
from app.rag.base import SearchResult


@runtime_checkable
class RetrieverProtocol(Protocol):
    """검색 전략 인터페이스

    모든 검색 전략은 이 Protocol을 구현해야 합니다.

    필수 속성:
        name: 레지스트리 등록 이름 (고유해야 함)

    필수 메서드:
        search(): 쿼리로 검색
        get_config(): 현재 설정 반환
    """

    name: str

    def search(
        self,
        query: str,
        query_vector: list[float],
        limit: int = 5,
        **kwargs,
    ) -> list[SearchResult]:
        """벡터 검색 수행

        Args:
            query: 검색 쿼리 텍스트
            query_vector: 쿼리 임베딩 벡터
            limit: 반환할 결과 수
            **kwargs: 추가 옵션 (전략별로 다름)
                - alpha: 하이브리드 검색 시 벡터/키워드 비중
                - year_from, year_to: 연도 필터
                - sections: 섹션 필터

        Returns:
            검색 결과 리스트
        """
        ...

    def get_config(self) -> dict[str, Any]:
        """현재 설정 반환

        Returns:
            설정 딕셔너리 (name 포함)
        """
        ...
