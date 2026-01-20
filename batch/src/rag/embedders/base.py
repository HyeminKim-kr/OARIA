"""임베딩 전략 베이스 클래스

모든 임베딩 전략은 EmbedderProtocol을 구현해야 합니다.

새 임베딩 전략 추가 시:
1. 이 파일의 EmbedderProtocol을 구현하는 클래스 작성
2. @register_embedder 데코레이터 추가
3. name 속성에 구체적인 이름 지정 (예: 'openai_3small')
4. 클래스 docstring 작성 (Admin Lab UI에 표시됨)
5. __init__.py에서 import

예시:
    @register_embedder
    class MyEmbedder:
        name = "my_embedder_v1"

        def embed(self, text: str) -> list[float]:
            ...

        def embed_batch(self, texts: list[str]) -> list[list[float]]:
            ...
"""

from typing import Protocol, runtime_checkable, Any, List, Dict


@runtime_checkable
class EmbedderProtocol(Protocol):
    """임베딩 전략 인터페이스

    모든 임베딩 전략은 이 프로토콜을 구현해야 합니다.
    """

    name: str  # 레지스트리 등록 이름 (필수)
    dimension: int  # 임베딩 차원 (필수)

    def embed(self, text: str) -> List[float]:
        """단일 텍스트 임베딩

        Args:
            text: 임베딩할 텍스트

        Returns:
            임베딩 벡터 (float 리스트)
        """
        ...

    def embed_batch(
        self,
        texts: List[str],
        batch_size: int = 100,
    ) -> List[List[float]]:
        """배치 텍스트 임베딩

        Args:
            texts: 임베딩할 텍스트 리스트
            batch_size: 한 번에 처리할 텍스트 수

        Returns:
            임베딩 벡터 리스트
        """
        ...

    def get_config(self) -> Dict[str, Any]:
        """현재 설정 반환

        Returns:
            설정 딕셔너리 (name, dimension, 파라미터 등)
        """
        ...
