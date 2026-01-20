"""Add chat tables (conversations, messages, answer_logs)

Revision ID: 003_add_chat
Revises: 002_rename_batch
Create Date: 2026-01-01

Tables:
- conversations: 대화 세션 관리
- messages: 대화 메시지 저장
- answer_logs: 답변 + 근거 저장 (재현용)
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

# revision identifiers, used by Alembic.
revision = "003_add_chat"
down_revision = "002_rename_batch"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ========================================
    # 1. conversations 테이블
    # ========================================
    op.create_table(
        "conversations",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(200), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("message_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("last_message_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_index("idx_conversations_user_id", "conversations", ["user_id"])
    op.create_index("idx_conversations_status", "conversations", ["status"])
    op.create_index("idx_conversations_updated_at", "conversations", ["updated_at"])

    # ========================================
    # 2. messages 테이블
    # ========================================
    op.create_table(
        "messages",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("conversation_id", UUID(as_uuid=True), sa.ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("tokens_used", sa.Integer, nullable=True),
        sa.Column("model", sa.String(50), nullable=True),
        sa.Column("latency_ms", sa.Integer, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )

    op.create_index("idx_messages_conversation_id", "messages", ["conversation_id"])
    op.create_index("idx_messages_created_at", "messages", ["created_at"])

    # ========================================
    # 3. answer_logs 테이블
    # ========================================
    op.create_table(
        "answer_logs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("message_id", UUID(as_uuid=True), sa.ForeignKey("messages.id", ondelete="SET NULL"), nullable=True),
        sa.Column("conversation_id", UUID(as_uuid=True), sa.ForeignKey("conversations.id", ondelete="SET NULL"), nullable=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        # 질문/답변
        sa.Column("question", sa.Text, nullable=False),
        sa.Column("answer", sa.Text, nullable=False),
        # 검색 정보
        sa.Column("search_query", sa.Text, nullable=True),
        sa.Column("search_filters", JSONB, nullable=True),
        # 근거 (재현용 핵심)
        sa.Column("evidence", JSONB, nullable=False),
        # LLM 정보
        sa.Column("model", sa.String(50), nullable=True),
        sa.Column("prompt_tokens", sa.Integer, nullable=True),
        sa.Column("completion_tokens", sa.Integer, nullable=True),
        sa.Column("total_tokens", sa.Integer, nullable=True),
        # 성능
        sa.Column("search_latency_ms", sa.Integer, nullable=True),
        sa.Column("llm_latency_ms", sa.Integer, nullable=True),
        sa.Column("total_latency_ms", sa.Integer, nullable=True),
        # 타임스탬프
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )

    op.create_index("idx_answer_logs_user_id", "answer_logs", ["user_id"])
    op.create_index("idx_answer_logs_conversation_id", "answer_logs", ["conversation_id"])
    op.create_index("idx_answer_logs_created_at", "answer_logs", ["created_at"])

    # ========================================
    # 4. 트리거: update_conversation_stats
    # ========================================
    op.execute("""
        CREATE OR REPLACE FUNCTION update_conversation_stats()
        RETURNS TRIGGER AS $$
        BEGIN
            IF TG_OP = 'INSERT' THEN
                UPDATE conversations
                SET message_count = message_count + 1,
                    last_message_at = NEW.created_at,
                    updated_at = NOW()
                WHERE id = NEW.conversation_id;
                RETURN NEW;
            ELSIF TG_OP = 'DELETE' THEN
                UPDATE conversations
                SET message_count = GREATEST(0, message_count - 1),
                    updated_at = NOW()
                WHERE id = OLD.conversation_id;
                RETURN OLD;
            END IF;
        END;
        $$ LANGUAGE plpgsql;
    """)

    op.execute("""
        CREATE TRIGGER trg_update_conversation_stats
            AFTER INSERT OR DELETE ON messages
            FOR EACH ROW
            EXECUTE FUNCTION update_conversation_stats();
    """)


def downgrade() -> None:
    # 트리거/함수 삭제
    op.execute("DROP TRIGGER IF EXISTS trg_update_conversation_stats ON messages;")
    op.execute("DROP FUNCTION IF EXISTS update_conversation_stats();")

    # 인덱스 삭제
    op.drop_index("idx_answer_logs_created_at", table_name="answer_logs")
    op.drop_index("idx_answer_logs_conversation_id", table_name="answer_logs")
    op.drop_index("idx_answer_logs_user_id", table_name="answer_logs")

    op.drop_index("idx_messages_created_at", table_name="messages")
    op.drop_index("idx_messages_conversation_id", table_name="messages")

    op.drop_index("idx_conversations_updated_at", table_name="conversations")
    op.drop_index("idx_conversations_status", table_name="conversations")
    op.drop_index("idx_conversations_user_id", table_name="conversations")

    # 테이블 삭제 (역순)
    op.drop_table("answer_logs")
    op.drop_table("messages")
    op.drop_table("conversations")
