"""Add paper_id and conversation_type to conversations

- Add paper_id column (FK to papers.id) for paper-specific chats
- Add conversation_type column ('global' or 'paper')
- Add indexes for efficient querying

Revision ID: 008_add_paper_conversation
Revises: 007_add_pdf_and_citations
Create Date: 2026-01-19
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers, used by Alembic.
revision = "008_add_paper_conversation"
down_revision = "007_add_pdf_and_citations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ========================================
    # 1. paper_id 컬럼 추가
    # ========================================
    op.add_column(
        "conversations",
        sa.Column(
            "paper_id",
            UUID(as_uuid=True),
            sa.ForeignKey("papers.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )

    # ========================================
    # 2. conversation_type 컬럼 추가
    # ========================================
    op.add_column(
        "conversations",
        sa.Column(
            "conversation_type",
            sa.String(20),
            nullable=False,
            server_default="global",
        ),
    )

    # ========================================
    # 3. 인덱스 생성
    # ========================================
    op.create_index(
        "idx_conversations_paper_id",
        "conversations",
        ["paper_id"],
    )
    op.create_index(
        "idx_conversations_type",
        "conversations",
        ["conversation_type"],
    )

    # ========================================
    # 4. CHECK 제약조건 추가
    # ========================================
    op.execute("""
        ALTER TABLE conversations
        ADD CONSTRAINT chk_conversation_type
        CHECK (conversation_type IN ('global', 'paper'))
    """)


def downgrade() -> None:
    # CHECK 제약조건 삭제
    op.execute("ALTER TABLE conversations DROP CONSTRAINT IF EXISTS chk_conversation_type")

    # 인덱스 삭제
    op.drop_index("idx_conversations_type", table_name="conversations")
    op.drop_index("idx_conversations_paper_id", table_name="conversations")

    # 컬럼 삭제
    op.drop_column("conversations", "conversation_type")
    op.drop_column("conversations", "paper_id")
