"""Study Plan Agent v3 - Search Types

3-tier 검색 스택과 Decision Point를 위한 타입 정의
"""

from dataclasses import dataclass, field
from enum import IntEnum, Enum
from typing import Literal


class SearchTier(IntEnum):
    """검색 티어 (승격 순서)"""

    RAG = 1  # Weaviate 벡터 검색
    EPMC = 2  # Europe PMC API
    WEB = 3  # Tavily Web Search


class SearchObjective(str, Enum):
    """검색 목적 (DP1 Router용)"""

    MECHANISM = "mechanism"  # 가설 뒷받침 기전 연구
    PROTOCOL_CONTROLS = "protocol_controls"  # 실험 프로토콜, 대조군
    EVIDENCE_STRENGTH = "evidence_strength"  # 근거 보강


class ClaimType(str, Enum):
    """Evidence 유형"""

    MECHANISM = "mechanism"  # 기전 설명
    PROTOCOL = "protocol"  # 실험 방법론
    CONTROL = "control"  # 대조군 정보
    MEASUREMENT = "measurement"  # 측정 방법
    RESULT = "result"  # 실험 결과


@dataclass
class EvidenceSnippetV3:
    """v3 Evidence Snippet - 3-tier 통합 스키마

    모든 티어(RAG, EPMC, Web)의 검색 결과를 통합 포맷으로 저장
    """

    # 필수 필드
    snippet_id: str
    text: str
    source_tier: SearchTier
    source_tool: str  # "weaviate", "europe_pmc", "tavily"
    claim_type: ClaimType

    # 출처 정보 (티어별로 다름)
    paper_id: str | None = None  # RAG, EPMC
    pmc_id: str | None = None  # EPMC only
    url: str | None = None  # Web only

    # 메타데이터
    title: str = ""
    journal: str = ""
    year: int | None = None
    section: str = ""  # abstract, methods, results, discussion

    # 점수
    relevance_score: float = 0.0
    confidence: float = 0.0  # LLM 평가 신뢰도

    # 추가 정보
    offset_start: int = 0
    offset_end: int = 0
    text_version: str = "v1"

    def to_dict(self) -> dict:
        """State 저장용 dict 변환"""
        return {
            "snippet_id": self.snippet_id,
            "text": self.text,
            "source_tier": self.source_tier.value,
            "source_tool": self.source_tool,
            "claim_type": self.claim_type.value,
            "paper_id": self.paper_id,
            "pmc_id": self.pmc_id,
            "url": self.url,
            "title": self.title,
            "journal": self.journal,
            "year": self.year,
            "section": self.section,
            "relevance_score": self.relevance_score,
            "confidence": self.confidence,
            "offset_start": self.offset_start,
            "offset_end": self.offset_end,
            "text_version": self.text_version,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "EvidenceSnippetV3":
        """dict에서 복원"""
        return cls(
            snippet_id=data["snippet_id"],
            text=data["text"],
            source_tier=SearchTier(data["source_tier"]),
            source_tool=data["source_tool"],
            claim_type=ClaimType(data["claim_type"]),
            paper_id=data.get("paper_id"),
            pmc_id=data.get("pmc_id"),
            url=data.get("url"),
            title=data.get("title", ""),
            journal=data.get("journal", ""),
            year=data.get("year"),
            section=data.get("section", ""),
            relevance_score=data.get("relevance_score", 0.0),
            confidence=data.get("confidence", 0.0),
            offset_start=data.get("offset_start", 0),
            offset_end=data.get("offset_end", 0),
            text_version=data.get("text_version", "v1"),
        )


@dataclass
class QueryPlan:
    """검색 쿼리 계획 (EPMC/Web 검색용)"""

    objective: SearchObjective
    primary_query: str
    fallback_queries: list[str] = field(default_factory=list)
    filters: dict = field(default_factory=dict)  # year_from, open_access_only 등

    def to_dict(self) -> dict:
        return {
            "objective": self.objective.value,
            "primary_query": self.primary_query,
            "fallback_queries": self.fallback_queries,
            "filters": self.filters,
        }


# ========================================
# Decision Point Types
# ========================================


@dataclass
class DP1RouterInput:
    """DP1 (검색 승격) 라우터 입력"""

    current_tier: SearchTier
    coverage_score: float  # 0-1
    evidence_density: int  # snippet 수
    test_questions: list[str]
    answered_questions: list[str]
    web_budget_remaining: int
    epmc_budget_remaining: int


DP1Decision = Literal["proceed", "upgrade_to_epmc", "upgrade_to_web", "skip_web_limit"]


@dataclass
class DP1RouterOutput:
    """DP1 (검색 승격) 라우터 출력"""

    decision: DP1Decision
    reason: str
    next_tier: SearchTier | None = None
    objective: SearchObjective | None = None
    query_plan: QueryPlan | None = None

    def to_dict(self) -> dict:
        return {
            "decision": self.decision,
            "reason": self.reason,
            "next_tier": self.next_tier.value if self.next_tier else None,
            "objective": self.objective.value if self.objective else None,
            "query_plan": self.query_plan.to_dict() if self.query_plan else None,
        }


# DP2 Types (Critique 전략)

DP2Decision = Literal[
    "redesign",  # 설계 재작업
    "search_for_controls",  # 추가 검색
    "ask_user",  # 사용자 질문
    "accept_minor_issues",  # 경미한 이슈 수용
]


@dataclass
class DP2RouterInput:
    """DP2 (Critique 전략) 라우터 입력"""

    quality_score: float
    missing_controls: list[str]  # vehicle, positive, rescue
    evidence_gaps: list[str]  # 빈약한 근거 영역
    feasibility_conflicts: list[str]  # 실현가능성 문제
    unclear_elements: list[str]  # 모델/assay 불명확
    search_budget_remaining: int
    loop_count: int  # DP2 루프 횟수 (최대 2)
    previous_gaps_searched: list[str]  # 이미 검색한 gap (같은 gap 연속 검색 금지)


@dataclass
class DP2RouterOutput:
    """DP2 (Critique 전략) 라우터 출력"""

    decision: DP2Decision
    reason: str
    target_gaps: list[str] = field(default_factory=list)  # search_for_controls용
    user_questions: list[str] = field(default_factory=list)  # ask_user용 (최대 3개)

    def to_dict(self) -> dict:
        return {
            "decision": self.decision,
            "reason": self.reason,
            "target_gaps": self.target_gaps,
            "user_questions": self.user_questions,
        }


# DP3 Types (Plan A/B 분기)

DP3Decision = Literal[
    "single_plan",  # Plan A만 생성
    "plan_a_b",  # Plan A + B 동시 생성
    "plan_b_only",  # Plan B만 생성 (제약으로 인해)
]


@dataclass
class DP3RouterInput:
    """DP3 (Plan A/B 분기) 라우터 입력"""

    quality_score: float
    approval_required: bool
    web_limit_exceeded: bool  # Web 한도 초과로 skip 했는지
    evidence_sufficient: bool  # 근거가 충분한지
    high_cost_experiment: bool  # 고비용 실험인지
    ethics_required: bool  # 윤리 승인 필요 여부
    explicit_constraints: list[str]  # 명시적 제약 조건


@dataclass
class DP3RouterOutput:
    """DP3 (Plan A/B 분기) 라우터 출력"""

    decision: DP3Decision
    reason: str
    plan_config: dict = field(default_factory=dict)  # 추가 설정

    def to_dict(self) -> dict:
        return {
            "decision": self.decision,
            "reason": self.reason,
            "plan_config": self.plan_config,
        }


# ========================================
# Search Result Types
# ========================================


@dataclass
class TierSearchResult:
    """단일 티어 검색 결과"""

    tier: SearchTier
    snippets: list[EvidenceSnippetV3]
    total_found: int
    coverage_score: float
    queries_used: list[str]
    latency_ms: int
    cached: bool = False

    @property
    def evidence_density(self) -> int:
        """검색된 스니펫 수"""
        return len(self.snippets)


@dataclass
class MultiTierSearchResult:
    """다중 티어 검색 종합 결과"""

    tier_results: dict[SearchTier, TierSearchResult]
    final_snippets: list[EvidenceSnippetV3]  # 모든 티어 통합
    highest_tier_used: SearchTier
    total_coverage_score: float
    dp1_decisions: list[DP1RouterOutput]  # 승격 결정 이력

    def to_state_dict(self) -> dict:
        """State 저장용 변환"""
        return {
            "tier_results": {
                tier.value: {
                    "tier": tier.value,
                    "total_found": result.total_found,
                    "snippet_count": result.evidence_density,
                    "coverage_score": result.coverage_score,
                    "queries_used": result.queries_used,
                    "latency_ms": result.latency_ms,
                    "cached": result.cached,
                }
                for tier, result in self.tier_results.items()
            },
            "final_snippets": [s.to_dict() for s in self.final_snippets],
            "highest_tier_used": self.highest_tier_used.value,
            "total_coverage_score": self.total_coverage_score,
            "dp1_decisions": [d.to_dict() for d in self.dp1_decisions],
        }
