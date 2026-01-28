"""Podcast 관련 모델 (PodcastSubscription, PodcastEpisode)

F-11: Agentic Podcast System
- Goal-driven podcast generation with 3-task agent
- Scheduled generation via Celery
"""

import uuid
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:
    from .user import User


class PodcastFrequency(str, Enum):
    """구독 주기"""
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


class PodcastStyle(str, Enum):
    """팟캐스트 스타일"""
    TWO_HOSTS = "two_hosts"      # 두 명의 호스트 대화
    INTERVIEW = "interview"      # 인터뷰 형식
    SOLO = "solo"                # 단일 발표자


class PodcastDuration(str, Enum):
    """에피소드 길이"""
    SHORT = "short"      # ~5분
    MEDIUM = "medium"    # ~10분
    LONG = "long"        # ~15분


class PaperSelectionMode(str, Enum):
    """논문 선택 모드"""
    AUTO = "auto"           # Reranker 점수 기반 자동 선택
    USER_PICK = "user_pick"  # 사용자 직접 선택
    COMPARE = "compare"      # 다른 관점의 논문 비교


class EpisodeStatus(str, Enum):
    """에피소드 생성 상태"""
    PENDING = "pending"           # 대기
    SEARCHING = "searching"       # RAG 검색 중 (Task 1)
    ANALYZING = "analyzing"       # 논문 분석 중 (Task 2)
    SCRIPTING = "scripting"       # 스크립트 생성 중 (Task 3)
    GENERATING_AUDIO = "generating_audio"  # TTS 생성 중
    COMPLETED = "completed"       # 완료
    FAILED = "failed"             # 실패


class PodcastSubscription(Base):
    """팟캐스트 구독 설정 (자동 생성용)"""

    __tablename__ = "podcast_subscriptions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # 구독 주제 (배열)
    topics: Mapped[list[str]] = mapped_column(
        ARRAY(String(200)),
        nullable=False,
    )

    # 생성 설정
    frequency: Mapped[str] = mapped_column(
        String(20),
        default=PodcastFrequency.WEEKLY.value,
        nullable=False,
    )
    episode_style: Mapped[str] = mapped_column(
        String(20),
        default=PodcastStyle.TWO_HOSTS.value,
        nullable=False,
    )
    episode_duration: Mapped[str] = mapped_column(
        String(10),
        default=PodcastDuration.SHORT.value,
        nullable=False,
    )
    language: Mapped[str] = mapped_column(
        String(5),
        default="ko",
        nullable=False,
    )

    # 상태
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
    last_generated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # 타임스탬프
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

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="podcast_subscriptions")
    episodes: Mapped[list["PodcastEpisode"]] = relationship(
        "PodcastEpisode",
        back_populates="subscription",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<PodcastSubscription {self.id} - topics={self.topics}>"


class PodcastEpisode(Base):
    """생성된 팟캐스트 에피소드"""

    __tablename__ = "podcast_episodes"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    subscription_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("podcast_subscriptions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Goal & Config
    goal: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    duration: Mapped[str] = mapped_column(
        String(10),
        default=PodcastDuration.SHORT.value,
        nullable=False,
    )
    style: Mapped[str] = mapped_column(
        String(20),
        default=PodcastStyle.TWO_HOSTS.value,
        nullable=False,
    )
    paper_mode: Mapped[str] = mapped_column(
        String(20),
        default=PaperSelectionMode.AUTO.value,
        nullable=False,
    )
    language: Mapped[str] = mapped_column(
        String(5),
        default="ko",
        nullable=False,
    )

    # Content
    title: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    script: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
    )
    audio_url: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )
    duration_seconds: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    # Evidence (RAG-based)
    paper_ids: Mapped[list[str] | None] = mapped_column(
        ARRAY(String(50)),
        nullable=True,
    )
    references: Mapped[list[dict[str, Any]] | None] = mapped_column(
        JSONB,
        nullable=True,
    )

    # Execution metadata (3 tasks results)
    task_results: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
    )

    # Search filters used
    search_filters: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
    )

    # Status
    status: Mapped[str] = mapped_column(
        String(20),
        default=EpisodeStatus.PENDING.value,
        nullable=False,
        index=True,
    )
    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="podcast_episodes")
    subscription: Mapped["PodcastSubscription | None"] = relationship(
        "PodcastSubscription",
        back_populates="episodes",
    )

    def __repr__(self) -> str:
        return f"<PodcastEpisode {self.id} - {self.title}>"
