"""Search 관련 타입 정의

v3 3-tier 검색 및 Decision Point용 타입들.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class SearchTier(int, Enum):
    """검색 티어"""
    RAG = 1      # 내부 RAG (Weaviate)
    EPMC = 2     # Europe PMC
    WEB = 3      # Tavily Web Search


class SearchObjective(str, Enum):
    """검색 목적"""
    MECHANISM = "mechanism"              # 기전 관련
    PROTOCOL_CONTROLS = "protocol_controls"  # 프로토콜/대조군
    EVIDENCE_STRENGTH = "evidence_strength"  # 근거 강화


@dataclass
class EvidenceSnippetV3:
    """v3 Evidence 스니펫"""
    paper_id: str
    title: str
    journal: str
    year: int
    snippet: str
    claim_type: str  # mechanism, protocol, control, etc.
    source_tier: SearchTier
    source_tool: str  # rag, epmc, tavily
    relevance_score: float = 0.0
    metadata: dict = field(default_factory=dict)


# ─────────────────────────────────────────────────────────────
# DP1: 검색 승격 결정
# ─────────────────────────────────────────────────────────────

@dataclass
class DP1RouterInput:
    """DP1 검색 승격 라우터 입력"""
    current_tier: SearchTier
    coverage: float  # 0.0 ~ 1.0
    evidence_density: int  # 질문당 평균 근거 수
    gap_categories: list[str]  # 커버리지 부족 카테고리 (N, S, P, E)
    web_budget_remaining: int
    epmc_budget_remaining: int


@dataclass
class DP1RouterOutput:
    """DP1 검색 승격 라우터 출력"""
    decision: str  # proceed | upgrade_to_epmc | upgrade_to_web | skip_web_limit
    reason: str
    next_tier: SearchTier
    objective: SearchObjective | None = None
    query_plan: dict = field(default_factory=dict)


# ─────────────────────────────────────────────────────────────
# DP2: Critique 전략 결정
# ─────────────────────────────────────────────────────────────

@dataclass
class DP2RouterInput:
    """DP2 Critique 라우터 입력"""
    quality_score: float  # 0.0 ~ 1.0
    missing_controls: list[str]  # vehicle, positive, rescue 등
    evidence_gaps: list[str]  # 커버리지 부족 영역
    feasibility_conflicts: list[str]  # 실현가능성 충돌
    unclear_items: list[str]  # 모델/assay 불명확 항목
    dp2_loop_count: int
    epmc_budget_remaining: int
    web_budget_remaining: int
    previous_gaps_searched: list[str] = field(default_factory=list)  # 이미 검색한 gap


@dataclass
class DP2RouterOutput:
    """DP2 Critique 라우터 출력"""
    decision: str  # redesign | search_for_controls | ask_user | accept_minor_issues
    reason: str
    search_queries: list[str] = field(default_factory=list)  # search_for_controls용
    user_questions: list[str] = field(default_factory=list)  # ask_user용


# ─────────────────────────────────────────────────────────────
# DP3: Plan A/B 분기
# ─────────────────────────────────────────────────────────────

@dataclass
class DP3RouterInput:
    """DP3 Plan A/B 라우터 입력"""
    quality_score: float  # 0.0 ~ 1.0
    approval_required: bool
    web_limit_exceeded: bool
    evidence_sufficient: bool
    high_cost_experiment: bool
    ethics_required: bool
    explicit_constraints: list[str] = field(default_factory=list)


@dataclass
class DP3RouterOutput:
    """DP3 Plan A/B 라우터 출력"""
    decision: str  # single_plan | plan_a_b | plan_b_only
    reason: str
    plan_config: dict = field(default_factory=dict)
