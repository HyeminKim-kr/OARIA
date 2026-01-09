"""청킹 전략 기본 인터페이스"""

from typing import Protocol, runtime_checkable, Any
from app.rag.base import Chunk


@runtime_checkable
class ChunkerProtocol(Protocol):
    """청킹 전략 인터페이스

    모든 청킹 전략은 이 Protocol을 구현해야 합니다.

    필수 속성:
        name: 레지스트리 등록 이름 (고유해야 함)

    필수 메서드:
        chunk(): 텍스트를 청크로 분할
        get_config(): 현재 설정 반환
    """

    name: str

    def chunk(self, text: str, **kwargs) -> list[Chunk]:
        """텍스트를 청크로 분할

        Args:
            text: 분할할 텍스트
            **kwargs: 추가 옵션 (전략별로 다름)

        Returns:
            청크 리스트
        """
        ...

    def get_config(self) -> dict[str, Any]:
        """현재 설정 반환

        Returns:
            설정 딕셔너리 (name 포함)
        """
        ...
