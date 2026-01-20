"""
Cross-Encoder Reranker for RAG Pipeline

Second-stage ranking using cross-encoder model:
- More accurate than bi-encoder (initial retrieval)
- Slower, so only applied to top candidates
- Uses BGE-Reranker-v2-M3 for multilingual support

Author: HK
Created: 2025-12-30
Spec: F-03 Section 3.5
"""

import time
import logging
from typing import Optional

from .models import SearchResult, RerankResult, RerankerOutput

logger = logging.getLogger(__name__)

# Lazy load heavy model
_reranker = None
_reranker_name = None


def _get_reranker(model_name: str = "BAAI/bge-reranker-v2-m3"):
    """Lazy load reranker model."""
    global _reranker, _reranker_name

    if _reranker is not None and _reranker_name == model_name:
        return _reranker

    try:
        from FlagEmbedding import FlagReranker
        logger.info(f"Loading reranker model: {model_name}")
        _reranker = FlagReranker(model_name, use_fp16=True)
        _reranker_name = model_name
        logger.info("Reranker model loaded successfully")
        return _reranker
    except ImportError:
        raise ImportError(
            "FlagEmbedding required for reranking. Install with: pip install FlagEmbedding"
        )


class CrossEncoderReranker:
    """
    Cross-encoder reranker for improved retrieval precision.

    Design Decisions:
    -----------------
    1. WHY CROSS-ENCODER?
       - Bi-encoders (BGE-M3) encode query and document separately
       - Cross-encoders process query+document together
       - Deeper interaction = more accurate relevance scoring

       Bi-encoder (fast, less accurate):
         query → [encoder] → vec1
         doc   → [encoder] → vec2
         score = cosine(vec1, vec2)

       Cross-encoder (slow, more accurate):
         [query, doc] → [encoder] → score

    2. WHY TWO-STAGE RETRIEVAL?
       - Can't run cross-encoder on 50,000 docs (too slow)
       - Use bi-encoder to get top 20 candidates (fast)
       - Use cross-encoder to rerank to top 5 (accurate)

    3. WHY BGE-RERANKER-V2-M3?
       - Matches BGE-M3 embedder (same training)
       - Multilingual (Korean + English)
       - State-of-the-art on MTEB

    Usage:
        reranker = CrossEncoderReranker()

        # Rerank search results
        results = retriever.search("EGFR mutations", top_k=20)
        reranked = reranker.rerank(
            query="EGFR mutations",
            documents=results.results,
            top_n=5
        )
    """

    def __init__(
        self,
        model_name: str = "BAAI/bge-reranker-v2-m3",
        use_fp16: bool = True,
    ):
        """
        Initialize reranker.

        Args:
            model_name: HuggingFace model name
            use_fp16: Use half precision (recommended for GPU)
        """
        self.model_name = model_name
        self.use_fp16 = use_fp16
        self._model = None

    @property
    def model(self):
        """Lazy load model on first use."""
        if self._model is None:
            self._model = _get_reranker(self.model_name)
        return self._model

    def rerank(
        self,
        query: str,
        documents: list[SearchResult],
        top_n: int = 5,
    ) -> RerankerOutput:
        """
        Rerank documents using cross-encoder.

        Args:
            query: Search query
            documents: Documents to rerank
            top_n: Number of top documents to keep

        Returns:
            RerankerOutput with reranked documents
        """
        start_time = time.time()

        if not documents:
            return RerankerOutput(
                query=query,
                results=[],
                rerank_time_ms=0,
                model=self.model_name,
            )

        # Create query-document pairs
        pairs = [(query, doc.text) for doc in documents]

        # Compute reranker scores
        scores = self.model.compute_score(pairs)

        # Handle single result case (returns float instead of list)
        if isinstance(scores, float):
            scores = [scores]

        # Create RerankResult objects with scores
        rerank_results = []
        for doc, score in zip(documents, scores):
            rerank_results.append(RerankResult(
                id=doc.id,
                text=doc.text,
                original_score=doc.score,
                rerank_score=float(score),
                rank=0,  # Will be set after sorting
                metadata=doc.metadata,
                paper_id=doc.paper_id,
                title=doc.title,
                authors=doc.authors,
                doi=doc.doi,
                pmid=doc.pmid,
            ))

        # Sort by rerank score (descending)
        rerank_results.sort(key=lambda x: x.rerank_score, reverse=True)

        # Assign ranks and limit to top_n
        for i, result in enumerate(rerank_results[:top_n]):
            result.rank = i + 1

        rerank_time_ms = (time.time() - start_time) * 1000

        logger.info(
            f"Reranking completed: query='{query[:50]}...', "
            f"input={len(documents)}, output={min(top_n, len(documents))}, "
            f"time={rerank_time_ms:.1f}ms"
        )

        return RerankerOutput(
            query=query,
            results=rerank_results[:top_n],
            rerank_time_ms=rerank_time_ms,
            model=self.model_name,
        )

    def compute_score(
        self,
        query: str,
        text: str,
    ) -> float:
        """
        Compute relevance score for a single query-document pair.

        Args:
            query: Search query
            text: Document text

        Returns:
            Relevance score
        """
        scores = self.model.compute_score([(query, text)])
        return float(scores[0]) if isinstance(scores, list) else float(scores)

    def batch_compute_scores(
        self,
        query: str,
        texts: list[str],
    ) -> list[float]:
        """
        Compute relevance scores for multiple documents.

        Args:
            query: Search query
            texts: List of document texts

        Returns:
            List of relevance scores
        """
        if not texts:
            return []

        pairs = [(query, text) for text in texts]
        scores = self.model.compute_score(pairs)

        if isinstance(scores, float):
            return [scores]
        return [float(s) for s in scores]


