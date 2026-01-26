"""Study Plan RAG 타입 정의"""

from dataclasses import dataclass, field


@dataclass
class SnippetResult:
    """검색된 스니펫"""

    snippet_id: str
    paper_id: str
    section: str  # "abstract", "methods", "results", "discussion", "web"
    text: str
    relevance_score: float
    offset_start: int = 0  # Optional for web/EPMC results
    offset_end: int = 0  # Optional for web/EPMC results
    text_version: str = "v1"


@dataclass
class PaperResult:
    """검색된 논문 결과"""

    paper_id: str
    title: str
    journal: str
    year: int
    snippets: list[SnippetResult] = field(default_factory=list)
    source: str = "weaviate"  # "weaviate", "epmc", "tavily"

    # 논문별 평균 관련성 점수
    @property
    def relevance_score(self) -> float:
        if not self.snippets:
            return 0.0
        return sum(s.relevance_score for s in self.snippets) / len(self.snippets)

    # 논문별 최고 관련성 점수
    @property
    def max_relevance_score(self) -> float:
        if not self.snippets:
            return 0.0
        return max(s.relevance_score for s in self.snippets)


@dataclass
class SearchResult:
    """검색 결과 집계"""

    papers: list[PaperResult]
    total_snippets: int
    coverage_score: float  # 0-1: 검색 범위 충분성
    queries_used: list[str]
    latency_ms: int

    # 전체 논문 수
    @property
    def total_papers(self) -> int:
        return len(self.papers)

    # dict 변환 (state 저장용)
    def to_prior_studies(self) -> list[dict]:
        """StudyPlanState.prior_studies 형식으로 변환"""
        return [
            {
                "paper_id": p.paper_id,
                "title": p.title,
                "journal": p.journal,
                "year": p.year,
                "relevance_score": p.max_relevance_score,
                "abstract": p.snippets[0].text if p.snippets else "",
                "section": p.snippets[0].section if p.snippets else "",
                "chunk_id": p.snippets[0].snippet_id if p.snippets else "",
                "offset_start": p.snippets[0].offset_start if p.snippets else 0,
                "offset_end": p.snippets[0].offset_end if p.snippets else 0,
                "text_version": p.snippets[0].text_version if p.snippets else "v1",
                # Evidence 구축용 추가 스니펫
                "all_snippets": [
                    {
                        "snippet_id": s.snippet_id,
                        "section": s.section,
                        "text": s.text,
                        "offset_start": s.offset_start,
                        "offset_end": s.offset_end,
                        "relevance_score": s.relevance_score,
                    }
                    for s in p.snippets
                ],
            }
            for p in self.papers
        ]
