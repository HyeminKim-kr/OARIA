"""Add agent_jobs and notifications tables

Background Job & Notification System
- agent_jobs: 백그라운드 에이전트 작업 관리
- notifications: 범용 인앱 알림 시스템
- study_plans 데이터를 agent_jobs로 마이그레이션

Revision ID: 010_add_agent_jobs_notifications
Revises: edc48308ac78
Create Date: 2025-01-22
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

# revision identifiers, used by Alembic.
revision = "010_add_agent_jobs_notifications"
down_revision = "edc48308ac78"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ========================================
    # 1. agent_jobs 테이블 생성
    # ========================================
    op.create_table(
        "agent_jobs",
        # Primary Key
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        # User Reference
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # Job Type
        sa.Column("agent_type", sa.String(50), nullable=False),
        sa.Column("job_name", sa.String(255), nullable=True),
        # Input
        sa.Column("input_data", JSONB, nullable=False),
        sa.Column("config", JSONB, nullable=True),
        # State Machine
        sa.Column("status", sa.String(30), nullable=False, server_default="pending"),
        sa.Column("current_step", sa.String(100), nullable=True),
        sa.Column("progress_percent", sa.Integer, nullable=False, server_default="0"),
        sa.Column("progress_detail", sa.String(500), nullable=True),
        sa.Column("step_results", JSONB, nullable=False, server_default="[]"),
        # Approval Gate
        sa.Column("approval_required", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("approval_gate_id", sa.String(50), nullable=True),
        sa.Column("approval_choices", JSONB, nullable=True),
        sa.Column("approval_decision", JSONB, nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        # Result
        sa.Column("result_data", JSONB, nullable=True),
        sa.Column("executive_summary", sa.String(2000), nullable=True),
        sa.Column("experiment_count", sa.Integer, nullable=False, server_default="0"),
        # Error Handling
        sa.Column("attempt_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer, nullable=False, server_default="3"),
        sa.Column("last_error_code", sa.String(50), nullable=True),
        sa.Column("last_error_message", sa.Text, nullable=True),
        # Timing
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("total_duration_ms", sa.Integer, nullable=True),
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
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )

    # agent_jobs 인덱스
    op.create_index("idx_agent_jobs_user_id", "agent_jobs", ["user_id"])
    op.create_index("idx_agent_jobs_agent_type", "agent_jobs", ["agent_type"])
    op.create_index("idx_agent_jobs_status", "agent_jobs", ["status"])
    op.create_index("idx_agent_jobs_created_at", "agent_jobs", ["created_at"])
    op.create_index(
        "idx_agent_jobs_user_status",
        "agent_jobs",
        ["user_id", "status"],
    )
    # 승인 대기 중인 작업 조회용 부분 인덱스
    op.execute("""
        CREATE INDEX idx_agent_jobs_waiting_approval
        ON agent_jobs(user_id, created_at DESC)
        WHERE status = 'waiting_approval';
    """)

    # ========================================
    # 2. notifications 테이블 생성
    # ========================================
    op.create_table(
        "notifications",
        # Primary Key
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        # User Reference
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # Type & Category
        sa.Column("type", sa.String(50), nullable=False),
        sa.Column("category", sa.String(50), nullable=False),
        # Content
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("message", sa.Text, nullable=False),
        # Entity Reference
        sa.Column("entity_type", sa.String(50), nullable=True),
        sa.Column(
            "entity_id",
            UUID(as_uuid=True),
            sa.ForeignKey("agent_jobs.id", ondelete="SET NULL"),
            nullable=True,
        ),
        # Action
        sa.Column("action_type", sa.String(50), nullable=True),
        sa.Column("action_url", sa.String(500), nullable=True),
        sa.Column("action_label", sa.String(100), nullable=True),
        # Display
        sa.Column("priority", sa.String(20), nullable=False, server_default="normal"),
        sa.Column("icon", sa.String(50), nullable=True),
        sa.Column("extra_data", JSONB, nullable=True),
        # Read Status
        sa.Column("is_read", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_dismissed", sa.Boolean, nullable=False, server_default="false"),
        # Timestamps
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    # notifications 인덱스
    op.create_index("idx_notifications_user_id", "notifications", ["user_id"])
    op.create_index("idx_notifications_type", "notifications", ["type"])
    op.create_index("idx_notifications_category", "notifications", ["category"])
    op.create_index("idx_notifications_created_at", "notifications", ["created_at"])
    # 읽지 않은 알림 조회용 부분 인덱스
    op.execute("""
        CREATE INDEX idx_notifications_user_unread
        ON notifications(user_id, created_at DESC)
        WHERE is_read = FALSE AND is_dismissed = FALSE;
    """)

    # ========================================
    # 3. updated_at 자동 갱신 트리거 (agent_jobs)
    # ========================================
    op.execute("""
        CREATE OR REPLACE FUNCTION update_agent_jobs_updated_at()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = NOW();
            RETURN NEW;
        END;
        $$ language 'plpgsql';
    """)

    op.execute("""
        CREATE TRIGGER trigger_update_agent_jobs_updated_at
            BEFORE UPDATE ON agent_jobs
            FOR EACH ROW
            EXECUTE FUNCTION update_agent_jobs_updated_at();
    """)

    # ========================================
    # 4. study_plans → agent_jobs 데이터 마이그레이션
    # ========================================
    op.execute("""
        INSERT INTO agent_jobs (
            id, user_id, agent_type, job_name, input_data, config,
            status, result_data, executive_summary, experiment_count,
            total_duration_ms, created_at, updated_at, deleted_at
        )
        SELECT
            id,
            user_id,
            CASE
                WHEN dp3_decision IS NOT NULL THEN 'study_plan_v3'
                ELSE 'study_plan_v2'
            END as agent_type,
            LEFT(hypothesis_input, 100) as job_name,
            jsonb_build_object(
                'hypothesis', hypothesis_input,
                'research_context', research_context,
                'preferred_experiment_types', preferred_experiment_types
            ) as input_data,
            jsonb_build_object() as config,
            CASE
                WHEN status = 'deleted' THEN 'cancelled'
                WHEN status = 'error' THEN 'failed'
                ELSE 'completed'
            END as status,
            jsonb_build_object(
                'final_plan', final_plan,
                'plan_a', plan_a,
                'plan_b', plan_b,
                'dp3_decision', dp3_decision,
                'experiment_designs', experiment_designs,
                'evidence_packs', evidence_packs,
                'measurements', measurements,
                'feasibility_assessment', feasibility_assessment,
                'references', "references",
                'hypothesis_structured', hypothesis_structured,
                'test_questions', test_questions
            ) as result_data,
            executive_summary,
            experiment_count,
            total_duration_ms,
            created_at,
            updated_at,
            CASE WHEN status = 'deleted' THEN NOW() ELSE NULL END as deleted_at
        FROM study_plans;
    """)


def downgrade() -> None:
    # ========================================
    # 1. 트리거 삭제
    # ========================================
    op.execute("DROP TRIGGER IF EXISTS trigger_update_agent_jobs_updated_at ON agent_jobs")
    op.execute("DROP FUNCTION IF EXISTS update_agent_jobs_updated_at()")

    # ========================================
    # 2. notifications 테이블 삭제
    # ========================================
    op.execute("DROP INDEX IF EXISTS idx_notifications_user_unread")
    op.drop_index("idx_notifications_created_at", table_name="notifications")
    op.drop_index("idx_notifications_category", table_name="notifications")
    op.drop_index("idx_notifications_type", table_name="notifications")
    op.drop_index("idx_notifications_user_id", table_name="notifications")
    op.drop_table("notifications")

    # ========================================
    # 3. agent_jobs 테이블 삭제
    # ========================================
    op.execute("DROP INDEX IF EXISTS idx_agent_jobs_waiting_approval")
    op.drop_index("idx_agent_jobs_user_status", table_name="agent_jobs")
    op.drop_index("idx_agent_jobs_created_at", table_name="agent_jobs")
    op.drop_index("idx_agent_jobs_status", table_name="agent_jobs")
    op.drop_index("idx_agent_jobs_agent_type", table_name="agent_jobs")
    op.drop_index("idx_agent_jobs_user_id", table_name="agent_jobs")
    op.drop_table("agent_jobs")
