"""
OAR-33: Cross-encoder Reranker Implementation

Reranks retrieved documents using cross-encoder scoring for improved relevance.
Cross-encoders are more accurate than bi-encoders but slower (O(n) vs O(1)).

Author: HK
Created: 2025-12-30
Jira: OAR-33
"""

import time
from dataclasses import dataclass
from typing import Optional

# Lazy imports
_cross_encoder = None


def _get_cross_encoder():
    """Lazy import CrossEncoder from sentence-transformers."""
    global _cross_encoder
    if _cross_encoder is None:
        try:
            from sentence_transformers import CrossEncoder
            _cross_encoder = CrossEncoder
        except ImportError:
            raise ImportError(
                "sentence-transformers required. Install with: pip install sentence-transformers"
            )
    return _cross_encoder


@dataclass
class RerankResult:
    """
    A single reranked document with scores.

    Contains both the original retrieval score and the new reranker score
    for comparison and analysis.
    """
    id: str
    text: str
    original_score: float  # From retriever (bi-encoder)
    rerank_score: float    # From cross-encoder
    rank: int              # Position after reranking (1-indexed)
    metadata: dict

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "text": self.text,
            "original_score": self.original_score,
            "rerank_score": self.rerank_score,
            "rank": self.rank,
            "metadata": self.metadata,
        }


@dataclass
class RerankerOutput:
    """Complete reranker output with timing and results."""
    query: str
    results: list[RerankResult]
    rerank_time_ms: float
    top_n: int
    model_name: str

    @property
    def top_result(self) -> Optional[RerankResult]:
        """Best result after reranking."""
        return self.results[0] if self.results else None

    @property
    def rerank_scores(self) -> list[float]:
        """All rerank scores."""
        return [r.rerank_score for r in self.results]

    def to_dict(self) -> dict:
        return {
            "query": self.query,
            "results": [r.to_dict() for r in self.results],
            "rerank_time_ms": self.rerank_time_ms,
            "top_n": self.top_n,
            "model_name": self.model_name,
        }


class CrossEncoderReranker:
    """
    Cross-encoder based reranker for improved relevance ranking.

    Design Decisions:
    -----------------
    1. WHY cross-encoder over bi-encoder?
       - Bi-encoder: Embeds query and doc separately, then compares
         → Fast (precompute doc embeddings) but less accurate
       - Cross-encoder: Processes query+doc together through transformer
         → Slower (can't precompute) but significantly more accurate

       Cross-encoders see the interaction between query and document,
       catching nuances that bi-encoders miss.

    2. WHY rerank AFTER initial retrieval?
       - Cross-encoders are O(n) per query (must score each doc)
       - Can't search millions of docs with cross-encoder
       - Solution: bi-encoder retrieves top-100 → cross-encoder reranks to top-10
       - Best of both: speed + accuracy

    3. WHY these models?
       - ms-marco-MiniLM: Small, fast, trained on MS-MARCO QA dataset
       - BiomedNLP reranker: Domain-specific for medical text
       - BGE reranker: State-of-the-art general reranking

    4. WHY lazy loading?
       - Model is ~100-400MB
       - Don't load until first use
       - Allows quick app startup
    """

    # Supported reranker models
    SUPPORTED_MODELS = {
        "ms-marco-mini": {
            "name": "cross-encoder/ms-marco-MiniLM-L-6-v2",
            "description": "Small, fast general reranker (22M params)",
        },
        "ms-marco-base": {
            "name": "cross-encoder/ms-marco-TinyBERT-L-2-v2",
            "description": "Tiny, fastest general reranker (4.4M params)",
        },
        "bge-reranker": {
            "name": "BAAI/bge-reranker-base",
            "description": "BGE reranker, excellent quality (278M params)",
        },
        "bge-reranker-large": {
            "name": "BAAI/bge-reranker-large",
            "description": "BGE large reranker, best quality (560M params)",
        },
    }

    def __init__(
        self,
        model_key: str = "ms-marco-mini",
        device: Optional[str] = None,
        default_top_n: int = 5,
    ):
        """
        Initialize the reranker.

        Args:
            model_key: Key from SUPPORTED_MODELS or full model name
            device: 'cuda', 'mps', 'cpu', or None for auto-detect
            default_top_n: Default number of top results to return
        """
        # Resolve model name
        if model_key in self.SUPPORTED_MODELS:
            self.model_name = self.SUPPORTED_MODELS[model_key]["name"]
        else:
            self.model_name = model_key

        self.default_top_n = default_top_n
        self._model = None

        # Determine device
        if device:
            self.device = device
        else:
            try:
                import torch
                if torch.cuda.is_available():
                    self.device = "cuda"
                elif torch.backends.mps.is_available():
                    self.device = "mps"
                else:
                    self.device = "cpu"
            except ImportError:
                self.device = "cpu"

    @property
    def model(self):
        """Lazy load the cross-encoder model."""
        if self._model is None:
            CrossEncoder = _get_cross_encoder()
            print(f"Loading reranker model: {self.model_name}")
            print(f"Device: {self.device}")
            self._model = CrossEncoder(self.model_name, device=self.device)
            print("Reranker model loaded.")
        return self._model

    def rerank(
        self,
        query: str,
        documents: list[dict],
        top_n: Optional[int] = None,
        text_field: str = "text",
        score_field: str = "score",
        id_field: str = "id",
    ) -> RerankerOutput:
        """
        Rerank documents by query relevance.

        Process:
        1. Create (query, document) pairs
        2. Score each pair with cross-encoder
        3. Sort by score descending
        4. Return top-n results

        Args:
            query: Search query
            documents: List of document dicts (from retriever)
            top_n: Number of top results to return
            text_field: Key for document text
            score_field: Key for original retrieval score
            id_field: Key for document ID

        Returns:
            RerankerOutput with reranked results
        """
        if not documents:
            return RerankerOutput(
                query=query,
                results=[],
                rerank_time_ms=0,
                top_n=top_n or self.default_top_n,
                model_name=self.model_name,
            )

        top_n = top_n or self.default_top_n
        start_time = time.perf_counter()

        # Create query-document pairs
        pairs = []
        for doc in documents:
            text = doc.get(text_field, "")
            if isinstance(doc, dict):
                text = doc.get(text_field, str(doc))
            else:
                text = str(doc)
            pairs.append([query, text])

        # Score with cross-encoder
        scores = self.model.predict(pairs, show_progress_bar=False)

        # Combine with original data
        scored_docs = []
        for i, (doc, score) in enumerate(zip(documents, scores)):
            scored_docs.append({
                "doc": doc,
                "rerank_score": float(score),
                "original_index": i,
            })

        # Sort by rerank score (descending)
        scored_docs.sort(key=lambda x: x["rerank_score"], reverse=True)

        # Build results
        results = []
        for rank, item in enumerate(scored_docs[:top_n], 1):
            doc = item["doc"]

            # Extract fields
            if isinstance(doc, dict):
                doc_id = doc.get(id_field, f"doc_{item['original_index']}")
                text = doc.get(text_field, "")
                original_score = doc.get(score_field, 0.0)
                metadata = {k: v for k, v in doc.items()
                           if k not in [id_field, text_field, score_field]}
            else:
                doc_id = f"doc_{item['original_index']}"
                text = str(doc)
                original_score = 0.0
                metadata = {}

            results.append(RerankResult(
                id=doc_id,
                text=text,
                original_score=original_score,
                rerank_score=item["rerank_score"],
                rank=rank,
                metadata=metadata,
            ))

        rerank_time = (time.perf_counter() - start_time) * 1000

        return RerankerOutput(
            query=query,
            results=results,
            rerank_time_ms=rerank_time,
            top_n=top_n,
            model_name=self.model_name,
        )

    def rerank_retrieval_result(
        self,
        query: str,
        retrieval_results: list,
        top_n: Optional[int] = None,
    ) -> RerankerOutput:
        """
        Rerank results from Retriever.

        Convenience method that handles SearchResult objects directly.

        Args:
            query: Search query
            retrieval_results: List of SearchResult from retriever
            top_n: Number of top results

        Returns:
            RerankerOutput with reranked results
        """
        # Convert SearchResults to dicts
        documents = []
        for r in retrieval_results:
            if hasattr(r, "to_dict"):
                doc = r.to_dict()
            elif hasattr(r, "__dict__"):
                doc = {
                    "id": getattr(r, "id", "unknown"),
                    "text": getattr(r, "text", ""),
                    "score": getattr(r, "score", 0.0),
                    "metadata": getattr(r, "metadata", {}),
                }
            else:
                doc = {"text": str(r)}
            documents.append(doc)

        return self.rerank(query, documents, top_n=top_n)

    def get_stats(self) -> dict:
        """Get reranker statistics."""
        return {
            "model_name": self.model_name,
            "device": self.device,
            "default_top_n": self.default_top_n,
            "model_loaded": self._model is not None,
        }


