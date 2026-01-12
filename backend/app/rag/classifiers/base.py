"""분류기 프로토콜 정의"""

from typing import Any, Protocol, runtime_checkable

from app.rag.base import ClassificationResult


@runtime_checkable
class ClassifierProtocol(Protocol):
    """도메인 분류기 인터페이스

    쿼리가 특정 도메인에 속하는지 분류합니다.
    Gate 1에서 Off-domain 쿼리를 감지하는 데 사용됩니다.

    필수 속성:
        name: 레지스트리 등록 이름 (고유해야 함)

    필수 메서드:
        classify(): 쿼리 도메인 분류
        get_config(): 현재 설정 반환
    """

    name: str

    def classify(
        self,
        query: str,
        **kwargs: Any,
    ) -> ClassificationResult:
        """쿼리 도메인 분류

        Args:
            query: 분류할 쿼리 텍스트
            **kwargs: 추가 파라미터

        Returns:
            ClassificationResult: 분류 결과 (category, confidence, is_allowed, reason)
        """
        ...

    def get_config(self) -> dict[str, Any]:
        """현재 설정 반환

        Returns:
            설정 딕셔너리 (name, model, threshold 등)
        """
        ...
