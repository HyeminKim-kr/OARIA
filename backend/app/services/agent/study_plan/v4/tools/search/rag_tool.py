"""RAG Search Tool - Unified 3-tier integrated search.

Combines results from:
- Weaviate (internal vector DB) - paper_id format: pmc:PMC... or pmid:...
- Tavily (web search) - paper_id format: web_...
"""

import logging
from typing import Any

from sqlalchemy import select

from app.database import async_session_maker
from app.models.paper import Paper
from app.services.agent.study_plan.v4.tools.base import BaseTool, ToolParameter

logger = logging.getLogger(__name__)


class RAGSearchTool(BaseTool):
    """Unified 3-tier search for scientific papers and evidence.

    Searches across multiple sources:
    - Tier 1: Weaviate (internal vector DB)
    - Tier 2: Europe PMC (external paper database)
    - Tier 3: Tavily (web search for protocols, reagents, etc.)

    Output format (unified):
    - papers[]: title, url, score, source, citation_text, markdown_link, ...
    - snippets[]: snippet_id, paper_id, section, text, relevance_score, source
    - coverage: float (0-1)
    - source: "rag", "web", or "rag+web"
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
            from app.services.agent.study_plan.shared.rag.search import StudySearchService

            # Parse filters
            year_from = filters.get("year_from") if filters else None
            year_to = filters.get("year_to") if filters else None
            sections = filters.get("sections") if filters else None

            # Execute search (combines Weaviate + Tavily)
            rag_service = StudySearchService(top_k_per_query=top_k)
            result = await rag_service.search_studies(
                queries=[query],
                year_from=year_from,
                year_to=year_to,
                sections=sections,
            )

            # Separate by source type:
            # - Weaviate: paper_id = "pmc:PMC..." or "pmid:..." (need DB lookup for URL)
            # - Tavily: paper_id = "web_..." (URL stored in journal field)
            weaviate_papers = [p for p in result.papers if not p.paper_id.startswith("web_")]
            tavily_papers = [p for p in result.papers if p.paper_id.startswith("web_")]

            # Fetch URLs from DB for Weaviate papers only
            weaviate_ids = [p.paper_id for p in weaviate_papers if p.paper_id]
            url_map = await self._fetch_paper_urls(weaviate_ids) if weaviate_ids else {}

            logger.info(
                f"Search results: {len(weaviate_papers)} from Weaviate, "
                f"{len(tavily_papers)} from Tavily, {len(url_map)} URLs found"
            )

            # Convert to unified output format
            papers = []
            snippets = []

            for paper in result.papers:
                paper_dict, paper_snippets = self._convert_paper(paper, url_map)
                papers.append(paper_dict)
                snippets.extend(paper_snippets)

            # Determine sources used
            sources_used = set(p.get("source") for p in papers)
            source_str = "+".join(sorted(sources_used)) if sources_used else "rag"

            return {
                "papers": papers[:top_k],
                "snippets": snippets[:top_k * 2],
                "coverage": result.coverage_score,
                "total_found": len(result.papers),
                "tier": 1,
                "source": source_str,
            }

        except ImportError as e:
            logger.warning(f"RAG service import error: {e}")
            return self._error_response(f"RAG service not available: {e}")

        except Exception as e:
            logger.error(f"RAG search error: {e}")
            return self._error_response(f"RAG search failed: {e}")

    def _convert_paper(self, paper: Any, url_map: dict) -> tuple[dict, list[dict]]:
        """Convert PaperResult to unified output format.

        Args:
            paper: PaperResult object
            url_map: Dict mapping paper_id to URL info (for Weaviate papers)

        Returns:
            Tuple of (paper_dict, snippets_list)
        """
        is_tavily = paper.paper_id.startswith("web_") or paper.source == "tavily"
        actual_source = "web" if is_tavily else ("rag" if paper.source == "weaviate" else paper.source)

        # Get URL and identifiers based on source
        if is_tavily:
            # Tavily: URL is stored in journal field
            url = paper.journal if paper.journal else None
            doi, pmcid, pmid = None, None, None
            journal_display = self._extract_domain(paper.journal)
        else:
            # Weaviate: lookup from DB
            url_info = url_map.get(paper.paper_id, {})
            url = url_info.get("url")
            doi = url_info.get("doi")
            pmcid = url_info.get("pmcid")
            pmid = url_info.get("pmid")
            journal_display = paper.journal

            # URL fallback: DOI > PMC > PubMed
            if not url:
                url = self._build_url_from_identifiers(doi, pmcid, pmid)

        title_short = paper.title[:50] + "..." if len(paper.title) > 50 else paper.title

        paper_dict = {
            # Common required fields
            "title": paper.title,
            "url": url,
            "score": paper.max_relevance_score,
            "source": actual_source,
            "citation_text": title_short,
            "markdown_link": f"[{title_short}]({url})" if url else title_short,
            # Paper-specific fields
            "paper_id": paper.paper_id,
            "journal": journal_display,
            "year": paper.year if paper.year > 0 else None,
            "doi": doi,
            "pmcid": pmcid,
            "pmid": pmid,
            # Web-specific field
            "content": paper.snippets[0].text if is_tavily and paper.snippets else None,
        }

        # Convert snippets
        snippets = [
            {
                "snippet_id": s.snippet_id,
                "paper_id": s.paper_id,
                "section": s.section,
                "text": s.text,
                "relevance_score": s.relevance_score,
                "source": actual_source,
            }
            for s in paper.snippets
        ]

        return paper_dict, snippets

    async def _fetch_paper_urls(self, paper_ids: list[str]) -> dict[str, dict[str, Any]]:
        """Fetch paper URLs and identifiers from database.

        Args:
            paper_ids: List of paper_ids (format: pmc:PMC... or pmid:...)

        Returns:
            Dict mapping paper_id to {url, doi, pmcid, pmid}
        """
        if not paper_ids:
            return {}

        url_map: dict[str, dict[str, Any]] = {}

        try:
            async with async_session_maker() as session:
                stmt = select(Paper).where(Paper.paper_id.in_(paper_ids))
                result = await session.execute(stmt)
                papers = result.scalars().all()

                for paper in papers:
                    url = self._build_url_from_paper(paper)
                    url_map[paper.paper_id] = {
                        "url": url,
                        "doi": paper.doi,
                        "pmcid": paper.pmcid,
                        "pmid": paper.pmid,
                    }

                # Log missing papers for debugging
                missing = set(paper_ids) - set(url_map.keys())
                if missing:
                    logger.debug(f"Papers not found in DB: {list(missing)[:3]}...")

        except Exception as e:
            logger.warning(f"Failed to fetch paper URLs: {e}")

        return url_map

    def _build_url_from_paper(self, paper: Paper) -> str | None:
        """Build URL from Paper model with priority: source_url > DOI > PMC > PubMed."""
        if paper.source_url:
            return paper.source_url
        return self._build_url_from_identifiers(paper.doi, paper.pmcid, paper.pmid)

    def _build_url_from_identifiers(
        self, doi: str | None, pmcid: str | None, pmid: str | None
    ) -> str | None:
        """Build URL from identifiers with priority: DOI > PMC > PubMed."""
        if doi:
            return f"https://doi.org/{doi}"
        if pmcid:
            return f"https://europepmc.org/article/PMC/{pmcid}"
        if pmid:
            return f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
        return None

    def _extract_domain(self, url: str | None) -> str:
        """Extract domain from URL for display (e.g., 'nature.com')."""
        if not url:
            return ""
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            domain = parsed.netloc or parsed.path.split("/")[0]
            return domain[4:] if domain.startswith("www.") else domain
        except Exception:
            return url[:50] if url else ""

    def _error_response(self, error: str) -> dict[str, Any]:
        """Return standardized error response."""
        return {
            "papers": [],
            "snippets": [],
            "coverage": 0.0,
            "total_found": 0,
            "tier": 1,
            "source": "rag",
            "error": error,
        }
