"""Study Plan 모델

연구 계획 에이전트 실행 결과를 저장
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:
    from .user import User


class StudyPlan(Base):
    """Study Plan 에이전트 결과 모델

    가설 기반 실험 설계 결과를 저장
    """

    __tablename__ = "study_plans"

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

    # === 입력 ===
    hypothesis_input: Mapped[str] = mapped_column(Text, nullable=False)
    research_context: Mapped[str | None] = mapped_column(Text, nullable=True)
    preferred_experiment_types: Mapped[list[str]] = mapped_column(
        ARRAY(String(50)),
        default=[],
        nullable=False,
    )

    # === 파싱된 가설 ===
    hypothesis_structured: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
    )
    hypothesis_confidence: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    # === 검증 질문 ===
    test_questions: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB,
        default=[],
        nullable=False,
    )

    # === 검색 결과 ===
    search_coverage_score: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )
    prior_studies_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    # === Evidence Pack ===
    evidence_packs: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB,
        default=[],
        nullable=False,
    )

    # === 실험 설계 ===
    experiment_designs: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB,
        default=[],
        nullable=False,
    )
    experiment_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    # === Critique ===
    quality_score: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )
    revision_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    # === 측정 항목 ===
    measurements: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB,
        default=[],
        nullable=False,
    )

    # === 실현가능성 ===
    feasibility_assessment: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
    )

    # === 승인 게이트 ===
    approval_required: Mapped[bool] = mapped_column(
        default=False,
        nullable=False,
    )
    approval_status: Mapped[str] = mapped_column(
        String(20),
        default="approved",
        nullable=False,
    )

    # === 최종 결과 ===
    final_plan: Mapped[str | None] = mapped_column(Text, nullable=True)
    executive_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    references: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB,
        default=[],
        nullable=False,
    )

    # === v3 전용 필드 ===
    # Plan A/B
    plan_a: Mapped[str | None] = mapped_column(Text, nullable=True)
    plan_b: Mapped[str | None] = mapped_column(Text, nullable=True)
    plan_config: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
    )

    # Decision Points 결과
    dp1_decisions: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB,
        default=[],
        nullable=False,
        server_default="[]",
    )
    dp2_decision: Mapped[str | None] = mapped_column(String(50), nullable=True)
    dp3_decision: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # 3-tier 검색 정보
    highest_tier_used: Mapped[int] = mapped_column(
        Integer,
        default=1,
        nullable=False,
        server_default="1",
    )
    evidence_snippets_v3: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB,
        default=[],
        nullable=False,
        server_default="[]",
    )
    search_tier_history: Mapped[list[int]] = mapped_column(
        ARRAY(Integer),
        default=[],
        nullable=False,
        server_default="{}",
    )

    # === 메타데이터 ===
    status: Mapped[str] = mapped_column(
        String(20),
        default="completed",
        nullable=False,
        index=True,
    )  # completed, error, deleted
    total_duration_ms: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

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

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="study_plans")

    def __repr__(self) -> str:
        return f"<StudyPlan {self.id} - {self.hypothesis_input[:50]}...>"
