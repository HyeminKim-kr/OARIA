"""Europe PMC search tool - Tier 2."""

import logging
from typing import Any

from app.services.agent.study_plan.v4.tools.base import BaseTool, ToolParameter

logger = logging.getLogger(__name__)


class EPMCSearchTool(BaseTool):
    """Search Europe PMC for scientific papers.

    Tier 2 search - external API, medium cost.
    Good for finding open access papers with full text.
    """

    @property
    def name(self) -> str:
        return "search_epmc"

    @property
    def description(self) -> str:
        return (
            "Search Europe PMC (PubMed Central Europe) for scientific papers. "
            "This is an external API with access to millions of open access papers. "
            "Use when internal RAG search doesn't find enough relevant results. "
            "Medium cost - use sparingly."
        )

    @property
    def cost(self) -> float:
        return 0.5  # Medium cost

    @property
    def category(self) -> str:
        return "search"

    def _get_parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="query",
                type="str",
                description="Search query for finding papers",
                required=True,
            ),
            ToolParameter(
                name="max_results",
                type="int",
                description="Maximum number of results (default: 20)",
                required=False,
                default=20,
            ),
            ToolParameter(
                name="open_access_only",
                type="bool",
                description="Only return open access papers (default: True)",
                required=False,
                default=True,
            ),
            ToolParameter(
                name="year_from",
                type="int",
                description="Filter papers from this year onwards",
                required=False,
                default=None,
            ),
        ]

    async def run(
        self,
        query: str,
        max_results: int = 20,
        open_access_only: bool = True,
        year_from: int | None = None,
    ) -> dict[str, Any]:
        """Execute Europe PMC search.

        Args:
            query: Search query
            max_results: Maximum results to return
            open_access_only: Filter to open access only
            year_from: Filter by publication year

        Returns:
            Dict with papers and metadata
        """
        logger.info(f"EPMC search: {query[:100]}... (max={max_results})")

        try:
            # Import Europe PMC service
            from app.services.agent.study_plan.shared.search.europe_pmc_service import (
                EuropePmcService,
            )

            epmc_service = EuropePmcService()
            results = await epmc_service.search(
                query=query,
                open_access_only=open_access_only,
                year_from=year_from,
                max_results=max_results,
            )

            # EPMCPaper 객체를 dict로 변환 (URL 포함)
            papers = []
            for paper in results.papers[:max_results]:
                paper_dict = {
                    "pmcid": paper.pmcid,
                    "pmid": paper.pmid,
                    "title": paper.title,
                    "abstract": paper.abstract,
                    "journal": paper.journal,
                    "year": paper.year,
                    "authors": paper.authors,
                    "is_open_access": paper.is_open_access,
                    "citations": paper.citations,
                    "doi": paper.doi,
                    "url": paper.url,
                    # 출처 표시용 필드
                    "citation_text": paper.citation_text,
                    "markdown_link": paper.markdown_link,
                }
                papers.append(paper_dict)

            return {
                "papers": papers,
                "total_found": results.total_count,
                "coverage": self._calculate_coverage(papers),
                "tier": 2,
                "source": "epmc",
            }

        except ImportError:
            logger.warning("EPMC service not available")
            return {
                "papers": [],
                "total_found": 0,
                "coverage": 0.0,
                "tier": 2,
                "source": "epmc",
                "error": "Europe PMC service not available",
            }

        except Exception as e:
            logger.error(f"EPMC search error: {e}")
            raise

    def _calculate_coverage(self, papers: list[dict]) -> float:
        """Calculate coverage based on results."""
        if not papers:
            return 0.0

        # Simple coverage based on count
        return min(len(papers) / 10, 1.0)
