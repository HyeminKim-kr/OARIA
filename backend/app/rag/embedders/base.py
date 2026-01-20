"""임베딩 모델 기본 인터페이스"""

from typing import Protocol, runtime_checkable, Any


@runtime_checkable
class EmbedderProtocol(Protocol):
    """임베딩 모델 인터페이스

    모든 임베딩 모델은 이 Protocol을 구현해야 합니다.

    필수 속성:
        name: 레지스트리 등록 이름 (고유해야 함)
        dimensions: 임베딩 벡터 차원 수

    필수 메서드:
        embed(): 단일 텍스트 임베딩
        embed_batch(): 복수 텍스트 임베딩
        get_config(): 현재 설정 반환
    """

    name: str
    dimensions: int

    def embed(self, text: str, **kwargs) -> list[float]:
        """단일 텍스트 임베딩

        Args:
            text: 임베딩할 텍스트

        Returns:
            임베딩 벡터
        """
        ...

    def embed_batch(self, texts: list[str], **kwargs) -> list[list[float]]:
        """복수 텍스트 임베딩

        Args:
            texts: 임베딩할 텍스트 리스트

        Returns:
            임베딩 벡터 리스트
        """
        ...

    def get_config(self) -> dict[str, Any]:
        """현재 설정 반환

        Returns:
            설정 딕셔너리 (name, dimensions 포함)
        """
        ...
