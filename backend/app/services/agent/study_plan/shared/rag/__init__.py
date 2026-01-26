"""Study Plan Agent 전용 RAG 모듈

기존 RAG 서비스를 활용하되, 에이전트 사용에 맞게 래핑합니다.
- 다중 쿼리 검색
- 섹션별 검색
- Evidence 추출에 최적화
"""

from .search import StudySearchService, study_search_service
from .types import SearchResult, PaperResult

__all__ = [
    "StudySearchService",
    "study_search_service",
    "SearchResult",
    "PaperResult",
]
