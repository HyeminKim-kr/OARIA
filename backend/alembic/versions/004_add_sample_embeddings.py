"""Add sample embeddings support

- Add query_type column to search_queries
- Create sample_embeddings table

Revision ID: 004_add_sample_embeddings
Revises: 003_add_chat_tables
Create Date: 2026-01-08
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "004_add_sample_embeddings"
down_revision = "003_add_chat"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. search_queries 테이블에 query_type 컬럼 추가
    op.add_column(
        "search_queries",
        sa.Column(
            "query_type",
            sa.String(20),
            nullable=False,
            server_default="production",
        ),
    )

    # query_type 인덱스 추가
    op.create_index(
        "idx_search_queries_type",
        "search_queries",
        ["query_type"],
    )

    # 2. sample_embeddings 테이블 생성
    op.create_table(
        "sample_embeddings",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        # 샘플 쿼리 참조
        sa.Column(
            "query_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("search_queries.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # 파이프라인 정보
        sa.Column("chunker", sa.String(100), nullable=False),
        sa.Column("embedder", sa.String(100), nullable=False),
        sa.Column("pipeline_key", sa.String(200), nullable=False),
        sa.Column("collection_name", sa.String(200), nullable=False),
        # 상태
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("paper_count", sa.Integer, server_default="0"),
        sa.Column("chunk_count", sa.Integer, server_default="0"),
        sa.Column("error_message", sa.Text),
        # 타임스탬프
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
        ),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        # 유니크 제약
        sa.UniqueConstraint("query_id", "pipeline_key", name="uq_sample_embeddings_query_pipeline"),
    )

    # 인덱스 생성
    op.create_index(
        "idx_sample_embeddings_query_id",
        "sample_embeddings",
        ["query_id"],
    )
    op.create_index(
        "idx_sample_embeddings_status",
        "sample_embeddings",
        ["status"],
    )


def downgrade() -> None:
    # sample_embeddings 테이블 삭제
    op.drop_index("idx_sample_embeddings_status", table_name="sample_embeddings")
    op.drop_index("idx_sample_embeddings_query_id", table_name="sample_embeddings")
    op.drop_table("sample_embeddings")

    # search_queries.query_type 컬럼 삭제
    op.drop_index("idx_search_queries_type", table_name="search_queries")
    op.drop_column("search_queries", "query_type")
