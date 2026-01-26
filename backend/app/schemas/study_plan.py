"""Study Plan Agent 스키마

API 요청/응답 스키마 정의.
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class StudyPlanRequest(BaseModel):
    """Study Plan 생성 요청"""

    hypothesis: str = Field(
        ...,
        min_length=10,
        max_length=2000,
        description="검증하고자 하는 가설 또는 기전 설명",
        examples=[
            "EGFR T790M 돌연변이 환자에서 osimertinib 내성 기전으로 MET amplification이 관여한다"
        ],
    )
    research_context: str | None = Field(
        default=None,
        max_length=500,
        description="연구 맥락 또는 배경 정보",
        examples=["NSCLC targeted therapy resistance research"],
    )
    constraints: list[str] | None = Field(
        default=None,
        description="제약조건 목록",
        examples=[["예산 $50K 이내", "6개월 내 완료"]],
    )
    preferred_experiment_types: list[str] | None = Field(
        default=None,
        description="선호하는 실험 유형 (in_vitro, in_vivo, clinical, computational)",
        examples=[["in_vitro", "in_vivo"]],
    )


class StudyPlanApprovalRequest(BaseModel):
    """승인 게이트 응답 요청"""

    plan_id: str = Field(..., description="Study Plan ID")
    choice_id: str = Field(
        ...,
        description="선택한 옵션 ID (approve_all, in_vitro_only, reduce_scope 등)",
    )
    comment: str | None = Field(default=None, description="추가 코멘트")


class TestQuestionResponse(BaseModel):
    """검증 질문 응답"""

    category: str
    question: str
    decision_rule: str
    priority: int


class ExperimentSummaryResponse(BaseModel):
    """실험 설계 요약 응답"""

    experiment_id: str
    experiment_type: str
    title: str
    test_category: str
    estimated_timeline: str
    estimated_cost_level: str


class ApprovalChoiceResponse(BaseModel):
    """승인 선택지 응답"""

    choice_id: str
    label: str
    description: str
    estimated_cost: str
    estimated_timeline: str


class ApprovalItemResponse(BaseModel):
    """승인 필요 항목 응답"""

    item_type: str
    reason: str
    cost_bucket: str
    ethics_bucket: str


class StudyPlanSummaryResponse(BaseModel):
    """Study Plan 요약 응답 (동기 실행 시)"""

    success: bool
    plan_id: str | None = None
    final_plan: str
    executive_summary: str
    experiment_count: int
    approval_required: bool
    approval_status: str
    total_duration_ms: int
    error: str | None = None


class StudyPlanDetailResponse(BaseModel):
    """Study Plan 상세 응답"""

    plan_id: str
    hypothesis: str
    test_questions: list[TestQuestionResponse]
    experiments: list[ExperimentSummaryResponse]
    final_plan: str
    executive_summary: str
    approval_required: bool
    approval_status: str
    approval_items: list[ApprovalItemResponse] | None = None
    approval_choices: list[ApprovalChoiceResponse] | None = None
    created_at: str
    total_duration_ms: int


# ============================================================
# 저장/히스토리용 스키마
# ============================================================


class StudyPlanSaveRequest(BaseModel):
    """Study Plan 저장 요청"""

    hypothesis_input: str = Field(..., description="입력된 가설")
    research_context: str | None = Field(default=None)
    preferred_experiment_types: list[str] = Field(default=[])

    # 파싱된 가설
    hypothesis_structured: dict[str, Any] | None = Field(default=None)
    hypothesis_confidence: float | None = Field(default=None)

    # 검증 질문
    test_questions: list[dict[str, Any]] = Field(default=[])

    # 검색 결과
    search_coverage_score: float | None = Field(default=None)
    prior_studies_count: int = Field(default=0)

    # Evidence Pack
    evidence_packs: list[dict[str, Any]] = Field(default=[])

    # 실험 설계
    experiment_designs: list[dict[str, Any]] = Field(default=[])
    experiment_count: int = Field(default=0)

    # Critique
    quality_score: float | None = Field(default=None)
    revision_count: int = Field(default=0)

    # 측정 항목
    measurements: list[dict[str, Any]] = Field(default=[])

    # 실현가능성
    feasibility_assessment: dict[str, Any] | None = Field(default=None)

    # 승인 게이트
    approval_required: bool = Field(default=False)
    approval_status: str = Field(default="approved")

    # 최종 결과
    final_plan: str | None = Field(default=None)
    executive_summary: str | None = Field(default=None)
    references: list[dict[str, Any]] = Field(default=[])

    # === v3 전용 필드 ===
    # Plan A/B
    plan_a: str | None = Field(default=None, description="Plan A (강력 검증)")
    plan_b: str | None = Field(default=None, description="Plan B (보수 검증)")
    plan_config: dict[str, Any] | None = Field(default=None, description="Plan A/B 설정")

    # Decision Points 결과
    dp1_decisions: list[dict[str, Any]] = Field(default=[], description="DP1 검색 승격 결정들")
    dp2_decision: str | None = Field(default=None, description="DP2 Critique 전략")
    dp3_decision: str | None = Field(default=None, description="DP3 Plan 분기")

    # 3-tier 검색 정보
    highest_tier_used: int = Field(default=1, description="사용된 최고 검색 티어 (1=RAG, 2=EPMC, 3=Web)")
    evidence_snippets_v3: list[dict[str, Any]] = Field(default=[], description="v3 Evidence snippets")
    search_tier_history: list[int] = Field(default=[], description="검색 티어 히스토리")

    # 메타
    status: str = Field(default="completed")
    total_duration_ms: int | None = Field(default=None)
    error_message: str | None = Field(default=None)


class StudyPlanListItem(BaseModel):
    """Study Plan 목록 아이템"""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    hypothesis_input: str
    experiment_count: int
    quality_score: float | None
    status: str
    created_at: datetime


class PaginatedStudyPlans(BaseModel):
    """페이지네이션된 Study Plan 목록"""

    items: list[StudyPlanListItem]
    total: int
    page: int
    size: int
    pages: int


class StudyPlanFullResponse(BaseModel):
    """Study Plan 전체 상세 응답 (DB에서 조회)"""

    id: UUID
    user_id: UUID

    # 입력
    hypothesis_input: str
    research_context: str | None
    preferred_experiment_types: list[str]

    # 파싱된 가설
    hypothesis_structured: dict[str, Any] | None
    hypothesis_confidence: float | None

    # 검증 질문
    test_questions: list[dict[str, Any]]

    # 검색 결과
    search_coverage_score: float | None
    prior_studies_count: int

    # Evidence Pack
    evidence_packs: list[dict[str, Any]]

    # 실험 설계
    experiment_designs: list[dict[str, Any]]
    experiment_count: int

    # Critique
    quality_score: float | None
    revision_count: int

    # 측정 항목
    measurements: list[dict[str, Any]]

    # 실현가능성
    feasibility_assessment: dict[str, Any] | None

    # 승인 게이트
    approval_required: bool
    approval_status: str

    # 최종 결과
    final_plan: str | None
    executive_summary: str | None
    references: list[dict[str, Any]]

    # === v3 전용 필드 ===
    # Plan A/B
    plan_a: str | None = None
    plan_b: str | None = None
    plan_config: dict[str, Any] | None = None

    # Decision Points 결과
    dp1_decisions: list[dict[str, Any]] = []
    dp2_decision: str | None = None
    dp3_decision: str | None = None

    # 3-tier 검색 정보
    highest_tier_used: int = 1
    evidence_snippets_v3: list[dict[str, Any]] = []
    search_tier_history: list[int] = []

    # 메타
    status: str
    total_duration_ms: int | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
