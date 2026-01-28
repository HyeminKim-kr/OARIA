"""Drop study_plans table

study_plans 테이블을 삭제하고 agent_jobs로 통합.
기존 데이터는 이 마이그레이션으로 영구 삭제됩니다.

Revision ID: 011_drop_study_plans
Revises: 010_add_agent_jobs_notifications
Create Date: 2025-01-26
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "011_drop_study_plans"
down_revision: Union[str, None] = "010_add_agent_jobs_notifications"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """study_plans 테이블 삭제"""
    op.drop_table("study_plans")


def downgrade() -> None:
    """study_plans 테이블 재생성 (데이터 복구 불가)"""
    op.create_table(
        "study_plans",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        # 입력
        sa.Column("hypothesis_input", sa.Text(), nullable=False),
        sa.Column("research_context", sa.Text(), nullable=True),
        sa.Column("preferred_experiment_types", postgresql.ARRAY(sa.String(50)), default=[], nullable=False),
        # 파싱된 가설
        sa.Column("hypothesis_structured", postgresql.JSONB(), nullable=True),
        sa.Column("hypothesis_confidence", sa.Float(), nullable=True),
        # 검증 질문
        sa.Column("test_questions", postgresql.JSONB(), default=[], nullable=False),
        # 검색 결과
        sa.Column("search_coverage_score", sa.Float(), nullable=True),
        sa.Column("prior_studies_count", sa.Integer(), default=0, nullable=False),
        # Evidence Pack
        sa.Column("evidence_packs", postgresql.JSONB(), default=[], nullable=False),
        # 실험 설계
        sa.Column("experiment_designs", postgresql.JSONB(), default=[], nullable=False),
        sa.Column("experiment_count", sa.Integer(), default=0, nullable=False),
        # Critique
        sa.Column("quality_score", sa.Float(), nullable=True),
        sa.Column("revision_count", sa.Integer(), default=0, nullable=False),
        # 측정 항목
        sa.Column("measurements", postgresql.JSONB(), default=[], nullable=False),
        # 실현가능성
        sa.Column("feasibility_assessment", postgresql.JSONB(), nullable=True),
        # 승인 게이트
        sa.Column("approval_required", sa.Boolean(), default=False, nullable=False),
        sa.Column("approval_status", sa.String(20), default="approved", nullable=False),
        # 최종 결과
        sa.Column("final_plan", sa.Text(), nullable=True),
        sa.Column("executive_summary", sa.Text(), nullable=True),
        sa.Column("references", postgresql.JSONB(), default=[], nullable=False),
        # v3 전용 필드
        sa.Column("plan_a", sa.Text(), nullable=True),
        sa.Column("plan_b", sa.Text(), nullable=True),
        sa.Column("plan_config", postgresql.JSONB(), nullable=True),
        sa.Column("dp1_decisions", postgresql.JSONB(), default=[], nullable=False, server_default="[]"),
        sa.Column("dp2_decision", sa.String(50), nullable=True),
        sa.Column("dp3_decision", sa.String(50), nullable=True),
        sa.Column("highest_tier_used", sa.Integer(), default=1, nullable=False, server_default="1"),
        sa.Column("evidence_snippets_v3", postgresql.JSONB(), default=[], nullable=False, server_default="[]"),
        sa.Column("search_tier_history", postgresql.ARRAY(sa.Integer()), default=[], nullable=False, server_default="{}"),
        # 메타데이터
        sa.Column("status", sa.String(20), default="completed", nullable=False, index=True),
        sa.Column("total_duration_ms", sa.Integer(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False, index=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
