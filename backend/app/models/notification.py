"""Notification 모델

범용 알림 시스템
- 인앱 알림 저장
- 다양한 알림 유형 지원
- 읽음/삭제 상태 관리
"""

import uuid
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:
    from .agent_job import AgentJob
    from .user import User


class NotificationType(str, Enum):
    """알림 유형 열거형"""

    # Agent Job 관련
    JOB_STARTED = "job_started"
    JOB_PROGRESS = "job_progress"
    JOB_WAITING_APPROVAL = "job_waiting_approval"
    JOB_APPROVED = "job_approved"
    JOB_COMPLETED = "job_completed"
    JOB_FAILED = "job_failed"

    # 시스템 관련
    SYSTEM_INFO = "system_info"
    SYSTEM_WARNING = "system_warning"


class NotificationCategory(str, Enum):
    """알림 카테고리 열거형"""

    AGENT = "agent"  # 에이전트 작업 관련
    PAPER = "paper"  # 논문 관련
    SYSTEM = "system"  # 시스템 관련


class NotificationPriority(str, Enum):
    """알림 우선순위 열거형"""

    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class NotificationActionType(str, Enum):
    """알림 액션 유형 열거형"""

    VIEW = "view"  # 상세 보기
    APPROVE = "approve"  # 승인 페이지로 이동
    RETRY = "retry"  # 재시도
    DISMISS = "dismiss"  # 닫기만


class Notification(Base):
    """알림 모델

    사용자에게 전달되는 인앱 알림 저장
    다양한 유형, 카테고리, 우선순위 지원
    """

    __tablename__ = "notifications"

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

    # === Type & Category ===
    type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )  # job_started, job_completed, approval_required, etc.
    category: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )  # agent, paper, system

    # === Content ===
    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    message: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    # === Entity Reference (선택적) ===
    entity_type: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )  # agent_job, paper, etc.
    entity_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agent_jobs.id", ondelete="SET NULL"),
        nullable=True,
    )

    # === Action ===
    action_type: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )  # view, approve, retry
    action_url: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )  # 클릭 시 이동할 URL
    action_label: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )  # 버튼 텍스트

    # === Display ===
    priority: Mapped[str] = mapped_column(
        String(20),
        default=NotificationPriority.NORMAL.value,
        nullable=False,
    )  # low, normal, high, urgent
    icon: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )  # 아이콘 이름/코드
    extra_data: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
    )  # 추가 데이터 (progress, experiment_count 등)

    # === Read Status ===
    is_read: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    read_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    is_dismissed: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    # === Timestamps ===
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )

    # === Relationships ===
    user: Mapped["User"] = relationship("User", back_populates="notifications")
    agent_job: Mapped["AgentJob | None"] = relationship(
        "AgentJob",
        back_populates="notifications",
    )

    def __repr__(self) -> str:
        return f"<Notification {self.id} [{self.type}] - {self.title[:30]}>"

    # === Helper Properties ===
    @property
    def is_visible(self) -> bool:
        """알림이 사용자에게 보여야 하는지 확인"""
        return not self.is_dismissed

    @property
    def is_actionable(self) -> bool:
        """알림에 액션이 있는지 확인"""
        return self.action_type is not None and self.action_url is not None
