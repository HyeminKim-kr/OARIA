"""
Hybrid Retriever for RAG Pipeline

Performs hybrid search (dense + sparse) against Qdrant:
- Dense: Semantic similarity (understands meaning)
- Sparse: Keyword matching (finds exact terms)
- Combined via Reciprocal Rank Fusion (RRF)

Author: HK
Created: 2025-12-30
Spec: F-03 Section 3.4
"""

import time
import logging
from typing import Optional
from datetime import date

from qdrant_client import QdrantClient
from qdrant_client.models import (
    SearchRequest,
    NamedVector,
    NamedSparseVector,
    SparseVector,
    Filter,
    FieldCondition,
    Range,
    MatchValue,
    Prefetch,
    FusionQuery,
    Query,
)

from .models import SearchResult, RetrievalOutput
from .embedder import BGEM3Embedder

logger = logging.getLogger(__name__)


class HybridRetriever:
    """
    Hybrid search retriever using BGE-M3 and Qdrant.

    Design Decisions:
    -----------------
    1. WHY HYBRID SEARCH?
       - Dense search alone misses exact keywords ("EGFR")
       - Sparse search alone misses semantics ("lung cancer" vs "pulmonary malignancy")
       - Hybrid captures both

    2. WHY RRF (Reciprocal Rank Fusion)?
       - Simple and effective fusion method
       - No tuning needed
       - Works well across domains

    3. WHY PREFETCH?
       - Retrieves candidates from both indexes separately
       - Then fuses results
       - More accurate than single-pass

    Usage:
        retriever = HybridRetriever()

        # Simple search
        results = retriever.search("EGFR mutations in lung cancer")

        # With filters
        results = retriever.search(
            "EGFR treatment",
            top_k=20,
            min_year=2020,
            min_citations=10,
        )
    """

    COLLECTION_NAME = "oncology_papers"

    def __init__(
        self,
        qdrant_host: str = "localhost",
        qdrant_port: int = 6333,
        embedder: Optional[BGEM3Embedder] = None,
    ):
        """
        Initialize retriever.

        Args:
            qdrant_host: Qdrant server host
            qdrant_port: Qdrant server port
            embedder: Optional embedder instance (shared for efficiency)
        """
        self.qdrant = QdrantClient(host=qdrant_host, port=qdrant_port)
        self.embedder = embedder or BGEM3Embedder()

        logger.info(f"HybridRetriever initialized: {qdrant_host}:{qdrant_port}")

    def _build_filter(
        self,
        min_year: Optional[int] = None,
        max_year: Optional[int] = None,
        min_citations: Optional[int] = None,
        max_citations: Optional[int] = None,
        concepts: Optional[list[str]] = None,
        sources: Optional[list[str]] = None,
        journals: Optional[list[str]] = None,
        journal_tiers: Optional[list[str]] = None,
        authors: Optional[list[str]] = None,
        exclude_sources: Optional[list[str]] = None,
    ) -> Optional[Filter]:
        """
        Build Qdrant filter from search parameters.

        Args:
            min_year: Minimum publication year
            max_year: Maximum publication year
            min_citations: Minimum citation count
            max_citations: Maximum citation count
            concepts: Required concepts (ANY match - OR logic)
            sources: Paper sources to include ['pmc', 'arxiv', 'medrxiv', 'biorxiv']
            journals: Journal names to include (ANY match)
            journal_tiers: Journal tiers to include ['tier1', 'tier2', 'tier3']
            authors: Author names to search for (ANY match)
            exclude_sources: Sources to exclude

        Returns:
            Filter or None if no conditions
        """
        must_conditions = []
        should_conditions = []
        must_not_conditions = []

        # Year range filter
        if min_year is not None:
            must_conditions.append(
                FieldCondition(
                    key="publication_year",
                    range=Range(gte=min_year)
                )
            )

        if max_year is not None:
            must_conditions.append(
                FieldCondition(
                    key="publication_year",
                    range=Range(lte=max_year)
                )
            )

        # Citation count filter
        if min_citations is not None:
            must_conditions.append(
                FieldCondition(
                    key="cited_by_count",
                    range=Range(gte=min_citations)
                )
            )

        if max_citations is not None:
            must_conditions.append(
                FieldCondition(
                    key="cited_by_count",
                    range=Range(lte=max_citations)
                )
            )

        # Source filter (pmc, arxiv, medrxiv, biorxiv)
        if sources:
            source_conditions = [
                FieldCondition(
                    key="source",
                    match=MatchValue(value=source.lower())
                )
                for source in sources
            ]
            if len(source_conditions) == 1:
                must_conditions.append(source_conditions[0])
            else:
                # OR logic for multiple sources
                must_conditions.append(
                    Filter(should=source_conditions)
                )

        # Exclude sources
        if exclude_sources:
            for source in exclude_sources:
                must_not_conditions.append(
                    FieldCondition(
                        key="source",
                        match=MatchValue(value=source.lower())
                    )
                )

        # Journal filter (case-insensitive partial match)
        if journals:
            from qdrant_client.models import MatchText
            journal_conditions = [
                FieldCondition(
                    key="journal",
                    match=MatchText(text=journal)
                )
                for journal in journals
            ]
            if len(journal_conditions) == 1:
                must_conditions.append(journal_conditions[0])
            else:
                must_conditions.append(
                    Filter(should=journal_conditions)
                )

        # Journal tier filter
        if journal_tiers:
            tier_conditions = [
                FieldCondition(
                    key="journal_tier",
                    match=MatchValue(value=tier.lower())
                )
                for tier in journal_tiers
            ]
            if len(tier_conditions) == 1:
                must_conditions.append(tier_conditions[0])
            else:
                must_conditions.append(
                    Filter(should=tier_conditions)
                )

        # Concept filter (ANY match)
        if concepts:
            from qdrant_client.models import MatchAny
            must_conditions.append(
                FieldCondition(
                    key="concepts",
                    match=MatchAny(any=concepts)
                )
            )

        # Author filter (ANY match - searches in author list)
        if authors:
            from qdrant_client.models import MatchAny
            must_conditions.append(
                FieldCondition(
                    key="authors",
                    match=MatchAny(any=authors)
                )
            )

        # Build final filter
        if not must_conditions and not should_conditions and not must_not_conditions:
            return None

        filter_args = {}
        if must_conditions:
            filter_args["must"] = must_conditions
        if should_conditions:
            filter_args["should"] = should_conditions
        if must_not_conditions:
            filter_args["must_not"] = must_not_conditions

        return Filter(**filter_args)

    def search(
        self,
        query: str,
        top_k: int = 20,
        min_year: Optional[int] = None,
        max_year: Optional[int] = None,
        min_citations: Optional[int] = None,
        max_citations: Optional[int] = None,
        concepts: Optional[list[str]] = None,
        sources: Optional[list[str]] = None,
        journals: Optional[list[str]] = None,
        journal_tiers: Optional[list[str]] = None,
        authors: Optional[list[str]] = None,
        exclude_sources: Optional[list[str]] = None,
        dense_weight: float = 0.5,
        sparse_weight: float = 0.5,
    ) -> RetrievalOutput:
        """
        Perform hybrid search with comprehensive filtering.

        Args:
            query: Search query text
            top_k: Number of results to return
            min_year: Filter by minimum publication year
            max_year: Filter by maximum publication year
            min_citations: Filter by minimum citation count
            max_citations: Filter by maximum citation count
            concepts: Filter by concepts (ANY match)
            sources: Filter by source ['pmc', 'arxiv', 'medrxiv', 'biorxiv']
            journals: Filter by journal names (ANY match)
            journal_tiers: Filter by journal tier ['tier1', 'tier2', 'tier3']
            authors: Filter by author names (ANY match)
            exclude_sources: Exclude specific sources
            dense_weight: Weight for dense search (not used with RRF)
            sparse_weight: Weight for sparse search (not used with RRF)

        Returns:
            RetrievalOutput with search results

        Examples:
            # Basic search
            results = retriever.search("EGFR mutations")

            # High-impact recent papers only
            results = retriever.search(
                "immunotherapy resistance",
                min_year=2020,
                min_citations=50,
            )

            # Only Nature/Science/Cell papers
            results = retriever.search(
                "checkpoint inhibitors",
                journal_tiers=["tier1"],
            )

            # Only PMC papers about immunotherapy
            results = retriever.search(
                "PD-L1 expression",
                sources=["pmc"],
                concepts=["immunotherapy"],
            )

            # Papers by specific authors
            results = retriever.search(
                "CRISPR cancer",
                authors=["Zhang F", "Doudna JA"],
            )
        """
        start_time = time.time()

        # Embed query
        embed_start = time.time()
        dense_vec, sparse_vec = self.embedder.embed_query(query)
        embedding_time_ms = (time.time() - embed_start) * 1000

        # Build filter with all parameters
        filters = self._build_filter(
            min_year=min_year,
            max_year=max_year,
            min_citations=min_citations,
            max_citations=max_citations,
            concepts=concepts,
            sources=sources,
            journals=journals,
            journal_tiers=journal_tiers,
            authors=authors,
            exclude_sources=exclude_sources,
        )

        # Perform hybrid search with prefetch + fusion
        search_start = time.time()
        try:
            results = self.qdrant.query_points(
                collection_name=self.COLLECTION_NAME,
                prefetch=[
                    # Dense search
                    Prefetch(
                        query=dense_vec,
                        using="dense",
                        limit=top_k * 2,  # Over-fetch for fusion
                        filter=filters,
                    ),
                    # Sparse search
                    Prefetch(
                        query=SparseVector(
                            indices=sparse_vec[0],
                            values=sparse_vec[1],
                        ),
                        using="sparse",
                        limit=top_k * 2,
                        filter=filters,
                    ),
                ],
                query=FusionQuery(fusion="rrf"),  # Reciprocal Rank Fusion
                limit=top_k,
            )
        except Exception as e:
            # Fallback to dense-only search if hybrid fails
            logger.warning(f"Hybrid search failed, falling back to dense: {e}")
            results = self.qdrant.search(
                collection_name=self.COLLECTION_NAME,
                query_vector=("dense", dense_vec),
                limit=top_k,
                query_filter=filters,
            )

        retrieval_time_ms = (time.time() - search_start) * 1000

        # Convert to SearchResult objects
        search_results = []
        for point in results.points if hasattr(results, 'points') else results:
            payload = point.payload
            search_results.append(SearchResult(
                id=str(point.id),
                score=point.score,
                text=payload.get("text", ""),
                metadata=payload,
                # Paper identifiers
                paper_id=payload.get("paper_id") or payload.get("openalex_id"),
                doi=payload.get("doi"),
                pmid=payload.get("pmid"),
                arxiv_id=payload.get("arxiv_id"),
                # Bibliographic info
                title=payload.get("title"),
                authors=payload.get("authors", []),
                journal=payload.get("journal"),
                journal_tier=payload.get("journal_tier"),
                publication_date=payload.get("publication_date"),
                publication_year=payload.get("publication_year"),
                # Metrics and classification
                cited_by_count=payload.get("cited_by_count"),
                source=payload.get("source"),
                concepts=payload.get("concepts", []),
            ))

        logger.info(
            f"Hybrid search completed: query='{query[:50]}...', "
            f"results={len(search_results)}, "
            f"retrieval_time={retrieval_time_ms:.1f}ms"
        )

        return RetrievalOutput(
            query=query,
            results=search_results,
            total_found=len(search_results),
            retrieval_time_ms=retrieval_time_ms,
            embedding_time_ms=embedding_time_ms,
        )

    def search_dense_only(
        self,
        query: str,
        top_k: int = 20,
        filters: Optional[Filter] = None,
    ) -> list[SearchResult]:
        """
        Perform dense-only search (for comparison/fallback).

        Args:
            query: Search query
            top_k: Number of results
            filters: Optional Qdrant filter

        Returns:
            List of SearchResult
        """
        dense_vec, _ = self.embedder.embed_query(query)

        results = self.qdrant.search(
            collection_name=self.COLLECTION_NAME,
            query_vector=("dense", dense_vec),
            limit=top_k,
            query_filter=filters,
        )

        return [
            SearchResult(
                id=str(point.id),
                score=point.score,
                text=point.payload.get("text", ""),
                metadata=point.payload,
                paper_id=point.payload.get("paper_id"),
                title=point.payload.get("title"),
            )
            for point in results
        ]

    def search_sparse_only(
        self,
        query: str,
        top_k: int = 20,
        filters: Optional[Filter] = None,
    ) -> list[SearchResult]:
        """
        Perform sparse-only search (for comparison/fallback).

        Args:
            query: Search query
            top_k: Number of results
            filters: Optional Qdrant filter

        Returns:
            List of SearchResult
        """
        _, sparse_vec = self.embedder.embed_query(query)

        results = self.qdrant.search(
            collection_name=self.COLLECTION_NAME,
            query_vector=NamedSparseVector(
                name="sparse",
                vector=SparseVector(
                    indices=sparse_vec[0],
                    values=sparse_vec[1],
                )
            ),
            limit=top_k,
            query_filter=filters,
        )

        return [
            SearchResult(
                id=str(point.id),
                score=point.score,
                text=point.payload.get("text", ""),
                metadata=point.payload,
                paper_id=point.payload.get("paper_id"),
                title=point.payload.get("title"),
            )
            for point in results
        ]

    def get_by_paper_id(self, paper_id: str) -> list[SearchResult]:
        """
        Get all chunks for a specific paper.

        Args:
            paper_id: OpenAlex paper ID

        Returns:
            List of chunks for the paper
        """
        results = self.qdrant.scroll(
            collection_name=self.COLLECTION_NAME,
            scroll_filter=Filter(
                must=[
                    FieldCondition(
                        key="paper_id",
                        match=MatchValue(value=paper_id)
                    )
                ]
            ),
            limit=100,
        )

        return [
            SearchResult(
                id=str(point.id),
                score=1.0,
                text=point.payload.get("text", ""),
                metadata=point.payload,
                paper_id=paper_id,
                title=point.payload.get("title"),
            )
            for point in results[0]
        ]


