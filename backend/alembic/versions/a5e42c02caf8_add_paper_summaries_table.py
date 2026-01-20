"""add_paper_summaries_table

Revision ID: a5e42c02caf8
Revises: 008_add_paper_conversation
Create Date: 2026-01-20 00:36:28.174990

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'a5e42c02caf8'
down_revision: Union[str, Sequence[str], None] = '008_add_paper_conversation'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # paper_summaries 테이블 생성
    op.create_table('paper_summaries',
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('paper_id', sa.UUID(), nullable=False),
        sa.Column('summary_type', sa.String(length=20), nullable=False),
        sa.Column('summary', sa.Text(), nullable=False),
        sa.Column('sections_used', postgresql.ARRAY(sa.Text()), nullable=True),
        sa.Column('tokens_used', sa.Integer(), nullable=True),
        sa.Column('embedding_status', sa.String(length=20), nullable=True),
        sa.Column('embedding_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.ForeignKeyConstraint(['paper_id'], ['papers.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('paper_id', 'summary_type', name='uq_paper_summary')
    )
    op.create_index('idx_paper_summaries_paper_id', 'paper_summaries', ['paper_id'], unique=False)
    op.create_index('idx_paper_summaries_embedding_status', 'paper_summaries', ['embedding_status'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('idx_paper_summaries_embedding_status', table_name='paper_summaries')
    op.drop_index('idx_paper_summaries_paper_id', table_name='paper_summaries')
    op.drop_table('paper_summaries')
