"""Add rag_strategies table

- Create rag_strategies table for storing available RAG strategies
- Auto-synced from code on server startup

Revision ID: 005_add_rag_strategies
Revises: 004_add_sample_embeddings
Create Date: 2026-01-08
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "005_add_rag_strategies"
down_revision = "004_add_sample_embeddings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # rag_strategies 테이블 생성
    op.create_table(
        "rag_strategies",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("category", sa.String(50), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("config", postgresql.JSONB, server_default=sa.text("'{}'::jsonb"), nullable=True),
        sa.Column("location", sa.String(20), nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )

    # Unique 제약 조건
    op.create_unique_constraint(
        "uq_rag_strategies_category_name",
        "rag_strategies",
        ["category", "name"],
    )

    # 인덱스
    op.create_index("idx_rag_strategies_category", "rag_strategies", ["category"])
    op.create_index(
        "idx_rag_strategies_active",
        "rag_strategies",
        ["is_active"],
        postgresql_where=sa.text("is_active = true"),
    )

    # updated_at 자동 갱신 트리거 함수
    op.execute("""
        CREATE OR REPLACE FUNCTION update_rag_strategies_updated_at()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = NOW();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)

    # 트리거 생성
    op.execute("""
        CREATE TRIGGER trg_rag_strategies_updated_at
            BEFORE UPDATE ON rag_strategies
            FOR EACH ROW
            EXECUTE FUNCTION update_rag_strategies_updated_at();
    """)


def downgrade() -> None:
    # 트리거 삭제
    op.execute("DROP TRIGGER IF EXISTS trg_rag_strategies_updated_at ON rag_strategies;")
    op.execute("DROP FUNCTION IF EXISTS update_rag_strategies_updated_at();")

    # 인덱스 삭제
    op.drop_index("idx_rag_strategies_active", table_name="rag_strategies")
    op.drop_index("idx_rag_strategies_category", table_name="rag_strategies")

    # 제약 조건 삭제
    op.drop_constraint("uq_rag_strategies_category_name", "rag_strategies", type_="unique")

    # 테이블 삭제
    op.drop_table("rag_strategies")
