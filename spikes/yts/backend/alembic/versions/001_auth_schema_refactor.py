"""auth schema refactor

- Add social_accounts table
- Migrate users.google_id to social_accounts
- Remove google_id, is_superuser from users
- Add user_refresh_tokens table

Revision ID: 001_auth_schema
Revises: 00eaf7deb7df
Create Date: 2025-12-31

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


# revision identifiers, used by Alembic.
revision: str = "001_auth_schema"
down_revision: Union[str, Sequence[str], None] = "00eaf7deb7df"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""

    # 1. Create social_accounts table
    op.create_table(
        "social_accounts",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column("provider_id", sa.String(255), nullable=False),
        sa.Column("provider_email", sa.String(255), nullable=True),
        sa.Column("provider_name", sa.String(255), nullable=True),
        sa.Column("provider_picture", sa.String(512), nullable=True),
        sa.Column("access_token", sa.Text(), nullable=True),
        sa.Column("refresh_token", sa.Text(), nullable=True),
        sa.Column("token_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("provider", "provider_id", name="uq_social_accounts_provider_provider_id"),
    )
    op.create_index("ix_social_accounts_user_id", "social_accounts", ["user_id"])
    op.create_index("ix_social_accounts_provider", "social_accounts", ["provider"])

    # 2. Migrate existing google_id data to social_accounts
    op.execute(
        """
        INSERT INTO social_accounts (user_id, provider, provider_id, provider_email, provider_name, provider_picture)
        SELECT id, 'google', google_id, email, name, picture
        FROM users
        WHERE google_id IS NOT NULL
        """
    )

    # 3. Drop google_id index and column from users
    op.drop_index("ix_users_google_id", table_name="users")
    op.drop_column("users", "google_id")

    # 4. Drop is_superuser column from users
    op.drop_column("users", "is_superuser")

    # 5. Create user_refresh_tokens table
    op.create_table(
        "user_refresh_tokens",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("device_info", sa.String(255), nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_reason", sa.String(100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_user_refresh_tokens_user_id", "user_refresh_tokens", ["user_id"])
    op.create_index("ix_user_refresh_tokens_token_hash", "user_refresh_tokens", ["token_hash"])
    # Partial index for valid tokens
    op.execute(
        """
        CREATE INDEX ix_user_refresh_tokens_valid
        ON user_refresh_tokens(user_id, expires_at)
        WHERE revoked_at IS NULL
        """
    )


def downgrade() -> None:
    """Downgrade schema."""

    # 1. Drop user_refresh_tokens table
    op.drop_index("ix_user_refresh_tokens_valid", table_name="user_refresh_tokens")
    op.drop_index("ix_user_refresh_tokens_token_hash", table_name="user_refresh_tokens")
    op.drop_index("ix_user_refresh_tokens_user_id", table_name="user_refresh_tokens")
    op.drop_table("user_refresh_tokens")

    # 2. Add is_superuser column back to users
    op.add_column("users", sa.Column("is_superuser", sa.Boolean(), nullable=False, server_default=sa.text("false")))

    # 3. Add google_id column back to users
    op.add_column("users", sa.Column("google_id", sa.String(255), nullable=True))
    op.create_index("ix_users_google_id", "users", ["google_id"], unique=True)

    # 4. Migrate social_accounts data back to users.google_id
    op.execute(
        """
        UPDATE users u
        SET google_id = sa.provider_id
        FROM social_accounts sa
        WHERE u.id = sa.user_id AND sa.provider = 'google'
        """
    )

    # 5. Drop social_accounts table
    op.drop_index("ix_social_accounts_provider", table_name="social_accounts")
    op.drop_index("ix_social_accounts_user_id", table_name="social_accounts")
    op.drop_table("social_accounts")
