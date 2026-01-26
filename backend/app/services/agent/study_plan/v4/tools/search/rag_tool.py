"""Unified search tool - 3-tier integrated search."""

import logging
from typing import Any

from app.services.agent.study_plan.v4.tools.base import BaseTool, ToolParameter

logger = logging.getLogger(__name__)


class RAGSearchTool(BaseTool):
    """Unified 3-tier search for scientific papers and evidence.

    Searches across multiple sources:
    - Tier 1: Weaviate (internal vector DB)
    - Tier 2: Europe PMC (external paper database)
    - Tier 3: Tavily (web search for protocols, reagents, etc.)
    """

    @property
    def name(self) -> str:
        return "search_rag"

    @property
    def description(self) -> str:
        return (
            "Search for scientific papers and evidence using 3-tier integrated search. "
            "Combines internal RAG (Weaviate), Europe PMC (paper database), and Tavily (web search). "
            "Use this to find relevant literature, experimental protocols, and reagent information."
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
            filters: Optional filters (year_from, year_to, sections)

        Returns:
            Dict with papers, coverage score, and snippets
        """
        logger.info(f"RAG search: {query[:100]}... (top_k={top_k})")

        try:
            # Import here to avoid circular dependencies
            from app.services.agent.study_plan.shared.rag.search import StudySearchService

            # Parse filters
            year_from = None
            year_to = None
            sections = None
            if filters:
                year_from = filters.get("year_from")
                year_to = filters.get("year_to")
                sections = filters.get("sections")

            # StudySearchService takes a list of queries
            rag_service = StudySearchService(top_k_per_query=top_k)
            result = await rag_service.search_studies(
                queries=[query],  # Wrap single query in list
                year_from=year_from,
                year_to=year_to,
                sections=sections,
            )

            # Convert PaperResult objects to dicts
            papers = []
            snippets = []
            for paper in result.papers:
                paper_dict = {
                    "paper_id": paper.paper_id,
                    "title": paper.title,
                    "journal": paper.journal,
                    "year": paper.year,
                    "score": paper.max_relevance_score,
                }
                papers.append(paper_dict)

                # Extract snippets from paper
                for snippet in paper.snippets:
                    snippet_dict = {
                        "snippet_id": snippet.snippet_id,
                        "paper_id": snippet.paper_id,
                        "section": snippet.section,
                        "text": snippet.text,
                        "relevance_score": snippet.relevance_score,
                    }
                    snippets.append(snippet_dict)

            return {
                "papers": papers[:top_k],
                "snippets": snippets[:top_k * 2],
                "coverage": result.coverage_score,
                "total_found": len(result.papers),
                "tier": 1,
                "source": "rag",
            }

        except ImportError as e:
            # Fallback if RAG service not available
            logger.warning(f"RAG service import error: {e}")
            return {
                "papers": [],
                "snippets": [],
                "coverage": 0.0,
                "total_found": 0,
                "tier": 1,
                "source": "rag",
                "error": f"RAG service not available: {e}",
            }

        except Exception as e:
            logger.error(f"RAG search error: {e}")
            return {
                "papers": [],
                "snippets": [],
                "coverage": 0.0,
                "total_found": 0,
                "tier": 1,
                "source": "rag",
                "error": f"RAG search failed: {e}",
            }

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
