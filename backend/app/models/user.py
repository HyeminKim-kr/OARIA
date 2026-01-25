"""User 모델"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:
    from .social_account import SocialAccount
    from .refresh_token import UserRefreshToken
    from .chat import Conversation, AnswerLog
    from .study_plan import StudyPlan
    from .agent_job import AgentJob
    from .notification import Notification


class User(Base):
    """서비스 사용자 모델

    소셜 로그인으로 인증된 사용자 정보 저장
    """

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        index=True,
        nullable=False,
    )
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    picture: Mapped[str | None] = mapped_column(String(512), nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    social_accounts: Mapped[list["SocialAccount"]] = relationship(
        "SocialAccount",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    refresh_tokens: Mapped[list["UserRefreshToken"]] = relationship(
        "UserRefreshToken",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    conversations: Mapped[list["Conversation"]] = relationship(
        "Conversation",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    answer_logs: Mapped[list["AnswerLog"]] = relationship(
        "AnswerLog",
        back_populates="user",
    )
    study_plans: Mapped[list["StudyPlan"]] = relationship(
        "StudyPlan",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    agent_jobs: Mapped[list["AgentJob"]] = relationship(
        "AgentJob",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    notifications: Mapped[list["Notification"]] = relationship(
        "Notification",
        back_populates="user",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<User {self.email}>"
