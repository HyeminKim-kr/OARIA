"""add_study_plan_v3_fields

Revision ID: edc48308ac78
Revises: 009_add_study_plans
Create Date: 2026-01-22 13:07:49.877603

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'edc48308ac78'
down_revision: Union[str, Sequence[str], None] = '009_add_study_plans'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add v3 fields to study_plans table."""
    # Plan A/B
    op.add_column('study_plans', sa.Column('plan_a', sa.Text(), nullable=True))
    op.add_column('study_plans', sa.Column('plan_b', sa.Text(), nullable=True))
    op.add_column('study_plans', sa.Column('plan_config', postgresql.JSONB(astext_type=sa.Text()), nullable=True))

    # Decision Points 결과
    op.add_column('study_plans', sa.Column('dp1_decisions', postgresql.JSONB(astext_type=sa.Text()), server_default='[]', nullable=False))
    op.add_column('study_plans', sa.Column('dp2_decision', sa.String(length=50), nullable=True))
    op.add_column('study_plans', sa.Column('dp3_decision', sa.String(length=50), nullable=True))

    # 3-tier 검색 정보
    op.add_column('study_plans', sa.Column('highest_tier_used', sa.Integer(), server_default='1', nullable=False))
    op.add_column('study_plans', sa.Column('evidence_snippets_v3', postgresql.JSONB(astext_type=sa.Text()), server_default='[]', nullable=False))
    op.add_column('study_plans', sa.Column('search_tier_history', postgresql.ARRAY(sa.Integer()), server_default='{}', nullable=False))


def downgrade() -> None:
    """Remove v3 fields from study_plans table."""
    op.drop_column('study_plans', 'search_tier_history')
    op.drop_column('study_plans', 'evidence_snippets_v3')
    op.drop_column('study_plans', 'highest_tier_used')
    op.drop_column('study_plans', 'dp3_decision')
    op.drop_column('study_plans', 'dp2_decision')
    op.drop_column('study_plans', 'dp1_decisions')
    op.drop_column('study_plans', 'plan_config')
    op.drop_column('study_plans', 'plan_b')
    op.drop_column('study_plans', 'plan_a')
