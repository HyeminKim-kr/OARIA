"""Web search tool - Tier 3."""

import logging
from typing import Any

from app.services.agent.study_plan.v4.tools.base import BaseTool, ToolParameter

logger = logging.getLogger(__name__)


class WebSearchTool(BaseTool):
    """Search the web for information using Tavily.

    Tier 3 search - highest cost, use sparingly.
    Good for finding latest information not in papers.
    """

    @property
    def name(self) -> str:
        return "search_web"

    @property
    def description(self) -> str:
        return (
            "Search the web using Tavily API for the latest information. "
            "Use this when scientific papers don't have enough information. "
            "HIGH COST - limited to 1 call per run, use only when necessary. "
            "Good for protocols, recent news, company information."
        )

    @property
    def cost(self) -> float:
        return 0.9  # High cost

    @property
    def category(self) -> str:
        return "search"

    def _get_parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="query",
                type="str",
                description="Search query",
                required=True,
            ),
            ToolParameter(
                name="search_depth",
                type="str",
                description="Search depth: 'basic' or 'advanced' (default: basic)",
                required=False,
                default="basic",
            ),
            ToolParameter(
                name="max_results",
                type="int",
                description="Maximum results (default: 5)",
                required=False,
                default=5,
            ),
        ]

    async def run(
        self,
        query: str,
        search_depth: str = "basic",
        max_results: int = 5,
    ) -> dict[str, Any]:
        """Execute web search via Tavily.

        Args:
            query: Search query
            search_depth: 'basic' or 'advanced'
            max_results: Maximum results

        Returns:
            Dict with web results
        """
        logger.info(f"Web search: {query[:100]}... (depth={search_depth})")

        try:
            from app.services.agent.study_plan.shared.search.tavily_service import (
                TavilyService,
            )

            tavily_service = TavilyService()
            search_result = await tavily_service.search(
                query=query,
                search_depth=search_depth,
                max_results=max_results,
            )

            # TavilyResult 객체를 dict로 변환 (URL 포함)
            papers = []
            for item in search_result.results[:max_results]:
                paper_dict = {
                    "title": item.title,
                    "url": item.url,
                    "content": item.content,
                    "score": item.score,
                    "published_date": item.published_date,
                    # 출처 표시용 필드
                    "citation_text": item.title[:50] + "..." if len(item.title) > 50 else item.title,
                    "markdown_link": f"[{item.title[:40]}...]({item.url})" if item.url else item.title,
                }
                papers.append(paper_dict)

            return {
                "papers": papers,  # "results" 대신 "papers"로 통일
                "total_found": len(search_result.results),
                "tier": 3,
                "source": "tavily",
            }

        except ImportError:
            logger.warning("Tavily service not available")
            return {
                "results": [],
                "total_found": 0,
                "tier": 3,
                "source": "tavily",
                "error": "Tavily service not available",
            }

        except Exception as e:
            logger.error(f"Web search error: {e}")
            raise
