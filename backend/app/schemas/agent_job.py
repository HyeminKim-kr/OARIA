"""Agent Job 스키마

백그라운드 에이전트 작업 API 요청/응답 스키마.
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


# ============================================================
# 요청 스키마
# ============================================================


class AgentJobCreateRequest(BaseModel):
    """Agent Job 생성 요청"""

    agent_type: str = Field(
        ...,
        description="에이전트 유형 (study_plan_v2, study_plan_v3, study_plan_v4)",
        examples=["study_plan_v3"],
    )
    input_data: dict[str, Any] = Field(
        ...,
        description="에이전트 입력 데이터 (가설, 컨텍스트 등)",
        examples=[
            {
                "hypothesis": "EGFR T790M 돌연변이 환자에서...",
                "research_context": "NSCLC targeted therapy",
                "constraints": ["예산 $50K 이내"],
            }
        ],
    )
    config: dict[str, Any] | None = Field(
        default=None,
        description="에이전트 설정 옵션",
    )
    job_name: str | None = Field(
        default=None,
        max_length=255,
        description="작업 이름 (지정하지 않으면 입력에서 자동 생성)",
    )


class AgentJobApprovalRequest(BaseModel):
    """승인 게이트 응답 요청"""

    decision: dict[str, Any] = Field(
        ...,
        description="승인 결정 (choice_id, comment 등)",
        examples=[
            {
                "choice_id": "approve_all",
                "comment": "비용 허용 범위 내입니다",
            }
        ],
    )


class AgentJobRetryRequest(BaseModel):
    """실패 작업 재시도 요청"""

    reset_config: dict[str, Any] | None = Field(
        default=None,
        description="재시도 시 변경할 설정",
    )


# ============================================================
# 응답 스키마
# ============================================================


class AgentJobResponse(BaseModel):
    """Agent Job 기본 응답"""

    id: UUID
    user_id: UUID
    agent_type: str
    job_name: str | None
    status: str
    current_step: str | None
    progress_percent: int
    progress_detail: str | None

    # Approval
    approval_required: bool
    approval_gate_id: str | None
    approval_choices: dict[str, Any] | None
    approved_at: datetime | None

    # Result
    executive_summary: str | None
    experiment_count: int

    # Error
    attempt_count: int
    max_attempts: int
    last_error_code: str | None
    last_error_message: str | None

    # Timing
    started_at: datetime | None
    completed_at: datetime | None
    total_duration_ms: int | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AgentJobDetailResponse(AgentJobResponse):
    """Agent Job 상세 응답 (입력/결과 포함)"""

    input_data: dict[str, Any]
    config: dict[str, Any] | None
    step_results: list[dict[str, Any]]
    approval_decision: dict[str, Any] | None
    result_data: dict[str, Any] | None


class AgentJobListItem(BaseModel):
    """Agent Job 목록 아이템"""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    agent_type: str
    job_name: str | None
    status: str
    progress_percent: int
    approval_required: bool
    experiment_count: int
    created_at: datetime


class PaginatedAgentJobs(BaseModel):
    """페이지네이션된 Agent Job 목록"""

    items: list[AgentJobListItem]
    total: int
    page: int
    size: int
    pages: int


# ============================================================
# SSE 이벤트 스키마
# ============================================================


class AgentJobSSEEvent(BaseModel):
    """SSE 스트리밍 이벤트"""

    event_type: str = Field(
        ...,
        description="이벤트 유형 (status, progress, step_complete, approval_required, completed, error)",
    )
    job_id: UUID
    data: dict[str, Any] = Field(
        default_factory=dict,
        description="이벤트 데이터",
    )
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
    )
