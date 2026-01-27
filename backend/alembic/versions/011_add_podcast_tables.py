"""Add podcast tables.

Revision ID: 011_add_podcast_tables
Revises: 010_add_agent_jobs_and_notifications
Create Date: 2026-01-27

F-11: Agentic Podcast System
- podcast_subscriptions: User subscriptions for automated generation
- podcast_episodes: Generated podcast episodes
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "011_add_podcast_tables"
down_revision = "010_add_agent_jobs_notifications"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create podcast_subscriptions table
    op.create_table(
        "podcast_subscriptions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        # Subscription topics
        sa.Column(
            "topics",
            postgresql.ARRAY(sa.String(200)),
            nullable=False,
        ),
        # Generation settings
        sa.Column(
            "frequency",
            sa.String(20),
            nullable=False,
            server_default="weekly",
        ),
        sa.Column(
            "episode_style",
            sa.String(20),
            nullable=False,
            server_default="two_hosts",
        ),
        sa.Column(
            "episode_duration",
            sa.String(10),
            nullable=False,
            server_default="short",
        ),
        sa.Column(
            "language",
            sa.String(5),
            nullable=False,
            server_default="ko",
        ),
        # Status
        sa.Column(
            "is_active",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column(
            "last_generated_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
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
            onupdate=sa.func.now(),
        ),
    )

    # Create podcast_episodes table
    op.create_table(
        "podcast_episodes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "subscription_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("podcast_subscriptions.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
        # Goal & Config
        sa.Column("goal", sa.Text, nullable=False),
        sa.Column(
            "duration",
            sa.String(10),
            nullable=False,
            server_default="short",
        ),
        sa.Column(
            "style",
            sa.String(20),
            nullable=False,
            server_default="two_hosts",
        ),
        sa.Column(
            "paper_mode",
            sa.String(20),
            nullable=False,
            server_default="auto",
        ),
        sa.Column(
            "language",
            sa.String(5),
            nullable=False,
            server_default="ko",
        ),
        # Content
        sa.Column("title", sa.String(500), nullable=True),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("script", postgresql.JSONB, nullable=True),
        sa.Column("audio_url", sa.String(500), nullable=True),
        sa.Column("duration_seconds", sa.Integer, nullable=True),
        # Evidence
        sa.Column("paper_ids", postgresql.ARRAY(sa.String(50)), nullable=True),
        sa.Column("references", postgresql.JSONB, nullable=True),
        # Execution metadata
        sa.Column("task_results", postgresql.JSONB, nullable=True),
        sa.Column("search_filters", postgresql.JSONB, nullable=True),
        # Status
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="pending",
            index=True,
        ),
        sa.Column("error_message", sa.Text, nullable=True),
        # Timestamps
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
            index=True,
        ),
        sa.Column(
            "completed_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )

    # Create indexes for common queries
    op.create_index(
        "ix_podcast_subscriptions_active",
        "podcast_subscriptions",
        ["is_active", "frequency"],
    )
    op.create_index(
        "ix_podcast_episodes_user_created",
        "podcast_episodes",
        ["user_id", "created_at"],
    )


def downgrade() -> None:
    # Drop indexes
    op.drop_index("ix_podcast_episodes_user_created", "podcast_episodes")
    op.drop_index("ix_podcast_subscriptions_active", "podcast_subscriptions")

    # Drop tables
    op.drop_table("podcast_episodes")
    op.drop_table("podcast_subscriptions")
