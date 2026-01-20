"""
OARIA RAG (Retrieval-Augmented Generation) Package

Evidence-based RAG system for oncology research questions.
Implements the F-03 specification with:
- BGE-M3 hybrid embeddings (dense + sparse)
- Qdrant vector storage
- Cross-encoder reranking
- Claude-based answer generation
- Citation linking and validation
- Gate 2 retrieval confidence checks

Author: HK
Created: 2025-12-30
"""

from .models import (
    # Chunker
    Chunk,
    # Embedding
    EmbeddingResult,
    ChunkEmbedding,
    # Retrieval
    SearchResult,
    RetrievalOutput,
    # Reranking
    RerankResult,
    RerankerOutput,
    # Generator
    Evidence,
    GeneratorOutput,
    # API
    RAGQuery,
    RAGResponse,
    RAGError,
    # Gate 2
    Gate2Result,
    Gate2Config,
    Gate2FailureReason,
    # Indexer
    IndexStats,
    Paper,
)

from .chunker import TextChunker, chunk_text
from .embedder import BGEM3Embedder, embed_texts
from .indexer import PaperIndexer, create_index, index_papers
from .retriever import HybridRetriever, hybrid_search
from .reranker import CrossEncoderReranker, rerank_documents
from .generator import LLMGenerator, generate_answer, build_prompt
from .pipeline import RAGPipeline, ask

__all__ = [
    # Models - Chunker
    "Chunk",
    # Models - Embedding
    "EmbeddingResult",
    "ChunkEmbedding",
    # Models - Retrieval
    "SearchResult",
    "RetrievalOutput",
    # Models - Reranking
    "RerankResult",
    "RerankerOutput",
    # Models - Generator
    "Evidence",
    "GeneratorOutput",
    # Models - API
    "RAGQuery",
    "RAGResponse",
    "RAGError",
    # Models - Gate 2
    "Gate2Result",
    "Gate2Config",
    "Gate2FailureReason",
    # Models - Indexer
    "IndexStats",
    "Paper",
    # Components
    "TextChunker",
    "BGEM3Embedder",
    "PaperIndexer",
    "HybridRetriever",
    "CrossEncoderReranker",
    "LLMGenerator",
    "RAGPipeline",
    # Convenience functions
    "chunk_text",
    "embed_texts",
    "create_index",
    "index_papers",
    "hybrid_search",
    "rerank_documents",
    "generate_answer",
    "build_prompt",
    "ask",
]
