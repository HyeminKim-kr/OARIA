"""Add retry_count to sample_embeddings

- Add retry_count column to sample_embeddings table
- For Job Management System v2

Revision ID: 006_add_retry_count
Revises: 005_add_rag_strategies
Create Date: 2026-01-08
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "006_add_retry_count"
down_revision = "005_add_rag_strategies"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # sample_embeddings 테이블에 retry_count 컬럼 추가
    op.add_column(
        "sample_embeddings",
        sa.Column(
            "retry_count",
            sa.Integer,
            nullable=False,
            server_default="0",
        ),
    )


def downgrade() -> None:
    # retry_count 컬럼 삭제
    op.drop_column("sample_embeddings", "retry_count")
