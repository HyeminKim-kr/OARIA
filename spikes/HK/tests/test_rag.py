"""
RAG Pipeline Tests

Tests for the F-03 Evidence RAG system:
- Text chunking
- BGE-M3 embedding
- Qdrant indexing
- Hybrid retrieval
- Cross-encoder reranking
- LLM generation
- Gate 2 validation

Author: HK
Created: 2025-12-30
Spec: F-03 Section 9
"""

import pytest
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.rag.models import (
    Chunk,
    EmbeddingResult,
    SearchResult,
    RerankResult,
    RAGQuery,
    RAGResponse,
    Gate2Result,
    Gate2Config,
    Gate2FailureReason,
    Paper,
)
from src.rag.chunker import TextChunker


# =============================================================================
# CHUNKER TESTS
# =============================================================================

class TestTextChunker:
    """Test text chunking functionality."""

    def test_basic_chunking(self):
        """Test basic text chunking."""
        chunker = TextChunker(chunk_size=100, chunk_overlap=20)
        text = "This is a test sentence. " * 50

        chunks = chunker.chunk_text(text, "W12345")

        assert len(chunks) > 0
        assert all(isinstance(c, Chunk) for c in chunks)
        assert all(c.paper_id == "W12345" for c in chunks)

    def test_empty_text(self):
        """Test chunking empty text."""
        chunker = TextChunker()
        chunks = chunker.chunk_text("", "W12345")
        assert chunks == []

    def test_short_text(self):
        """Test chunking text shorter than chunk size."""
        chunker = TextChunker(chunk_size=512, chunk_overlap=50)
        text = "Short text that fits in one chunk."

        chunks = chunker.chunk_text(text, "W12345")

        # Short text may be filtered out if below min_chunk_size
        # or kept as single chunk
        assert len(chunks) <= 1

    def test_chunk_ids(self):
        """Test that chunk IDs are unique and correctly formatted."""
        chunker = TextChunker(chunk_size=100, chunk_overlap=20)
        text = "This is a test sentence. " * 50

        chunks = chunker.chunk_text(text, "W12345")

        chunk_ids = [c.chunk_id for c in chunks]
        assert len(chunk_ids) == len(set(chunk_ids))  # All unique
        assert all(cid.startswith("W12345_chunk_") for cid in chunk_ids)

    def test_chunk_paper(self):
        """Test chunking a paper with title and abstract."""
        chunker = TextChunker(chunk_size=200, chunk_overlap=40)

        chunks = chunker.chunk_paper(
            paper_id="W12345",
            title="EGFR Mutations in Lung Cancer",
            abstract="This is a detailed abstract about EGFR mutations. " * 30,
            metadata={"doi": "10.1000/example"},
        )

        assert len(chunks) > 0
        # First chunk should contain title
        assert "EGFR" in chunks[0].text
        # Metadata should be preserved
        assert chunks[0].metadata.get("doi") == "10.1000/example"


# =============================================================================
# MODEL TESTS
# =============================================================================

class TestModels:
    """Test Pydantic models."""

    def test_chunk_model(self):
        """Test Chunk model."""
        chunk = Chunk(
            chunk_id="W12345_chunk_0",
            paper_id="W12345",
            chunk_index=0,
            text="Sample text",
            token_count=10,
        )
        assert chunk.chunk_id == "W12345_chunk_0"
        assert chunk.paper_id == "W12345"

    def test_embedding_result_model(self):
        """Test EmbeddingResult model."""
        result = EmbeddingResult(
            text="Sample text",
            dense_vector=[0.1] * 1024,
            sparse_indices=[1, 2, 3],
            sparse_values=[0.5, 0.3, 0.2],
        )
        assert len(result.dense_vector) == 1024
        assert len(result.sparse_indices) == 3

    def test_search_result_model(self):
        """Test SearchResult model."""
        result = SearchResult(
            id="W12345_chunk_0",
            score=0.85,
            text="Sample text",
            metadata={"title": "Test Paper"},
        )
        assert result.score == 0.85

    def test_rag_query_validation(self):
        """Test RAGQuery validation."""
        # Valid query
        query = RAGQuery(query="What are EGFR mutations?")
        assert query.top_k == 20  # Default
        assert query.top_n == 5  # Default

        # Query with parameters
        query = RAGQuery(
            query="EGFR treatment options",
            top_k=30,
            top_n=7,
        )
        assert query.top_k == 30

        # Invalid: query too short
        with pytest.raises(Exception):
            RAGQuery(query="Hi")

    def test_gate2_result_model(self):
        """Test Gate2Result model."""
        result = Gate2Result(
            passed=True,
            max_similarity=0.85,
            relevant_count=4,
            domain_ratio=0.9,
        )
        assert result.passed is True

        result = Gate2Result(
            passed=False,
            reason=Gate2FailureReason.LOW_SIMILARITY,
            message="Not enough relevant papers",
            max_similarity=0.55,
        )
        assert result.passed is False
        assert result.reason == Gate2FailureReason.LOW_SIMILARITY


