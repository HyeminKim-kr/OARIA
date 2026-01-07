"""
Pydantic models for OARIA Paper Crawler (F-02)

Based on:
- ADR-001: OpenAlex as paper source (openalex_id as primary key)
- ADR-007: Async-first architecture
- F-02 Specification: Paper data schema

Note: Embeddings are stored in Qdrant (ADR-002), not PostgreSQL.
"""

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class Author(BaseModel):
    """Author information from OpenAlex."""

    name: str = Field(..., description="Author name (e.g., 'Kim, Hyemin')")
    orcid: Optional[str] = Field(None, description="ORCID ID if available")
    institution: Optional[str] = Field(None, description="Affiliation")
    country: Optional[str] = Field(None, description="Country code (e.g., 'KR', 'US')")


class Concept(BaseModel):
    """OpenAlex Concept (topic classification)."""

    id: str = Field(..., description="OpenAlex Concept ID (e.g., 'C126322002')")
    name: str = Field(..., description="Concept name (e.g., 'Oncology')")
    score: float = Field(..., ge=0, le=1, description="Relevance score (0.0 ~ 1.0)")


class Paper(BaseModel):
    """
    Paper record - stored in PostgreSQL.

    Paper metadata from OpenAlex API.
    Embeddings are stored separately in Qdrant (ADR-002).
    """

    # === Primary Key ===
    openalex_id: str = Field(
        ...,
        pattern=r"^W\d+$",
        description="OpenAlex Work ID (e.g., 'W2741809807')"
    )

    # === Core Metadata ===
    title: str = Field(..., min_length=1, description="Paper title")
    abstract: Optional[str] = Field(None, description="Abstract (critical for RAG)")

    # === External Identifiers ===
    doi: Optional[str] = Field(None, description="DOI")
    pmid: Optional[str] = Field(None, description="PubMed ID")

    # === Authors ===
    authors: list[Author] = Field(default_factory=list, description="Author list")

    # === Publication Info ===
    publication_date: Optional[date] = Field(None, description="Publication date")
    journal: Optional[str] = Field(None, description="Journal name")
    publisher: Optional[str] = Field(None, description="Publisher")
    volume: Optional[str] = Field(None)
    issue: Optional[str] = Field(None)

    # === Classification ===
    concepts: list[Concept] = Field(default_factory=list, description="OpenAlex concepts")
    topics: list[str] = Field(default_factory=list, description="Topic classification")
    keywords: list[str] = Field(default_factory=list, description="Author keywords")
    mesh_terms: list[str] = Field(default_factory=list, description="MeSH terms")

    # === Accessibility ===
    is_open_access: bool = Field(False, description="Open access status")
    open_access_url: Optional[str] = Field(None, description="Free PDF URL")
    landing_page_url: Optional[str] = Field(None, description="Publisher page URL")

    # === Impact ===
    cited_by_count: int = Field(0, ge=0, description="Citation count")

    # === Processing Status ===
    collected_at: datetime = Field(default_factory=datetime.utcnow)
    is_embedded: bool = Field(False, description="Qdrant indexing status")
    embedding_error: Optional[str] = Field(None, description="Embedding error message")

    @field_validator("abstract")
    @classmethod
    def validate_abstract_length(cls, v: Optional[str]) -> Optional[str]:
        """Abstract must be at least 50 chars for RAG quality."""
        if v is not None and len(v) < 50:
            return None
        return v


class CrawlerConfig(BaseModel):
    """Crawler configuration for F-02."""

    concept_ids: list[str] = Field(
        default=[
            "C126322002",   # Oncology
            "C502942594",   # Cancer
            "C17744445",    # Cancer research
            "C54355233",    # Tumor
            "C89423630",    # Chemotherapy
            "C2777844474",  # Immunotherapy
        ],
        description="OpenAlex concept IDs to search"
    )
    from_date: date = Field(default=date(2019, 1, 1))
    to_date: date = Field(default_factory=date.today)
    max_results: int = Field(default=50000, description="Max papers to collect")
    per_page: int = Field(default=200, ge=1, le=200, description="Results per API call")
    requests_per_second: float = Field(default=10, description="Rate limit")
    email: str = Field(default="your-email@example.com", description="For polite pool")


class CrawlResult(BaseModel):
    """Crawl operation result."""

    total_fetched: int = Field(..., description="Papers fetched from API")
    total_saved: int = Field(..., description="Papers saved to DB")
    total_skipped: int = Field(..., description="Papers skipped (no abstract, etc.)")
    errors: list[str] = Field(default_factory=list, description="Error messages")
    duration_seconds: float = Field(0, description="Total crawl duration")
