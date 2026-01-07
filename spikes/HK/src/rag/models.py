"""
RAG Pydantic Models

Defines all data structures used across the RAG pipeline:
- Chunker outputs
- Embedding results
- Search/Retrieval results
- Reranker outputs
- Generator I/O
- Gate 2 validation

Author: HK
Created: 2025-12-30
Spec: F-03 Section 4
"""

from pydantic import BaseModel, Field
from typing import Optional
from datetime import date
from enum import Enum


# ============================================================================
# CHUNKER MODELS
# ============================================================================

class Chunk(BaseModel):
    """A text chunk from a paper."""
    chunk_id: str = Field(..., description="Unique ID: {paper_id}_chunk_{index}")
    paper_id: str = Field(..., description="OpenAlex paper ID")
    chunk_index: int = Field(..., description="Position in paper (0-indexed)")
    text: str = Field(..., description="Chunk text content")
    token_count: int = Field(0, description="Approximate token count")
    char_start: int = Field(0, description="Start position in original text")
    char_end: int = Field(0, description="End position in original text")
    metadata: dict = Field(default_factory=dict, description="Paper metadata")


# ============================================================================
# EMBEDDING MODELS
# ============================================================================

class EmbeddingResult(BaseModel):
    """Result of embedding a text."""
    text: str = Field(..., description="Original text")
    dense_vector: list[float] = Field(..., description="Dense embedding (1024-dim for BGE-M3)")
    sparse_indices: Optional[list[int]] = Field(None, description="Sparse vector indices")
    sparse_values: Optional[list[float]] = Field(None, description="Sparse vector values")
    model: str = Field("BAAI/bge-m3", description="Model used")


class ChunkEmbedding(BaseModel):
    """A chunk with its embeddings."""
    chunk: Chunk
    dense_vector: list[float]
    sparse_indices: Optional[list[int]] = None
    sparse_values: Optional[list[float]] = None


# ============================================================================
# RETRIEVAL MODELS
# ============================================================================

class SearchResult(BaseModel):
    """Single search result from vector store."""
    id: str = Field(..., description="Document/chunk ID")
    score: float = Field(..., description="Similarity score")
    text: str = Field(..., description="Document text")
    metadata: dict = Field(default_factory=dict, description="Additional metadata")

    # Optional fields populated from metadata
    paper_id: Optional[str] = None
    title: Optional[str] = None
    authors: Optional[list[str]] = None
    journal: Optional[str] = None
    journal_tier: Optional[str] = None  # tier1/tier2/tier3/tier4
    publication_date: Optional[str] = None
    publication_year: Optional[int] = None
    cited_by_count: Optional[int] = None
    source: Optional[str] = None  # pmc/arxiv/medrxiv/biorxiv
    concepts: Optional[list[str]] = None
    doi: Optional[str] = None
    pmid: Optional[str] = None
    arxiv_id: Optional[str] = None


class RetrievalOutput(BaseModel):
    """Output from retrieval stage."""
    query: str
    results: list[SearchResult]
    total_found: int
    retrieval_time_ms: float
    embedding_time_ms: float


# ============================================================================
# RERANKER MODELS
# ============================================================================

class RerankResult(BaseModel):
    """Single result after reranking."""
    id: str
    text: str
    original_score: float = Field(..., description="Score from initial retrieval")
    rerank_score: float = Field(..., description="Score from cross-encoder")
    rank: int = Field(..., description="Position after reranking (1-indexed)")
    metadata: dict = Field(default_factory=dict)

    # Populated from metadata
    paper_id: Optional[str] = None
    title: Optional[str] = None
    authors: Optional[list[str]] = None
    doi: Optional[str] = None
    pmid: Optional[str] = None


class RerankerOutput(BaseModel):
    """Output from reranking stage."""
    query: str
    results: list[RerankResult]
    rerank_time_ms: float
    model: str


# ============================================================================
# GENERATOR MODELS
# ============================================================================

