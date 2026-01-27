"""Add thinking_history column to agent_jobs table

Revision ID: 012
Revises: 011
Create Date: 2026-01-27

에이전트의 thinking/reasoning 과정을 저장하기 위한 컬럼 추가
- 페이지 새로고침 시에도 진행 상황 복원 가능
- 에이전트 동작 분석 및 디버깅에 활용
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "012_add_thinking_history"
down_revision = "011_drop_study_plans"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # thinking_history: 에이전트의 reasoning 과정 저장
    # 구조: [{"iteration": 1, "title": "...", "bullets": [...], "action": "...", ...}, ...]
    op.add_column(
        "agent_jobs",
        sa.Column(
            "thinking_history",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment="에이전트 thinking/reasoning 이력 (iteration별 기록)",
        ),
    )

    # cumulative_tokens: 전체 토큰 사용량 누적
    op.add_column(
        "agent_jobs",
        sa.Column(
            "cumulative_tokens",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment="누적 토큰 사용량 {prompt_tokens, completion_tokens, total_tokens}",
        ),
    )


def downgrade() -> None:
    op.drop_column("agent_jobs", "cumulative_tokens")
    op.drop_column("agent_jobs", "thinking_history")
