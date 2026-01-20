"""리랭킹 모델 기본 인터페이스"""

from typing import Protocol, runtime_checkable, Any
from app.rag.base import RerankResult


@runtime_checkable
class RerankerProtocol(Protocol):
    """리랭킹 모델 인터페이스

    모든 리랭킹 모델은 이 Protocol을 구현해야 합니다.

    필수 속성:
        name: 레지스트리 등록 이름 (고유해야 함)

    필수 메서드:
        rerank(): 검색 결과 재정렬
        get_config(): 현재 설정 반환
    """

    name: str

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
            **kwargs: 추가 옵션 (모델별로 다름)
                - content_key: 문서에서 텍스트를 가져올 키
                - min_score: 최소 점수 임계값

        Returns:
            점수 순으로 정렬된 결과 리스트
        """
        ...

    def get_config(self) -> dict[str, Any]:
        """현재 설정 반환

        Returns:
            설정 딕셔너리 (name 포함)
        """
        ...