# Convenience function
def rerank_documents(
    query: str,
    documents: list[SearchResult],
    top_n: int = 5,
) -> RerankerOutput:
    """Quick function to rerank documents."""
    reranker = CrossEncoderReranker()
    return reranker.rerank(query, documents, top_n)


if __name__ == "__main__":
    print("=== Cross-Encoder Reranker Demo ===\n")

    # Check if FlagEmbedding is available
    try:
        from FlagEmbedding import FlagReranker
        has_flag = True
    except ImportError:
        has_flag = False
        print("FlagEmbedding not installed. Showing structure only.\n")

    if has_flag:
        reranker = CrossEncoderReranker()

        # Demo with sample documents
        query = "EGFR mutations in lung cancer treatment"
        documents = [
            SearchResult(
                id="1",
                score=0.85,
                text="EGFR mutations are found in approximately 15% of NSCLC patients in Western populations.",
                metadata={},
                title="EGFR in NSCLC"
            ),
            SearchResult(
                id="2",
                score=0.82,
                text="Immunotherapy has revolutionized cancer treatment in recent years.",
                metadata={},
                title="Immunotherapy Overview"
            ),
            SearchResult(
                id="3",
                score=0.80,
                text="Osimertinib is a third-generation EGFR TKI effective against T790M resistance mutations.",
                metadata={},
                title="Osimertinib Efficacy"
            ),
        ]

        print(f"Query: {query}\n")
        print("Before reranking:")
        for doc in documents:
            print(f"  [{doc.score:.3f}] {doc.title}")

        results = reranker.rerank(query, documents, top_n=3)

        print("\nAfter reranking:")
        for r in results.results:
            print(f"  [{r.rerank_score:.3f}] {r.title} (was: {r.original_score:.3f})")

        print(f"\nRerank time: {results.rerank_time_ms:.1f}ms")
    else:
        print("Structure overview:")
        print("""
CrossEncoderReranker:
  - rerank(query, documents, top_n) -> RerankerOutput
  - compute_score(query, text) -> float
  - batch_compute_scores(query, texts) -> list[float]

RerankerOutput:
  - query: str
  - results: list[RerankResult]
  - rerank_time_ms: float
  - model: str
        """)
