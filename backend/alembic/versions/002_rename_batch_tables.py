"""Rename batch tables for consistency

Revision ID: 002_rename_batch
Revises: 001_initial
Create Date: 2026-01-01

Renames:
- collection_jobs → batch_jobs
- article_jobs → batch_articles (FK: batch_job_id → job_id)
- article_errors → batch_errors
- batch_job_logs → batch_logs
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "002_rename_batch"
down_revision = "001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ========================================
    # Step 1: Drop FK constraints (child tables first)
    # ========================================

    # batch_articles (currently article_jobs)
    op.drop_constraint("article_jobs_batch_job_id_fkey", "article_jobs", type_="foreignkey")
    op.drop_constraint("uq_article_jobs_batch_pmcid", "article_jobs", type_="unique")

    # batch_errors (currently article_errors)
    op.drop_constraint("article_errors_job_id_fkey", "article_errors", type_="foreignkey")

    # batch_logs (currently batch_job_logs)
    op.drop_constraint("batch_job_logs_job_id_fkey", "batch_job_logs", type_="foreignkey")

    # batch_failed_items
    op.drop_constraint("batch_failed_items_job_id_fkey", "batch_failed_items", type_="foreignkey")

    # collection_jobs → search_queries FK
    op.drop_constraint("collection_jobs_query_id_fkey", "collection_jobs", type_="foreignkey")

    # ========================================
    # Step 2: Drop indexes
    # ========================================

    # collection_jobs indexes
    op.drop_index("idx_jobs_pending", table_name="collection_jobs")
    op.drop_index("idx_jobs_delayed", table_name="collection_jobs")
    op.drop_index("idx_jobs_stale_lock", table_name="collection_jobs")
    op.drop_index("idx_jobs_type", table_name="collection_jobs")
    op.drop_index("idx_jobs_query", table_name="collection_jobs")

    # article_jobs indexes
    op.drop_index("idx_article_jobs_status", table_name="article_jobs")
    op.drop_index("idx_article_jobs_retry", table_name="article_jobs")

    # article_errors indexes
    op.drop_index("idx_article_errors_job", table_name="article_errors")
    op.drop_index("idx_article_errors_pmcid", table_name="article_errors")
    op.drop_index("idx_article_errors_stage", table_name="article_errors")
    op.drop_index("idx_article_errors_code", table_name="article_errors")

    # batch_job_logs indexes
    op.drop_index("idx_job_logs_job", table_name="batch_job_logs")
    op.drop_index("idx_job_logs_level", table_name="batch_job_logs")

    # ========================================
    # Step 3: Rename tables
    # ========================================

    op.rename_table("collection_jobs", "batch_jobs")
    op.rename_table("article_jobs", "batch_articles")
    op.rename_table("article_errors", "batch_errors")
    op.rename_table("batch_job_logs", "batch_logs")

    # ========================================
    # Step 4: Rename FK column in batch_articles
    # ========================================

    op.alter_column("batch_articles", "batch_job_id", new_column_name="job_id")

    # ========================================
    # Step 5: Recreate FK constraints
    # ========================================

    # batch_jobs → search_queries
    op.create_foreign_key(
        "batch_jobs_query_id_fkey",
        "batch_jobs", "search_queries",
        ["query_id"], ["id"]
    )

    # batch_articles → batch_jobs
    op.create_foreign_key(
        "batch_articles_job_id_fkey",
        "batch_articles", "batch_jobs",
        ["job_id"], ["id"],
        ondelete="CASCADE"
    )

    # batch_errors → batch_jobs
    op.create_foreign_key(
        "batch_errors_job_id_fkey",
        "batch_errors", "batch_jobs",
        ["job_id"], ["id"],
        ondelete="CASCADE"
    )

    # batch_logs → batch_jobs
    op.create_foreign_key(
        "batch_logs_job_id_fkey",
        "batch_logs", "batch_jobs",
        ["job_id"], ["id"],
        ondelete="CASCADE"
    )

    # batch_failed_items → batch_jobs
    op.create_foreign_key(
        "batch_failed_items_job_id_fkey",
        "batch_failed_items", "batch_jobs",
        ["job_id"], ["id"]
    )

    # ========================================
    # Step 6: Recreate indexes with new names
    # ========================================

    # batch_jobs indexes
    op.create_index(
        "idx_batch_jobs_pending",
        "batch_jobs",
        ["priority", "created_at"],
        postgresql_where="status IN ('pending', 'delayed')"
    )
    op.create_index(
        "idx_batch_jobs_delayed",
        "batch_jobs",
        ["next_run_at"],
        postgresql_where="status = 'delayed'"
    )
    op.create_index(
        "idx_batch_jobs_stale_lock",
        "batch_jobs",
        ["locked_at"],
        postgresql_where="status = 'running'"
    )
    op.create_index("idx_batch_jobs_type", "batch_jobs", ["job_type", "status"])
    op.create_index("idx_batch_jobs_query", "batch_jobs", ["query_id", "created_at"])

    # batch_articles indexes
    op.create_index("idx_batch_articles_status", "batch_articles", ["job_id", "status"])
    op.create_index(
        "idx_batch_articles_retry",
        "batch_articles",
        ["status", "next_run_at"],
        postgresql_where="status IN ('pending', 'failed')"
    )

    # batch_articles unique constraint
    op.create_unique_constraint(
        "uq_batch_articles_job_pmcid",
        "batch_articles",
        ["job_id", "pmcid"]
    )

    # batch_errors indexes
    op.create_index("idx_batch_errors_job", "batch_errors", ["job_id", "created_at"])
    op.create_index("idx_batch_errors_pmcid", "batch_errors", ["pmcid"])
    op.create_index("idx_batch_errors_stage", "batch_errors", ["stage"])
    op.create_index("idx_batch_errors_code", "batch_errors", ["error_code"])

    # batch_logs indexes
    op.create_index("idx_batch_logs_job", "batch_logs", ["job_id", "created_at"])
    op.create_index("idx_batch_logs_level", "batch_logs", ["level", "created_at"])


def downgrade() -> None:
    # ========================================
    # Step 1: Drop FK constraints
    # ========================================

    op.drop_constraint("batch_jobs_query_id_fkey", "batch_jobs", type_="foreignkey")
    op.drop_constraint("batch_articles_job_id_fkey", "batch_articles", type_="foreignkey")
    op.drop_constraint("batch_errors_job_id_fkey", "batch_errors", type_="foreignkey")
    op.drop_constraint("batch_logs_job_id_fkey", "batch_logs", type_="foreignkey")
    op.drop_constraint("batch_failed_items_job_id_fkey", "batch_failed_items", type_="foreignkey")

    # ========================================
    # Step 2: Drop indexes
    # ========================================

    op.drop_index("idx_batch_jobs_pending", table_name="batch_jobs")
    op.drop_index("idx_batch_jobs_delayed", table_name="batch_jobs")
    op.drop_index("idx_batch_jobs_stale_lock", table_name="batch_jobs")
    op.drop_index("idx_batch_jobs_type", table_name="batch_jobs")
    op.drop_index("idx_batch_jobs_query", table_name="batch_jobs")

    op.drop_index("idx_batch_articles_status", table_name="batch_articles")
    op.drop_index("idx_batch_articles_retry", table_name="batch_articles")
    op.drop_constraint("uq_batch_articles_job_pmcid", "batch_articles", type_="unique")

    op.drop_index("idx_batch_errors_job", table_name="batch_errors")
    op.drop_index("idx_batch_errors_pmcid", table_name="batch_errors")
    op.drop_index("idx_batch_errors_stage", table_name="batch_errors")
    op.drop_index("idx_batch_errors_code", table_name="batch_errors")

    op.drop_index("idx_batch_logs_job", table_name="batch_logs")
    op.drop_index("idx_batch_logs_level", table_name="batch_logs")

    # ========================================
    # Step 3: Rename FK column back
    # ========================================

    op.alter_column("batch_articles", "job_id", new_column_name="batch_job_id")

    # ========================================
    # Step 4: Rename tables back
    # ========================================

    op.rename_table("batch_jobs", "collection_jobs")
    op.rename_table("batch_articles", "article_jobs")
    op.rename_table("batch_errors", "article_errors")
    op.rename_table("batch_logs", "batch_job_logs")

    # ========================================
    # Step 5: Recreate original FK constraints
    # ========================================

    op.create_foreign_key(
        "collection_jobs_query_id_fkey",
        "collection_jobs", "search_queries",
        ["query_id"], ["id"]
    )
    op.create_foreign_key(
        "article_jobs_batch_job_id_fkey",
        "article_jobs", "collection_jobs",
        ["batch_job_id"], ["id"],
        ondelete="CASCADE"
    )
    op.create_foreign_key(
        "article_errors_job_id_fkey",
        "article_errors", "collection_jobs",
        ["job_id"], ["id"],
        ondelete="CASCADE"
    )
    op.create_foreign_key(
        "batch_job_logs_job_id_fkey",
        "batch_job_logs", "collection_jobs",
        ["job_id"], ["id"],
        ondelete="CASCADE"
    )
    op.create_foreign_key(
        "batch_failed_items_job_id_fkey",
        "batch_failed_items", "collection_jobs",
        ["job_id"], ["id"]
    )

    # ========================================
    # Step 6: Recreate original indexes
    # ========================================

    op.create_index(
        "idx_jobs_pending",
        "collection_jobs",
        ["priority", "created_at"],
        postgresql_where="status IN ('pending', 'delayed')"
    )
    op.create_index(
        "idx_jobs_delayed",
        "collection_jobs",
        ["next_run_at"],
        postgresql_where="status = 'delayed'"
    )
    op.create_index(
        "idx_jobs_stale_lock",
        "collection_jobs",
        ["locked_at"],
        postgresql_where="status = 'running'"
    )
    op.create_index("idx_jobs_type", "collection_jobs", ["job_type", "status"])
    op.create_index("idx_jobs_query", "collection_jobs", ["query_id", "created_at"])

    op.create_index("idx_article_jobs_status", "article_jobs", ["batch_job_id", "status"])
    op.create_index(
        "idx_article_jobs_retry",
        "article_jobs",
        ["status", "next_run_at"],
        postgresql_where="status IN ('pending', 'failed')"
    )
    op.create_unique_constraint(
        "uq_article_jobs_batch_pmcid",
        "article_jobs",
        ["batch_job_id", "pmcid"]
    )

    op.create_index("idx_article_errors_job", "article_errors", ["job_id", "created_at"])
    op.create_index("idx_article_errors_pmcid", "article_errors", ["pmcid"])
    op.create_index("idx_article_errors_stage", "article_errors", ["stage"])
    op.create_index("idx_article_errors_code", "article_errors", ["error_code"])

    op.create_index("idx_job_logs_job", "batch_job_logs", ["job_id", "created_at"])
    op.create_index("idx_job_logs_level", "batch_job_logs", ["level", "created_at"])
