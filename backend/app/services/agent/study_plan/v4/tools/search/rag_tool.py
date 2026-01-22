"""RAG search tool - Tier 1."""

import logging
from typing import Any

from app.services.agent.study_plan.v4.tools.base import BaseTool, ToolParameter

logger = logging.getLogger(__name__)


class RAGSearchTool(BaseTool):
    """Search internal RAG system for relevant papers.

    Tier 1 search - fastest and cheapest.
    Uses vector similarity to find relevant papers.
    """

    @property
    def name(self) -> str:
        return "search_rag"

    @property
    def description(self) -> str:
        return (
            "Search the internal RAG (Retrieval-Augmented Generation) system "
            "for relevant scientific papers. This is the fastest and cheapest "
            "search option. Use this first before trying external searches."
        )

    @property
    def cost(self) -> float:
        return 0.1  # Low cost

    @property
    def category(self) -> str:
        return "search"

    def _get_parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="query",
                type="str",
                description="Search query for finding relevant papers",
                required=True,
            ),
            ToolParameter(
                name="top_k",
                type="int",
                description="Number of results to return (default: 10)",
                required=False,
                default=10,
            ),
            ToolParameter(
                name="filters",
                type="dict",
                description="Optional filters (e.g., year range, journal)",
                required=False,
                default=None,
            ),
        ]

    async def run(
        self,
        query: str,
        top_k: int = 10,
        filters: dict | None = None,
    ) -> dict[str, Any]:
        """Execute RAG search.

        Args:
            query: Search query
            top_k: Number of results
            filters: Optional filters

        Returns:
            Dict with papers, coverage score, and snippets
        """
        logger.info(f"RAG search: {query[:100]}... (top_k={top_k})")

        try:
            # Import here to avoid circular dependencies
            from app.services.agent.study_plan.rag.search import RAGSearchService

            rag_service = RAGSearchService()
            results = await rag_service.search(
                query=query,
                top_k=top_k,
                filters=filters,
            )

            # Extract papers and compute coverage
            papers = results.get("papers", [])
            snippets = results.get("snippets", [])

            # Calculate coverage based on result quality
            coverage = self._calculate_coverage(papers, snippets)

            return {
                "papers": papers[:top_k],
                "snippets": snippets[:top_k * 2],
                "coverage": coverage,
                "total_found": len(papers),
                "tier": 1,
                "source": "rag",
            }

        except ImportError:
            # Fallback if RAG service not available
            logger.warning("RAG service not available, returning empty results")
            return {
                "papers": [],
                "snippets": [],
                "coverage": 0.0,
                "total_found": 0,
                "tier": 1,
                "source": "rag",
                "error": "RAG service not available",
            }

        except Exception as e:
            logger.error(f"RAG search error: {e}")
            raise

    def _calculate_coverage(
        self,
        papers: list[dict],
        snippets: list[dict],
    ) -> float:
        """Calculate search coverage score.

        Based on:
        - Number of results
        - Relevance scores
        - Evidence density
        """
        if not papers:
            return 0.0

        # Base coverage from count (max 0.5)
        count_score = min(len(papers) / 10, 0.5)

        # Relevance score average (max 0.3)
        relevance_scores = [p.get("score", 0) for p in papers if "score" in p]
        avg_relevance = sum(relevance_scores) / len(relevance_scores) if relevance_scores else 0.5
        relevance_score = avg_relevance * 0.3

        # Evidence density from snippets (max 0.2)
        snippet_count = len(snippets)
        density_score = min(snippet_count / 20, 0.2)

        return min(count_score + relevance_score + density_score, 1.0)
