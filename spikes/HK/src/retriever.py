"""
OAR-32: Retriever Implementation

Retrieves relevant document chunks based on query similarity.
Combines embedder and vector store into a unified search interface.

Author: HK
Created: 2025-12-30
Jira: OAR-32
"""

import time
from dataclasses import dataclass, field
from typing import Optional, Any

from embedder import PubMedBERTEmbedder
from vector_store import VectorStore, SearchResult, create_vector_store


@dataclass
class RetrievalResult:
    """
    Complete retrieval result with timing and metadata.

    Contains both the search results and performance metrics
    for monitoring and Gate 2 validation.
    """
    query: str
    results: list[SearchResult]
    query_time_ms: float
    total_time_ms: float
    top_k: int
    filter_applied: Optional[dict] = None

    @property
    def max_score(self) -> float:
        """Highest similarity score (for Gate 2 threshold check)."""
        return self.results[0].score if self.results else 0.0

    @property
    def scores(self) -> list[float]:
        """All similarity scores."""
        return [r.score for r in self.results]

    @property
    def texts(self) -> list[str]:
        """All retrieved texts."""
        return [r.text for r in self.results]

    def to_dict(self) -> dict:
        return {
            "query": self.query,
            "results": [r.to_dict() for r in self.results],
            "query_time_ms": self.query_time_ms,
            "total_time_ms": self.total_time_ms,
            "top_k": self.top_k,
            "max_score": self.max_score,
            "result_count": len(self.results),
            "filter_applied": self.filter_applied,
        }


class Retriever:
    """
    Query-based document retriever using semantic search.

    Design Decisions:
    -----------------
    1. WHY combine embedder + vector store?
       - Single interface for query → results
       - Handles embedding internally (user just provides text)
       - Consistent configuration management

    2. WHY cosine similarity?
       - Works well with normalized embeddings
       - Interpretable scores (0-1 range)
       - Standard for semantic search

    3. WHY return full SearchResult objects?
       - Downstream components (reranker, generator) need all info
       - Metadata enables filtering and citation
       - Scores enable Gate 2 validation

    4. WHY timing metrics?
       - Monitor performance (<100ms target)
       - Identify bottlenecks
       - Gate 2 can check query time
    """

    def __init__(
        self,
        embedder: Optional[PubMedBERTEmbedder] = None,
        vector_store: Optional[VectorStore] = None,
        default_top_k: int = 10,
    ):
        """
        Initialize the retriever.

        Args:
            embedder: PubMedBERTEmbedder instance (creates default if None)
            vector_store: VectorStore instance (creates in-memory if None)
            default_top_k: Default number of results to return
        """
        self.embedder = embedder or PubMedBERTEmbedder()
        self.vector_store = vector_store or create_vector_store("memory")
        self.default_top_k = default_top_k

    def retrieve(
        self,
        query: str,
        top_k: Optional[int] = None,
        filter_dict: Optional[dict] = None,
        min_score: float = 0.0,
    ) -> RetrievalResult:
        """
        Retrieve relevant documents for a query.

        Process:
        1. Embed the query text
        2. Search vector store for similar vectors
        3. Filter by minimum score if specified
        4. Return results with timing info

        Args:
            query: Natural language query
            top_k: Number of results (default: self.default_top_k)
            filter_dict: Metadata filter (e.g., {"paper_id": "W123"})
            min_score: Minimum similarity score threshold

        Returns:
            RetrievalResult with documents and metrics
        """
        start_time = time.perf_counter()
        top_k = top_k or self.default_top_k

        # Step 1: Embed the query
        embed_start = time.perf_counter()
        query_embedding = self.embedder.embed(query)
        embed_time = (time.perf_counter() - embed_start) * 1000

        # Step 2: Search vector store
        query_start = time.perf_counter()
        results = self.vector_store.search(
            query_embedding=query_embedding.tolist(),
            top_k=top_k,
            filter_dict=filter_dict,
        )
        query_time = (time.perf_counter() - query_start) * 1000

        # Step 3: Filter by minimum score
        if min_score > 0:
            results = [r for r in results if r.score >= min_score]

        total_time = (time.perf_counter() - start_time) * 1000

        return RetrievalResult(
            query=query,
            results=results,
            query_time_ms=query_time,
            total_time_ms=total_time,
            top_k=top_k,
            filter_applied=filter_dict,
        )

    def retrieve_batch(
        self,
        queries: list[str],
        top_k: Optional[int] = None,
        filter_dict: Optional[dict] = None,
    ) -> list[RetrievalResult]:
        """
        Retrieve for multiple queries.

        Note: Currently sequential. Could be parallelized for
        production workloads.

        Args:
            queries: List of query texts
            top_k: Number of results per query
            filter_dict: Common filter for all queries

        Returns:
            List of RetrievalResults
        """
        return [
            self.retrieve(q, top_k=top_k, filter_dict=filter_dict)
            for q in queries
        ]

    def get_context_for_generation(
        self,
        query: str,
        top_k: int = 5,
        max_context_chars: int = 8000,
    ) -> tuple[str, list[SearchResult]]:
        """
        Get formatted context for LLM generation.

        Retrieves documents and formats them as numbered context
        suitable for RAG prompts.

        Args:
            query: User query
            top_k: Number of chunks to retrieve
            max_context_chars: Maximum context length

        Returns:
            Tuple of (formatted_context, results)
        """
        result = self.retrieve(query, top_k=top_k)

        context_parts = []
        total_chars = 0

        for i, r in enumerate(result.results, 1):
            # Format: [1] (score: 0.85) Text...
            entry = f"[{i}] (score: {r.score:.2f}, paper: {r.metadata.get('paper_id', 'unknown')})\n{r.text}\n"

            if total_chars + len(entry) > max_context_chars:
                break

            context_parts.append(entry)
            total_chars += len(entry)

        formatted_context = "\n".join(context_parts)
        return formatted_context, result.results

    def index_chunks(
        self,
        chunks: list[dict],
        text_field: str = "text",
        id_field: str = "chunk_id",
    ) -> int:
        """
        Index chunks into the vector store.

        Convenience method that embeds and stores chunks.

        Args:
            chunks: List of chunk dicts with text and metadata
            text_field: Key containing text to embed
            id_field: Key for unique chunk ID (generated if missing)

        Returns:
            Number of chunks indexed
        """
        if not chunks:
            return 0

        # Generate IDs if not present
        for i, chunk in enumerate(chunks):
            if id_field not in chunk:
                paper_id = chunk.get("paper_id", "unknown")
                chunk_idx = chunk.get("chunk_index", i)
                chunk[id_field] = f"{paper_id}_chunk_{chunk_idx}"

        # Embed chunks
        texts = [c.get(text_field, "") for c in chunks]
        embeddings = self.embedder.embed_batch(texts, show_progress=True)

        # Prepare for vector store
        ids = [c[id_field] for c in chunks]
        metadatas = [
            {k: v for k, v in c.items() if k not in [text_field, "embedding"]}
            for c in chunks
        ]

        # Add to store
        self.vector_store.add(
            ids=ids,
            embeddings=embeddings.tolist(),
            texts=texts,
            metadatas=metadatas,
        )

        return len(chunks)

    def get_stats(self) -> dict:
        """Get retriever statistics."""
        return {
            "vector_count": self.vector_store.count(),
            "default_top_k": self.default_top_k,
            "embedder": self.embedder.get_stats(),
        }


