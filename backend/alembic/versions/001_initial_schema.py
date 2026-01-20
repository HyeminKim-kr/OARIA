"""Initial schema

Revision ID: 001_initial
Revises:
Create Date: 2026-01-01

All tables managed by Alembic:
- papers, paper_authors, paper_sections, paper_relations
- users, social_accounts, user_refresh_tokens
- search_queries, collection_jobs, article_jobs, article_errors
- batch_job_logs, batch_failed_items, watermarks

Admin tables (admin_users, admin_refresh_tokens) are managed by TypeORM.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ========================================
    # Users & Auth
    # ========================================

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("name", sa.String(255), nullable=True),
        sa.Column("picture", sa.String(512), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "social_accounts",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column("provider_id", sa.String(255), nullable=False),
        sa.Column("provider_email", sa.String(255), nullable=True),
        sa.Column("provider_name", sa.String(255), nullable=True),
        sa.Column("provider_picture", sa.String(512), nullable=True),
        sa.Column("access_token", sa.Text(), nullable=True),
        sa.Column("refresh_token", sa.Text(), nullable=True),
        sa.Column("token_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("provider", "provider_id", name="uq_social_accounts_provider_provider_id"),
    )
    op.create_index("ix_social_accounts_user_id", "social_accounts", ["user_id"])
    op.create_index("ix_social_accounts_provider", "social_accounts", ["provider"])

    op.create_table(
        "user_refresh_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("device_info", sa.String(255), nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_reason", sa.String(100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_user_refresh_tokens_user_id", "user_refresh_tokens", ["user_id"])
    op.create_index("ix_user_refresh_tokens_token_hash", "user_refresh_tokens", ["token_hash"])

    # ========================================
    # Papers
    # ========================================

    op.create_table(
        "papers",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("paper_id", sa.String(100), nullable=False),
        sa.Column("pmcid", sa.String(20), nullable=True),
        sa.Column("pmid", sa.String(20), nullable=True),
        sa.Column("doi", sa.String(200), nullable=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("abstract", sa.Text(), nullable=True),
        sa.Column("journal", sa.String(500), nullable=True),
        sa.Column("year", sa.Integer(), nullable=True),
        sa.Column("keywords", postgresql.ARRAY(sa.Text()), nullable=True),
        sa.Column("canonical_bucket", sa.String(100), server_default=sa.text("'oaria-papers'"), nullable=True),
        sa.Column("canonical_prefix", sa.Text(), nullable=True),
        sa.Column("canonical_text_version", sa.String(50), server_default=sa.text("'v1'"), nullable=True),
        sa.Column("canonical_text_hash", sa.String(64), nullable=True),
        sa.Column("canonical_text_length", sa.Integer(), nullable=True),
        sa.Column("raw_xml_hash", sa.String(64), nullable=True),
        sa.Column("parser_version", sa.String(20), server_default=sa.text("'1.0.0'"), nullable=True),
        sa.Column("source", sa.String(50), server_default=sa.text("'europe_pmc'"), nullable=True),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("is_open_access", sa.Boolean(), server_default=sa.text("true"), nullable=True),
        sa.Column("status", sa.String(20), server_default=sa.text("'collected'"), nullable=True),
        sa.Column("chunked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("indexed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("embedding_status", sa.String(20), nullable=True),
        sa.Column("embedding_chunk_count", sa.Integer(), server_default=sa.text("0"), nullable=True),
        sa.Column("embedding_error", sa.Text(), nullable=True),
        sa.Column("embedding_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("pub_types", postgresql.ARRAY(sa.Text()), nullable=True),
        sa.Column("has_correction", sa.Boolean(), server_default=sa.text("false"), nullable=True),
        sa.Column("has_erratum", sa.Boolean(), server_default=sa.text("false"), nullable=True),
        sa.Column("has_retraction", sa.Boolean(), server_default=sa.text("false"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_papers_paper_id", "papers", ["paper_id"], unique=True)
    op.create_index("idx_papers_pmcid_unique", "papers", ["pmcid"], unique=True, postgresql_where=sa.text("pmcid IS NOT NULL"))
    op.create_index("idx_papers_pmid_unique", "papers", ["pmid"], unique=True, postgresql_where=sa.text("pmid IS NOT NULL"))
    op.create_index("idx_papers_doi_unique", "papers", ["doi"], unique=True, postgresql_where=sa.text("doi IS NOT NULL"))
    op.create_index("idx_papers_year", "papers", ["year"])
    op.create_index("idx_papers_status", "papers", ["status"])
    op.create_index("idx_papers_created_at", "papers", ["created_at"])
    op.create_index("idx_papers_keywords", "papers", ["keywords"], postgresql_using="gin")
    op.create_index("idx_papers_embedding_status", "papers", ["embedding_status"])
    op.create_index("idx_papers_embedding_pending", "papers", ["created_at"], postgresql_where=sa.text("embedding_status IS NULL OR embedding_status = 'pending'"))

    op.create_table(
        "paper_authors",
        sa.Column("paper_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("author_order", sa.SmallInteger(), nullable=False),
        sa.Column("author_name", sa.Text(), nullable=False),
        sa.Column("is_corresponding", sa.Boolean(), server_default=sa.text("false"), nullable=True),
        sa.Column("orcid", sa.String(50), nullable=True),
        sa.Column("affiliation", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("paper_id", "author_order"),
        sa.ForeignKeyConstraint(["paper_id"], ["papers.id"], ondelete="CASCADE"),
    )
    op.create_index("idx_paper_authors_name", "paper_authors", ["author_name"])
    op.create_index("idx_paper_authors_name_trgm", "paper_authors", ["author_name"], postgresql_using="gin", postgresql_ops={"author_name": "gin_trgm_ops"})
    op.create_index("idx_paper_authors_corresponding", "paper_authors", ["paper_id"], postgresql_where=sa.text("is_corresponding = true"))

    op.create_table(
        "paper_sections",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("paper_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("section_order", sa.SmallInteger(), nullable=False),
        sa.Column("section_name", sa.String(200), nullable=False),
        sa.Column("section_title", sa.Text(), nullable=True),
        sa.Column("offset_start", sa.Integer(), nullable=False),
        sa.Column("offset_end", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["paper_id"], ["papers.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("paper_id", "section_order", name="uq_paper_sections_order"),
    )
    op.create_index("idx_paper_sections_paper_id", "paper_sections", ["paper_id"])
    op.create_index("idx_paper_sections_name", "paper_sections", ["section_name"])

    op.create_table(
        "paper_relations",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("source_pmid", sa.Text(), nullable=False),
        sa.Column("target_pmid", sa.Text(), nullable=False),
        sa.Column("relation_type", sa.Text(), nullable=False),
        sa.Column("raw_type", sa.Text(), nullable=True),
        sa.Column("reference", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("uq_paper_relations", "paper_relations", ["source_pmid", "target_pmid", "relation_type"], unique=True)
    op.create_index("idx_paper_relations_target", "paper_relations", ["target_pmid"])
    op.create_index("idx_paper_relations_source", "paper_relations", ["source_pmid"])

    # ========================================
    # Batch / Collection
    # ========================================

    op.create_table(
        "search_queries",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("query", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=True),
        sa.Column("priority", sa.Integer(), server_default=sa.text("10"), nullable=True),
        sa.Column("max_results", sa.Integer(), nullable=True),
        sa.Column("year_from", sa.Integer(), nullable=True),
        sa.Column("year_to", sa.Integer(), nullable=True),
        sa.Column("open_access_only", sa.Boolean(), server_default=sa.text("true"), nullable=True),
        sa.Column("max_concurrent", sa.Integer(), server_default=sa.text("35"), nullable=True),
        sa.Column("auto_backfill", sa.Boolean(), server_default=sa.text("false"), nullable=True),
        sa.Column("total_collected", sa.Integer(), server_default=sa.text("0"), nullable=True),
        sa.Column("last_backfill_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_incremental_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=True),
        sa.Column("created_by", sa.String(100), nullable=True),
        sa.Column("updated_by", sa.String(100), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_search_queries_active", "search_queries", ["is_active", "priority"])

    op.create_table(
        "collection_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("job_type", sa.String(20), nullable=False),
        sa.Column("query_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("priority", sa.Integer(), server_default=sa.text("10"), nullable=True),
        sa.Column("query", sa.Text(), nullable=False),
        sa.Column("params", postgresql.JSONB(), nullable=True),
        sa.Column("api_name", sa.String(50), server_default=sa.text("'europe_pmc'"), nullable=True),
        sa.Column("status", sa.String(20), server_default=sa.text("'pending'"), nullable=True),
        sa.Column("checkpoint", postgresql.JSONB(), nullable=True),
        sa.Column("total_count", sa.Integer(), nullable=True),
        sa.Column("processed_count", sa.Integer(), server_default=sa.text("0"), nullable=True),
        sa.Column("success_count", sa.Integer(), server_default=sa.text("0"), nullable=True),
        sa.Column("failed_count", sa.Integer(), server_default=sa.text("0"), nullable=True),
        sa.Column("attempt_count", sa.Integer(), server_default=sa.text("0"), nullable=True),
        sa.Column("max_attempts", sa.Integer(), server_default=sa.text("5"), nullable=True),
        sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("locked_by", sa.String(100), nullable=True),
        sa.Column("last_error_code", sa.String(20), nullable=True),
        sa.Column("last_error_message", sa.Text(), nullable=True),
        sa.Column("last_error_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["query_id"], ["search_queries.id"]),
    )
    op.create_index("idx_jobs_pending", "collection_jobs", ["priority", "created_at"], postgresql_where=sa.text("status IN ('pending', 'delayed')"))
    op.create_index("idx_jobs_delayed", "collection_jobs", ["next_run_at"], postgresql_where=sa.text("status = 'delayed'"))
    op.create_index("idx_jobs_stale_lock", "collection_jobs", ["locked_at"], postgresql_where=sa.text("status = 'running'"))
    op.create_index("idx_jobs_type", "collection_jobs", ["job_type", "status"])
    op.create_index("idx_jobs_query", "collection_jobs", ["query_id", "created_at"])

    op.create_table(
        "article_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("batch_job_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("pmcid", sa.String(20), nullable=False),
        sa.Column("pmid", sa.String(20), nullable=True),
        sa.Column("doi", sa.String(100), nullable=True),
        sa.Column("metadata", postgresql.JSONB(), nullable=True),
        sa.Column("status", sa.String(20), server_default=sa.text("'pending'"), nullable=True),
        sa.Column("attempt_count", sa.Integer(), server_default=sa.text("0"), nullable=True),
        sa.Column("max_attempts", sa.Integer(), server_default=sa.text("3"), nullable=True),
        sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error_code", sa.String(20), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["batch_job_id"], ["collection_jobs.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("batch_job_id", "pmcid", name="uq_article_jobs_batch_pmcid"),
    )
    op.create_index("idx_article_jobs_status", "article_jobs", ["batch_job_id", "status"])
    op.create_index("idx_article_jobs_retry", "article_jobs", ["status", "next_run_at"], postgresql_where=sa.text("status IN ('pending', 'failed')"))

    op.create_table(
        "article_errors",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("pmcid", sa.String(20), nullable=True),
        sa.Column("pmid", sa.String(20), nullable=True),
        sa.Column("doi", sa.String(100), nullable=True),
        sa.Column("stage", sa.String(30), nullable=False),
        sa.Column("error_code", sa.String(50), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=False),
        sa.Column("error_detail", sa.Text(), nullable=True),
        sa.Column("raw_response", sa.Text(), nullable=True),
        sa.Column("context", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["job_id"], ["collection_jobs.id"], ondelete="CASCADE"),
    )
    op.create_index("idx_article_errors_job", "article_errors", ["job_id", "created_at"])
    op.create_index("idx_article_errors_pmcid", "article_errors", ["pmcid"])
    op.create_index("idx_article_errors_stage", "article_errors", ["stage"])
    op.create_index("idx_article_errors_code", "article_errors", ["error_code"])

    op.create_table(
        "batch_job_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("level", sa.String(10), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("details", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["job_id"], ["collection_jobs.id"], ondelete="CASCADE"),
    )
    op.create_index("idx_job_logs_job", "batch_job_logs", ["job_id", "created_at"])
    op.create_index("idx_job_logs_level", "batch_job_logs", ["level", "created_at"])

    op.create_table(
        "batch_failed_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("item_type", sa.String(20), nullable=False),
        sa.Column("item_id", sa.String(100), nullable=True),
        sa.Column("error_code", sa.String(20), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("retry_count", sa.Integer(), server_default=sa.text("0"), nullable=True),
        sa.Column("max_retries", sa.Integer(), server_default=sa.text("3"), nullable=True),
        sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(20), server_default=sa.text("'pending'"), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["job_id"], ["collection_jobs.id"]),
    )
    op.create_index("idx_failed_items_status", "batch_failed_items", ["status", "next_retry_at"])
    op.create_index("idx_failed_items_job", "batch_failed_items", ["job_id"])

    op.create_table(
        "watermarks",
        sa.Column("id", sa.String(100), nullable=False),
        sa.Column("last_completed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("overlap_days", sa.Integer(), server_default=sa.text("2"), nullable=True),
        sa.Column("last_query", sa.Text(), nullable=True),
        sa.Column("last_result_count", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    # ========================================
    # Default Data
    # ========================================

    op.execute("""
        INSERT INTO search_queries (name, query, description, priority) VALUES
            ('폐암 면역치료', 'lung cancer immunotherapy', '폐암 면역치료 관련 논문', 1),
            ('유방암 BRCA', 'breast cancer BRCA mutation', 'BRCA 변이 유방암 논문', 2),
            ('대장암 표적치료', 'colorectal cancer targeted therapy', '대장암 표적치료 논문', 3)
    """)


def downgrade() -> None:
    op.drop_table("watermarks")
    op.drop_table("batch_failed_items")
    op.drop_table("batch_job_logs")
    op.drop_table("article_errors")
    op.drop_table("article_jobs")
    op.drop_table("collection_jobs")
    op.drop_table("search_queries")
    op.drop_table("paper_relations")
    op.drop_table("paper_sections")
    op.drop_table("paper_authors")
    op.drop_table("papers")
    op.drop_table("user_refresh_tokens")
    op.drop_table("social_accounts")
    op.drop_table("users")