class Evidence(BaseModel):
    """
    Single piece of evidence (cited paper).

    Used in RAG response to show which papers were cited.
    """
    openalex_id: str = Field(..., description="OpenAlex paper ID")
    title: str = Field(..., description="Paper title")
    cited_chunk: str = Field(..., description="Text chunk that was cited")
    relevance_score: float = Field(..., description="Reranker score")

    # Display metadata
    authors: list[str] = Field(default_factory=list)
    journal: Optional[str] = None
    publication_date: Optional[date] = None
    doi: Optional[str] = None
    pmid: Optional[str] = None
    url: Optional[str] = None

    # Citation tracking
    citation_markers: list[str] = Field(
        default_factory=list,
        description="Where this paper was cited in answer, e.g., ['[1]', '[1]']"
    )


class GeneratorOutput(BaseModel):
    """Output from LLM generation."""
    answer: str = Field(..., description="Generated answer with citations")
    citations_used: list[int] = Field(default_factory=list, description="Citation numbers used")
    model: str
    input_tokens: int
    output_tokens: int
    generation_time_ms: float
    context_sources: list[dict] = Field(default_factory=list)


# ============================================================================
# RAG QUERY/RESPONSE MODELS (API)
# ============================================================================

class RAGQuery(BaseModel):
    """
    RAG query input with comprehensive filtering options.

    Matches API spec:
    - POST /api/v1/ask
    - Input: { query, top_k, rerank_top_n, filters... }

    Examples:
        # Basic query
        RAGQuery(query="What are EGFR mutations in lung cancer?")

        # High-impact recent papers only
        RAGQuery(
            query="immunotherapy resistance mechanisms",
            min_year=2020,
            min_citations=50,
            journal_tiers=["tier1", "tier2"],
        )

        # Specific sources and concepts
        RAGQuery(
            query="PD-L1 checkpoint inhibitors",
            sources=["pmc"],
            concepts=["immunotherapy", "checkpoint"],
        )
    """
    query: str = Field(..., min_length=5, max_length=1000, description="User's question")
    top_k: int = Field(default=20, ge=5, le=50, description="Initial retrieval count")
    top_n: int = Field(default=5, ge=3, le=10, description="Docs after reranking")

    # Date filters
    min_year: Optional[int] = Field(
        None,
        ge=1900,
        le=2100,
        description="Minimum publication year (e.g., 2020)"
    )
    max_year: Optional[int] = Field(
        None,
        ge=1900,
        le=2100,
        description="Maximum publication year (e.g., 2024)"
    )
    date_from: Optional[date] = Field(None, description="(Deprecated) Use min_year instead")
    date_to: Optional[date] = Field(None, description="(Deprecated) Use max_year instead")

    # Citation filters
    min_citations: Optional[int] = Field(
        None,
        ge=0,
        description="Minimum citation count (e.g., 50 for high-impact papers)"
    )
    max_citations: Optional[int] = Field(
        None,
        ge=0,
        description="Maximum citation count"
    )

    # Source filters
    sources: Optional[list[str]] = Field(
        None,
        description="Paper sources to include: ['pmc', 'arxiv', 'medrxiv', 'biorxiv']"
    )
    exclude_sources: Optional[list[str]] = Field(
        None,
        description="Paper sources to exclude"
    )

    # Journal filters
    journals: Optional[list[str]] = Field(
        None,
        description="Journal names to include (partial match, e.g., ['Nature', 'Cell'])"
    )
    journal_tiers: Optional[list[str]] = Field(
        None,
        description="Journal tiers to include: ['tier1', 'tier2', 'tier3', 'tier4']"
    )

    # Concept/topic filters
    concepts: Optional[list[str]] = Field(
        None,
        description="Required concepts/topics (ANY match, e.g., ['immunotherapy', 'EGFR'])"
    )

    # Author filters
    authors: Optional[list[str]] = Field(
        None,
        description="Author names to search for (ANY match)"
    )

    # Display options
    include_full_abstract: bool = Field(default=True)


class RAGResponse(BaseModel):
    """
    Complete RAG response.

    Matches API spec output:
    - answer: string with inline citations
    - evidence: list of cited papers
    - retrieval_scores: similarity scores
    - processing_time_ms: total time
    """
    answer: str = Field(..., description="Generated answer with [1], [2] citations")
    evidence: list[Evidence] = Field(default_factory=list)
    retrieval_scores: list[float] = Field(default_factory=list)
    avg_relevance: float = Field(0.0, description="Average reranker score")
    processing_time_ms: int = Field(..., description="Total processing time")

    # Gate 2 info
    gate2_passed: bool = True
    gate2_details: dict = Field(default_factory=dict)

    # Metadata
    citations_used: list[int] = Field(default_factory=list)
    model: str = ""
    input_tokens: int = 0
    output_tokens: int = 0


