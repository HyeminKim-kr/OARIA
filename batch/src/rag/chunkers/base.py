"""청킹 전략 베이스 클래스

모든 청킹 전략은 ChunkerProtocol을 구현해야 합니다.

새 청킹 전략 추가 시:
1. 이 파일의 ChunkerProtocol을 구현하는 클래스 작성
2. @register_chunker 데코레이터 추가
3. name 속성에 구체적인 이름 지정 (예: 'fixed_char_1000_200')
4. 클래스 docstring 작성 (Admin Lab UI에 표시됨)
5. __init__.py에서 import

예시:
    @register_chunker
    class MyChunker:
        name = "my_chunker_v1"

        def chunk(self, fulltext, sections, paper_id, title, year=None):
            ...
"""

from typing import Protocol, runtime_checkable, Any, Optional, List, Dict
from ..base import ChunkingResult


@runtime_checkable
class ChunkerProtocol(Protocol):
    """청킹 전략 인터페이스

    모든 청킹 전략은 이 프로토콜을 구현해야 합니다.
    """

    name: str  # 레지스트리 등록 이름 (필수)

    def chunk(
        self,
        fulltext: str,
        sections: List[Dict],
        paper_id: str,
        title: str,
        year: Optional[int] = None,
    ) -> ChunkingResult:
        """텍스트를 청크로 분할

        Args:
            fulltext: 논문 전체 텍스트
            sections: 섹션 정보 리스트 [{"name": "abstract", "offset_start": 0, "offset_end": 1000}, ...]
            paper_id: 논문 ID (예: pmid:12345678)
            title: 논문 제목
            year: 출판 연도 (임베딩 prefix용)

        Returns:
            ChunkingResult: 청킹 결과 (chunks, sections, 통계 등)
        """
        ...

    def get_config(self) -> Dict[str, Any]:
        """현재 설정 반환

        Returns:
            설정 딕셔너리 (name, 파라미터 등)
        """
        ...