# Convenience function
def create_retriever(
    vector_backend: str = "memory",
    embedder_model: str = "pubmedbert",
    **kwargs,
) -> Retriever:
    """
    Create a configured retriever.

    Args:
        vector_backend: "memory", "chroma", or "qdrant"
        embedder_model: Model key for embedder
        **kwargs: Additional args for vector store

    Returns:
        Configured Retriever instance
    """
    embedder = PubMedBERTEmbedder(model_key=embedder_model)
    vector_store = create_vector_store(vector_backend, **kwargs)
    return Retriever(embedder=embedder, vector_store=vector_store)


if __name__ == "__main__":
    print("=== Retriever Demo ===\n")

    # Create retriever with in-memory store and small model for demo
    from embedder import PubMedBERTEmbedder
    from vector_store import InMemoryStore

    embedder = PubMedBERTEmbedder(model_key="bge-small")
    store = InMemoryStore(embedding_dim=384)
    retriever = Retriever(embedder=embedder, vector_store=store, default_top_k=3)

    # Index some sample chunks
    sample_chunks = [
        {
            "text": "EGFR mutations are found in approximately 15% of non-small cell lung cancer patients in Western populations and up to 50% in Asian populations.",
            "paper_id": "W001",
            "chunk_index": 0,
        },
        {
            "text": "Erlotinib and gefitinib are first-generation EGFR tyrosine kinase inhibitors that have shown significant efficacy in EGFR-mutant lung cancer.",
            "paper_id": "W001",
            "chunk_index": 1,
        },
        {
            "text": "Immune checkpoint inhibitors targeting PD-1 and PD-L1 have revolutionized the treatment of melanoma and non-small cell lung cancer.",
            "paper_id": "W002",
            "chunk_index": 0,
        },
        {
            "text": "BRCA1 and BRCA2 mutations significantly increase the risk of breast and ovarian cancer.",
            "paper_id": "W003",
            "chunk_index": 0,
        },
    ]

    print("Indexing sample chunks...")
    count = retriever.index_chunks(sample_chunks)
    print(f"Indexed {count} chunks\n")

    # Test retrieval
    queries = [
        "What are EGFR inhibitors?",
        "Tell me about immunotherapy for cancer",
        "BRCA gene mutations",
    ]

    for query in queries:
        print(f"Query: {query}")
        result = retriever.retrieve(query, top_k=2)
        print(f"  Time: {result.total_time_ms:.1f}ms (search: {result.query_time_ms:.1f}ms)")
        print(f"  Max score: {result.max_score:.3f}")
        for r in result.results:
            print(f"    [{r.score:.3f}] {r.text[:80]}...")
        print()

    # Test context generation
    print("=== Context for Generation ===")
    context, results = retriever.get_context_for_generation(
        "What mutations cause lung cancer?",
        top_k=3
    )
    print(context)
