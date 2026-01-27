"""Agent Job 모델

백그라운드 에이전트 작업 관리
- 상태 머신 기반 작업 추적
- 승인 게이트 지원
- 결과 데이터 저장
"""

import uuid
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:
    from .notification import Notification
    from .user import User


class AgentJobStatus(str, Enum):
    """작업 상태 열거형"""

    PENDING = "pending"  # 생성됨, 아직 큐에 추가 안됨
    QUEUED = "queued"  # 큐에 추가됨, 실행 대기
    RUNNING = "running"  # 실행 중
    WAITING_APPROVAL = "waiting_approval"  # 사용자 승인 대기
    APPROVED = "approved"  # 승인됨, 다음 단계 실행 대기
    COMPLETED = "completed"  # 성공적으로 완료
    FAILED = "failed"  # 실패
    CANCELLED = "cancelled"  # 사용자에 의해 취소


class AgentType(str, Enum):
    """에이전트 유형 열거형"""

    STUDY_PLAN_V2 = "study_plan_v2"
    STUDY_PLAN_V3 = "study_plan_v3"
    STUDY_PLAN_V4 = "study_plan_v4"


class AgentJob(Base):
    """에이전트 작업 모델

    백그라운드에서 실행되는 에이전트 작업을 관리
    상태 머신, 승인 워크플로우, 결과 저장 지원
    """

    __tablename__ = "agent_jobs"

    # === Primary Key ===
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    # === User Reference ===
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # === Job Type ===
    agent_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )  # study_plan_v2, study_plan_v3, study_plan_v4
    job_name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )  # 사용자 친화적 이름 (가설 앞부분 등)

    # === Input ===
    input_data: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
    )  # hypothesis, research_context, constraints 등
    config: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
    )  # version, preferences 등

    # === State Machine ===
    status: Mapped[str] = mapped_column(
        String(30),
        default=AgentJobStatus.PENDING.value,
        nullable=False,
        index=True,
    )
    current_step: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )  # 현재 실행 중인 노드/단계
    progress_percent: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )  # 0-100
    progress_detail: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )  # 진행 상세 메시지
    step_results: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB,
        default=[],
        nullable=False,
    )  # 각 단계별 결과 기록

    # === Approval Gate ===
    approval_required: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    approval_gate_id: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )  # 현재 대기 중인 승인 게이트 ID
    approval_choices: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
    )  # 사용자에게 보여줄 선택지
    approval_decision: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
    )  # 사용자의 승인 결정
    approved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # === Result (기존 study_plans 필드 통합) ===
    result_data: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
    )  # final_plan, plan_a, plan_b, dp3_decision 등
    executive_summary: Mapped[str | None] = mapped_column(
        String(2000),
        nullable=True,
    )
    experiment_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    # === Thinking History (에이전트 reasoning 과정 저장) ===
    thinking_history: Mapped[list[dict[str, Any]] | None] = mapped_column(
        JSONB,
        nullable=True,
    )  # [{iteration, title, bullets, action, confidence, token_usage, timestamp}, ...]
    cumulative_tokens: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
    )  # {prompt_tokens, completion_tokens, total_tokens}

    # === Error Handling ===
    attempt_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    max_attempts: Mapped[int] = mapped_column(
        Integer,
        default=3,
        nullable=False,
    )
    last_error_code: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )
    last_error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # === Timing ===
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    total_duration_ms: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    # === Timestamps ===
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )  # Soft delete

    # === Relationships ===
    user: Mapped["User"] = relationship("User", back_populates="agent_jobs")
    notifications: Mapped[list["Notification"]] = relationship(
        "Notification",
        back_populates="agent_job",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<AgentJob {self.id} [{self.agent_type}] - {self.status}>"

    # === Helper Properties ===
    @property
    def is_terminal(self) -> bool:
        """작업이 종료 상태인지 확인"""
        return self.status in [
            AgentJobStatus.COMPLETED.value,
            AgentJobStatus.FAILED.value,
            AgentJobStatus.CANCELLED.value,
        ]

    @property
    def is_running(self) -> bool:
        """작업이 실행 중인지 확인"""
        return self.status in [
            AgentJobStatus.QUEUED.value,
            AgentJobStatus.RUNNING.value,
            AgentJobStatus.APPROVED.value,
        ]

    @property
    def needs_attention(self) -> bool:
        """사용자 조치가 필요한지 확인"""
        return self.status == AgentJobStatus.WAITING_APPROVAL.value

    @property
    def can_retry(self) -> bool:
        """재시도 가능한지 확인"""
        return (
            self.status == AgentJobStatus.FAILED.value
            and self.attempt_count < self.max_attempts
        )
