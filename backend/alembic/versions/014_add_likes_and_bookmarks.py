"""Add likes and bookmarks tables.

Revision ID: 014_add_likes_bookmarks
Revises: 013_add_podcast_tables
Create Date: 2026-01-30

paper_likes: 유저-논문 좋아요 (복합 PK)
bookmark_collections: 북마크 컬렉션(폴더)
paper_bookmarks: 유저-논문 북마크 (컬렉션 연결)
papers.like_count: 좋아요 수 캐시 컬럼
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "014_add_likes_bookmarks"
down_revision = "013_add_podcast_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. papers 테이블에 like_count 캐시 컬럼 추가
    op.add_column(
        "papers",
        sa.Column("like_count", sa.Integer(), nullable=False, server_default="0"),
    )

    # 2. paper_likes 테이블 생성 (복합 PK)
    op.create_table(
        "paper_likes",
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "paper_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("papers.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("user_id", "paper_id"),
    )
    op.create_index("ix_paper_likes_paper_id", "paper_likes", ["paper_id"])
    op.create_index("ix_paper_likes_user_id", "paper_likes", ["user_id"])

    # 3. bookmark_collections 테이블 생성
    op.create_table(
        "bookmark_collections",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "is_default",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "sort_order", sa.Integer(), nullable=False, server_default="0"
        ),
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
    op.create_index(
        "ix_bookmark_collections_user_id", "bookmark_collections", ["user_id"]
    )
    # Partial unique: 유저당 기본 컬렉션 1개만
    op.create_index(
        "uq_bookmark_collections_user_default",
        "bookmark_collections",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text("is_default = true"),
    )

    # 4. paper_bookmarks 테이블 생성
    op.create_table(
        "paper_bookmarks",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "paper_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("papers.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "collection_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("bookmark_collections.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "user_id", "paper_id", name="uq_paper_bookmarks_user_paper"
        ),
    )
    op.create_index(
        "ix_paper_bookmarks_user_id", "paper_bookmarks", ["user_id"]
    )
    op.create_index(
        "ix_paper_bookmarks_paper_id", "paper_bookmarks", ["paper_id"]
    )
    op.create_index(
        "ix_paper_bookmarks_collection_id",
        "paper_bookmarks",
        ["collection_id"],
    )


def downgrade() -> None:
    op.drop_table("paper_bookmarks")
    op.drop_table("bookmark_collections")
    op.drop_table("paper_likes")
    op.drop_column("papers", "like_count")