# Convenience function
def hybrid_search(
    query: str,
    top_k: int = 20,
    min_year: Optional[int] = None,
    min_citations: Optional[int] = None,
) -> RetrievalOutput:
    """Quick function for hybrid search."""
    retriever = HybridRetriever()
    return retriever.search(
        query,
        top_k=top_k,
        min_year=min_year,
        min_citations=min_citations,
    )


if __name__ == "__main__":
    print("=== Hybrid Retriever Demo ===\n")

    # Check if Qdrant is available
    try:
        retriever = HybridRetriever()

        # Check collection
        collection_info = retriever.qdrant.get_collection(
            retriever.COLLECTION_NAME
        )
        print(f"Collection: {retriever.COLLECTION_NAME}")
        print(f"Points: {collection_info.points_count}")

        if collection_info.points_count > 0:
            # Demo search
            query = "EGFR mutations in lung cancer"
            results = retriever.search(query, top_k=5)

            print(f"\nQuery: {query}")
            print(f"Results: {len(results.results)}")
            print(f"Retrieval time: {results.retrieval_time_ms:.1f}ms")

            for i, r in enumerate(results.results, 1):
                print(f"\n{i}. [{r.score:.3f}] {r.title}")
                print(f"   {r.text[:100]}...")
        else:
            print("\nNo papers indexed. Run build_index.py first.")

    except Exception as e:
        print(f"Error: {e}")
        print("\nMake sure Qdrant is running and papers are indexed.")
