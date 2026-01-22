"""Add study_plans table

Study Plan Agent 결과 저장용 테이블

Revision ID: 009_add_study_plans
Revises: a5e42c02caf8_add_paper_summaries_table
Create Date: 2025-01-21
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID

# revision identifiers, used by Alembic.
revision = "009_add_study_plans"
down_revision = "a5e42c02caf8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ========================================
    # 1. study_plans 테이블 생성
    # ========================================
    op.create_table(
        "study_plans",
        # Primary Key
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        # Foreign Key
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # 입력
        sa.Column("hypothesis_input", sa.Text, nullable=False),
        sa.Column("research_context", sa.Text, nullable=True),
        sa.Column(
            "preferred_experiment_types",
            ARRAY(sa.String(50)),
            nullable=False,
            server_default="{}",
        ),
        # 파싱된 가설
        sa.Column("hypothesis_structured", JSONB, nullable=True),
        sa.Column("hypothesis_confidence", sa.Float, nullable=True),
        # 검증 질문
        sa.Column("test_questions", JSONB, nullable=False, server_default="[]"),
        # 검색 결과
        sa.Column("search_coverage_score", sa.Float, nullable=True),
        sa.Column("prior_studies_count", sa.Integer, nullable=False, server_default="0"),
        # Evidence Pack
        sa.Column("evidence_packs", JSONB, nullable=False, server_default="[]"),
        # 실험 설계
        sa.Column("experiment_designs", JSONB, nullable=False, server_default="[]"),
        sa.Column("experiment_count", sa.Integer, nullable=False, server_default="0"),
        # Critique
        sa.Column("quality_score", sa.Float, nullable=True),
        sa.Column("revision_count", sa.Integer, nullable=False, server_default="0"),
        # 측정 항목
        sa.Column("measurements", JSONB, nullable=False, server_default="[]"),
        # 실현가능성
        sa.Column("feasibility_assessment", JSONB, nullable=True),
        # 승인 게이트
        sa.Column("approval_required", sa.Boolean, nullable=False, server_default="false"),
        sa.Column(
            "approval_status",
            sa.String(20),
            nullable=False,
            server_default="approved",
        ),
        # 최종 결과
        sa.Column("final_plan", sa.Text, nullable=True),
        sa.Column("executive_summary", sa.Text, nullable=True),
        sa.Column("references", JSONB, nullable=False, server_default="[]"),
        # 메타데이터
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="completed",
        ),
        sa.Column("total_duration_ms", sa.Integer, nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        # Timestamps
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    # ========================================
    # 2. 인덱스 생성
    # ========================================
    op.create_index("idx_study_plans_user_id", "study_plans", ["user_id"])
    op.create_index("idx_study_plans_status", "study_plans", ["status"])
    op.create_index(
        "idx_study_plans_created_at", "study_plans", ["created_at"], postgresql_using="btree"
    )

    # ========================================
    # 3. updated_at 자동 갱신 트리거
    # ========================================
    op.execute("""
        CREATE OR REPLACE FUNCTION update_study_plans_updated_at()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = NOW();
            RETURN NEW;
        END;
        $$ language 'plpgsql';
    """)

    op.execute("""
        CREATE TRIGGER trigger_update_study_plans_updated_at
            BEFORE UPDATE ON study_plans
            FOR EACH ROW
            EXECUTE FUNCTION update_study_plans_updated_at();
    """)


def downgrade() -> None:
    # 트리거 삭제
    op.execute("DROP TRIGGER IF EXISTS trigger_update_study_plans_updated_at ON study_plans")
    op.execute("DROP FUNCTION IF EXISTS update_study_plans_updated_at()")

    # 인덱스 삭제
    op.drop_index("idx_study_plans_created_at", table_name="study_plans")
    op.drop_index("idx_study_plans_status", table_name="study_plans")
    op.drop_index("idx_study_plans_user_id", table_name="study_plans")

    # 테이블 삭제
    op.drop_table("study_plans")
