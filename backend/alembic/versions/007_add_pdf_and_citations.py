"""Add PDF and citations fields

- Add PDF-related columns to papers table
- Add paper_citations table for Citations/References

Revision ID: 007_add_pdf_and_citations
Revises: 006_add_retry_count
Create Date: 2026-01-14
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "007_add_pdf_and_citations"
down_revision = "006_add_retry_count"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # papers 테이블에 PDF 관련 컬럼 추가
    op.add_column(
        "papers",
        sa.Column("has_pdf", sa.Boolean(), server_default=sa.text("false")),
    )
    op.add_column(
        "papers",
        sa.Column("pdf_size", sa.Integer()),
    )
    op.add_column(
        "papers",
        sa.Column("pdf_hash", sa.String(64)),
    )
    op.add_column(
        "papers",
        sa.Column("pdf_downloaded_at", sa.DateTime(timezone=True)),
    )

    # papers 테이블에 인용 통계 컬럼 추가
    op.add_column(
        "papers",
        sa.Column("citation_count", sa.Integer(), server_default=sa.text("0")),
    )
    op.add_column(
        "papers",
        sa.Column("reference_count", sa.Integer(), server_default=sa.text("0")),
    )

    # paper_citations 테이블 생성
    op.create_table(
        "paper_citations",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("source_paper_id", sa.String(100), nullable=False),
        sa.Column("target_paper_id", sa.String(100), nullable=False),
        sa.Column("source_pmcid", sa.String(20)),
        sa.Column("source_pmid", sa.String(20)),
        sa.Column("target_pmcid", sa.String(20)),
        sa.Column("target_pmid", sa.String(20)),
        sa.Column("collected_from", sa.String(100), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # paper_citations 인덱스 생성
    op.create_index(
        "uq_paper_citations",
        "paper_citations",
        ["source_paper_id", "target_paper_id"],
        unique=True,
    )
    op.create_index(
        "idx_paper_citations_source",
        "paper_citations",
        ["source_paper_id"],
    )
    op.create_index(
        "idx_paper_citations_target",
        "paper_citations",
        ["target_paper_id"],
    )
    op.create_index(
        "idx_paper_citations_collected",
        "paper_citations",
        ["collected_from"],
    )

    # papers 테이블에 PDF 관련 인덱스 추가
    op.create_index(
        "idx_papers_has_pdf",
        "papers",
        ["has_pdf"],
    )


def downgrade() -> None:
    # 인덱스 삭제
    op.drop_index("idx_papers_has_pdf", table_name="papers")
    op.drop_index("idx_paper_citations_collected", table_name="paper_citations")
    op.drop_index("idx_paper_citations_target", table_name="paper_citations")
    op.drop_index("idx_paper_citations_source", table_name="paper_citations")
    op.drop_index("uq_paper_citations", table_name="paper_citations")

    # paper_citations 테이블 삭제
    op.drop_table("paper_citations")

    # papers 테이블 컬럼 삭제
    op.drop_column("papers", "reference_count")
    op.drop_column("papers", "citation_count")
    op.drop_column("papers", "pdf_downloaded_at")
    op.drop_column("papers", "pdf_hash")
    op.drop_column("papers", "pdf_size")
    op.drop_column("papers", "has_pdf")