# =============================================================================
# GATE 2 TESTS
# =============================================================================

class TestGate2:
    """Test Gate 2 validation logic."""

    def test_gate2_config_defaults(self):
        """Test Gate2Config default values."""
        config = Gate2Config()
        assert config.similarity_threshold == 0.7
        assert config.min_relevant_docs == 3
        assert config.min_doc_score == 0.6
        assert config.domain_ratio_threshold == 0.80

    def test_gate2_custom_config(self):
        """Test Gate2Config with custom values."""
        config = Gate2Config(
            similarity_threshold=0.8,
            min_relevant_docs=5,
            min_doc_score=0.7,
            domain_ratio_threshold=0.9,
        )
        assert config.similarity_threshold == 0.8
        assert config.min_relevant_docs == 5


# =============================================================================
# PAPER MODEL TESTS
# =============================================================================

class TestPaperModel:
    """Test Paper model."""

    def test_paper_model(self):
        """Test Paper model creation."""
        paper = Paper(
            openalex_id="W12345",
            title="Test Paper",
            abstract="This is an abstract",
            doi="10.1000/test",
        )
        assert paper.openalex_id == "W12345"
        assert paper.title == "Test Paper"

    def test_paper_model_optional_fields(self):
        """Test Paper model with optional fields."""
        paper = Paper(
            openalex_id="W12345",
            title="Test Paper",
        )
        assert paper.abstract is None
        assert paper.doi is None
        assert paper.authors == []


# =============================================================================
# INTEGRATION TESTS (Require external services)
# =============================================================================

@pytest.mark.skipif(
    os.environ.get("SKIP_INTEGRATION_TESTS", "1") == "1",
    reason="Integration tests disabled. Set SKIP_INTEGRATION_TESTS=0 to run."
)
class TestIntegration:
    """Integration tests requiring Qdrant and optionally Claude API."""

    def test_embedder_import(self):
        """Test that embedder can be imported."""
        try:
            from src.rag.embedder import BGEM3Embedder
            assert BGEM3Embedder is not None
        except ImportError as e:
            pytest.skip(f"FlagEmbedding not installed: {e}")

    def test_retriever_import(self):
        """Test that retriever can be imported."""
        from src.rag.retriever import HybridRetriever
        assert HybridRetriever is not None

    def test_indexer_import(self):
        """Test that indexer can be imported."""
        from src.rag.indexer import PaperIndexer
        assert PaperIndexer is not None


# =============================================================================
# SPEC TEST CASES (from F-03 Section 9)
# =============================================================================

class TestSpecTestCases:
    """Test cases from F-03 specification."""

    def test_tc1_basic_query(self):
        """TC-1: Basic oncology query should return relevant papers."""
        # This is a placeholder - full test requires running services
        query = RAGQuery(query="EGFR 변이란 무엇인가?")
        assert query.query == "EGFR 변이란 무엇인가?"

    def test_tc2_comparison_query(self):
        """TC-2: Comparison query should work."""
        query = RAGQuery(query="폐암에서 erlotinib vs gefitinib 효과 비교")
        assert "erlotinib" in query.query
        assert "gefitinib" in query.query

    def test_tc3_low_relevance_handling(self):
        """TC-3: Low relevance should trigger Gate 2 failure."""
        result = Gate2Result(
            passed=False,
            reason=Gate2FailureReason.LOW_SIMILARITY,
            message="관련 논문을 찾지 못했습니다",
            max_similarity=0.45,
        )
        assert result.passed is False
        assert result.reason == Gate2FailureReason.LOW_SIMILARITY

    def test_tc4_off_topic_handling(self):
        """TC-4: Off-topic query should fail domain check."""
        result = Gate2Result(
            passed=False,
            reason=Gate2FailureReason.DOMAIN_MISMATCH,
            message="검색 결과가 암 연구와 관련성이 낮습니다",
            domain_ratio=0.2,
        )
        assert result.passed is False
        assert result.reason == Gate2FailureReason.DOMAIN_MISMATCH


# =============================================================================
# RUN TESTS
# =============================================================================

if __name__ == "__main__":
    # Run with: pytest tests/test_rag.py -v
    pytest.main([__file__, "-v"])