# Convenience function
def rerank_documents(
    query: str,
    documents: list[dict],
    top_n: int = 5,
    model_key: str = "ms-marco-mini",
) -> list[dict]:
    """
    Simple function to rerank documents.

    Args:
        query: Search query
        documents: List of document dicts
        top_n: Number of results
        model_key: Reranker model to use

    Returns:
        List of reranked document dicts
    """
    reranker = CrossEncoderReranker(model_key=model_key, default_top_n=top_n)
    output = reranker.rerank(query, documents, top_n=top_n)
    return [r.to_dict() for r in output.results]


if __name__ == "__main__":
    print("=== Cross-Encoder Reranker Demo ===\n")

    # Sample documents (as if from retriever)
    documents = [
        {
            "id": "doc1",
            "text": "EGFR mutations are common in non-small cell lung cancer and predict response to EGFR inhibitors.",
            "score": 0.75,
            "paper_id": "W001",
        },
        {
            "id": "doc2",
            "text": "Immunotherapy has transformed cancer treatment, particularly for melanoma and lung cancer.",
            "score": 0.82,  # Higher retrieval score
            "paper_id": "W002",
        },
        {
            "id": "doc3",
            "text": "Erlotinib and gefitinib are first-generation EGFR tyrosine kinase inhibitors used in lung cancer treatment.",
            "score": 0.70,
            "paper_id": "W003",
        },
        {
            "id": "doc4",
            "text": "BRCA1 mutations increase breast cancer risk but are unrelated to lung cancer EGFR pathways.",
            "score": 0.65,
            "paper_id": "W004",
        },
    ]

    query = "What are EGFR inhibitors for lung cancer?"

    print(f"Query: {query}\n")
    print("Original order (by retrieval score):")
    for doc in sorted(documents, key=lambda x: x["score"], reverse=True):
        print(f"  [{doc['score']:.2f}] {doc['id']}: {doc['text'][:60]}...")

    # Rerank
    reranker = CrossEncoderReranker(model_key="ms-marco-mini", default_top_n=3)
    output = reranker.rerank(query, documents)

    print(f"\nAfter reranking ({output.rerank_time_ms:.1f}ms):")
    for r in output.results:
        print(f"  Rank {r.rank} [{r.rerank_score:.2f}] (was {r.original_score:.2f}) {r.id}: {r.text[:50]}...")

    print(f"\nTop result: {output.top_result.id}")
    print(f"Model: {output.model_name}")