class RAGError(BaseModel):
    """Error response for RAG failures."""
    error_type: str = Field(..., description="insufficient_evidence, gate_failed, etc.")
    message: str = Field(..., description="User-friendly error message")
    suggestion: str = Field("", description="How to improve the query")
    details: dict = Field(default_factory=dict)


# ============================================================================
# GATE 2 MODELS
# ============================================================================

class Gate2FailureReason(str, Enum):
    """Reasons for Gate 2 failure."""
    LOW_SIMILARITY = "low_similarity"
    INSUFFICIENT_DOCS = "insufficient_docs"
    DOMAIN_MISMATCH = "domain_mismatch"


class Gate2Result(BaseModel):
    """
    Gate 2 validation result.

    Output format per spec:
    - passed: boolean
    - reason: low_similarity | insufficient_docs | domain_mismatch
    - message: string
    - max_similarity, relevant_count
    """
    passed: bool
    reason: Optional[Gate2FailureReason] = None
    message: str = ""

    # Metrics
    max_similarity: float = 0.0
    relevant_count: int = 0
    domain_ratio: float = 0.0

    # Detailed breakdown
    details: dict = Field(default_factory=dict)


class Gate2Config(BaseModel):
    """Configuration for Gate 2 validation."""
    similarity_threshold: float = Field(0.7, description="max(similarity) must be >= this")
    min_relevant_docs: int = Field(3, description="Number of docs with score >= min_doc_score")
    min_doc_score: float = Field(0.6, description="Score threshold for 'relevant'")
    domain_ratio_threshold: float = Field(0.80, description="Ratio of oncology docs required")


# ============================================================================
# INDEXER MODELS
# ============================================================================

class IndexStats(BaseModel):
    """Statistics from indexing operation."""
    total_papers: int = 0
    total_chunks: int = 0
    papers_indexed: int = 0
    papers_skipped: int = 0
    errors: list[str] = Field(default_factory=list)
    duration_seconds: float = 0.0


class Paper(BaseModel):
    """
    Paper metadata for full-text indexing.

    OARIA REQUIREMENT: full_text is MANDATORY for indexing.
    Papers without full_text will be skipped during indexing.

    Identifier Notes:
    - PMC papers: Have PMID
    - arXiv papers: Have arXiv ID (stored in openalex_id), NO PMID
    - bioRxiv/medRxiv: Have DOI (10.1101/...), NO PMID
    """
    openalex_id: str  # Primary ID (OpenAlex ID, arXiv ID, or DOI)
    title: str
    abstract: Optional[str] = None  # For display only, NOT indexed
    full_text: Optional[str] = None  # REQUIRED for indexing (from PDF extraction)
    doi: Optional[str] = None  # Available for all sources
    pmid: Optional[str] = None  # Only PMC papers have PMID
    arxiv_id: Optional[str] = None  # Only arXiv papers
    authors: list[str] = Field(default_factory=list)
    journal: Optional[str] = None
    publication_date: Optional[date] = None
    cited_by_count: int = 0
    is_open_access: bool = True  # All indexed papers must be Open Access
    concepts: list[dict] = Field(default_factory=list)
    source: Optional[str] = None  # 'pmc', 'arxiv', 'biorxiv', 'medrxiv'

    def has_full_text(self) -> bool:
        """Check if paper has sufficient full-text for indexing."""
        return bool(self.full_text and len(self.full_text) >= 500)

    def get_indexable_text(self) -> Optional[str]:
        """
        Get full-text content for indexing.

        Returns:
            Full text with title, or None if no full-text available.
            Abstract is NOT used - full-text is REQUIRED.
        """
        if not self.has_full_text():
            return None
        return f"{self.title}\n\n{self.full_text}"

    def get_primary_identifier(self) -> str:
        """Get the best available identifier for citation."""
        if self.doi:
            return f"DOI: {self.doi}"
        if self.pmid:
            return f"PMID: {self.pmid}"
        if self.arxiv_id:
            return f"arXiv: {self.arxiv_id}"
        return self.openalex_id
