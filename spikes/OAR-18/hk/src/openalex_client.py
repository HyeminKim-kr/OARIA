"""
OpenAlex API Client for OARIA Paper Crawler (F-02)

Author: Hyemin Kim (AI Lead)
Task: OAR-94

Why OpenAlex instead of PubMed? (ADR-001)
- OpenAlex includes ALL PubMed papers + 200M more
- Better API: cursor pagination, no key required
- Richer metadata: citations, concepts, institutions
"""

# === IMPORTS ===

# Standard library
import asyncio                      # For async/await and sleep (rate limiting)
from datetime import date, datetime
from typing import AsyncGenerator, Optional   # Type hints for Python 3.9 compatibility

# Third-party
import httpx                        # Async HTTP client (like requests, but async)
import structlog                    # Structured logging (key=value format)

# Our models (from OAR-20 schema work)
from models import Paper, Author, Concept, CrawlerConfig

# Setup logger
logger = structlog.get_logger()


# === CLIENT CLASS ===

class OpenAlexClient:
    """
    Async client for OpenAlex API.

    Usage:
        async with OpenAlexClient(email="you@example.com") as client:
            async for batch in client.search_papers(config):
                for paper in batch:
                    print(paper.title)

    Why async context manager (async with)?
    - Ensures HTTP connection is properly opened and closed
    - Prevents resource leaks
    """

    BASE_URL = "https://api.openalex.org"

    def __init__(self, email: Optional[str] = None):
        """
        Initialize client.

        Args:
            email: Your email for "polite pool" access.
                   Without email: 1 request/second
                   With email: 10 requests/second (10x faster!)
        """
        self.email = email
        self._client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self) -> "OpenAlexClient":
        """Called when entering 'async with' block. Opens HTTP connection."""
        self._client = httpx.AsyncClient(
            timeout=30.0,  # 30 second timeout per request
            headers={
                # Identify ourselves to OpenAlex (good practice)
                "User-Agent": f"OARIA/1.0 (mailto:{self.email})" if self.email else "OARIA/1.0"
            }
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Called when exiting 'async with' block. Closes HTTP connection."""
        if self._client:
            await self._client.aclose()
            self._client = None


    # === Part 2: Filter Builder ===

    def _build_filter_string(self, config: CrawlerConfig) -> str:
        """
        Convert CrawlerConfig into OpenAlex filter syntax.

        OpenAlex filter rules:
        - Multiple values for SAME field (OR): use pipe "|"
          Example: concepts.id:C123|C456 means "C123 OR C456"

        - Multiple DIFFERENT fields (AND): use comma ","
          Example: concepts.id:C123,has_abstract:true means "concept C123 AND has abstract"

        Args:
            config: Our crawler configuration

        Returns:
            Filter string like "concepts.id:C123|C456,has_abstract:true,publication_year:>2023"
        """
        filters = []

        # --- Filter 1: Oncology concepts (OR combination) ---
        # We want papers that match ANY of our oncology concepts
        if config.concept_ids:
            concept_filter = "|".join(config.concept_ids)  # C123|C456|C789
            filters.append(f"concepts.id:{concept_filter}")

        # --- Filter 2: Date range ---
        # publication_year:>2023 means "published in 2024 or later"
        if config.from_date:
            # Subtract 1 because we want >= from_date.year
            filters.append(f"publication_year:>{config.from_date.year - 1}")
        if config.to_date:
            # Add 1 because we want <= to_date.year
            filters.append(f"publication_year:<{config.to_date.year + 1}")

        # --- Filter 3: Must have abstract (CRITICAL for RAG!) ---
        # Papers without abstracts are useless for our system
        filters.append("has_abstract:true")

        # --- Filter 4: Only peer-reviewed articles ---
        # Exclude preprints, datasets, books, etc.
        # "journal-article" = regular papers, "review" = review papers
        filters.append("type:journal-article|review")

        # Join all filters with comma (AND logic)
        return ",".join(filters)


    # === Part 3: Abstract Reconstruction ===

    def _extract_abstract(self, raw: dict) -> Optional[str]:
        """
        Reconstruct abstract from OpenAlex's inverted index format.

        WHY INVERTED INDEX?
        OpenAlex compresses abstracts to save storage. Instead of storing:
            "EGFR mutations are common in lung cancer patients"

        They store:
            {"EGFR": [0], "mutations": [1], "are": [2], "common": [3],
             "in": [4], "lung": [5], "cancer": [6], "patients": [7]}

        Each word maps to its position(s) in the text. A word appearing
        multiple times has multiple positions: {"the": [0, 5, 12]}

        HOW WE RECONSTRUCT:
        1. Create (position, word) pairs: [(0, "EGFR"), (1, "mutations"), ...]
        2. Sort by position: already sorted in this example
        3. Join with spaces: "EGFR mutations are common in lung cancer patients"

        Args:
            raw: Raw paper data from OpenAlex API

        Returns:
            Reconstructed abstract string, or None if no abstract
        """
        inverted = raw.get("abstract_inverted_index")

        # No abstract available
        if not inverted:
            return None

        # Step 1: Build (position, word) pairs
        # Example: {"EGFR": [0, 15], "mutations": [1]} becomes
        #          [(0, "EGFR"), (15, "EGFR"), (1, "mutations")]
        position_word_pairs = []
        for word, positions in inverted.items():
            for pos in positions:
                position_word_pairs.append((pos, word))

        # Step 2: Sort by position
        # [(0, "EGFR"), (1, "mutations"), (15, "EGFR")]
        position_word_pairs.sort(key=lambda x: x[0])

        # Step 3: Extract just the words and join
        # "EGFR mutations ... EGFR"
        abstract = " ".join(word for _, word in position_word_pairs)

        return abstract

    def _parse_date(self, date_str: Optional[str]) -> Optional[date]:
        """
        Parse ISO date string to Python date object.

        Args:
            date_str: Date like "2024-03-15" or None

        Returns:
            date object or None if invalid/missing
        """
        if not date_str:
            return None
        try:
            return date.fromisoformat(date_str)
        except ValueError:
            return None


    # === Part 4: Paper Parser ===

    def _parse_paper(self, raw: dict) -> Optional[Paper]:
        """
        Convert raw OpenAlex API response to our Paper model.

        This is where we transform OpenAlex's JSON structure into our
        PostgreSQL-ready Paper object (from OAR-73 schema).

        Args:
            raw: Raw JSON dict from OpenAlex API

        Returns:
            Paper object, or None if paper should be skipped
        """

        # --- Step 1: Extract and validate abstract ---
        # Abstract is REQUIRED for RAG - skip papers without it
        abstract = self._extract_abstract(raw)
        if not abstract or len(abstract) < 50:
            # Too short = probably not useful for RAG
            return None

        # --- Step 2: Extract OpenAlex ID ---
        # API returns: "https://openalex.org/W2741809807"
        # We want just: "W2741809807"
        full_id = raw.get("id", "")
        openalex_id = full_id.split("/")[-1]  # Get last part after "/"
        if not openalex_id:
            return None

        # --- Step 3: Parse authors ---
        # OpenAlex structure:
        # "authorships": [
        #   {
        #     "author": {"display_name": "John Smith", "orcid": "..."},
        #     "institutions": [{"display_name": "Harvard", "country_code": "US"}]
        #   }
        # ]
        authors = []
        for authorship in raw.get("authorships", []):
            author_data = authorship.get("author", {})
            institutions = authorship.get("institutions", [])

            # Get first institution if available
            first_inst = institutions[0] if institutions else {}

            authors.append(Author(
                name=author_data.get("display_name", "Unknown"),
                orcid=author_data.get("orcid"),
                institution=first_inst.get("display_name"),
                country=first_inst.get("country_code"),
            ))

        # --- Step 4: Parse concepts ---
        # OpenAlex tags papers with concepts and confidence scores
        # We only keep concepts with score > 0.3 (reasonably confident)
        concepts = []
        for c in raw.get("concepts", []):
            score = c.get("score", 0)
            if score > 0.3:  # Filter low-confidence concepts
                concept_id = c.get("id", "").split("/")[-1]  # "C123" from URL
                concepts.append(Concept(
                    id=concept_id,
                    name=c.get("display_name", ""),
                    score=score,
                ))

        # --- Step 5: Extract publication info ---
        # Primary location contains journal/source info
        primary_location = raw.get("primary_location") or {}
        source = primary_location.get("source") or {}

        # Biblio contains volume, issue, pages
        biblio = raw.get("biblio") or {}

        # --- Step 6: Extract external IDs ---
        # DOI is directly available
        doi = raw.get("doi")

        # PMID is nested in "ids" dict
        ids = raw.get("ids") or {}
        pmid = ids.get("pmid")

        # --- Step 7: Extract topics, keywords, MeSH terms ---
        topics = [
            t.get("display_name")
            for t in raw.get("topics", [])
            if t.get("display_name")
        ]

        keywords = [
            k.get("keyword")
            for k in raw.get("keywords", [])
            if k.get("keyword")
        ]

        mesh_terms = [
            m.get("descriptor_name")
            for m in raw.get("mesh", [])
            if m.get("descriptor_name")
        ]

        # --- Step 8: Open access info ---
        open_access = raw.get("open_access") or {}

        # --- Step 9: Build and return Paper object ---
        return Paper(
            openalex_id=openalex_id,
            title=raw.get("title") or "Untitled",
            abstract=abstract,
            doi=doi,
            pmid=pmid,
            authors=authors,
            publication_date=self._parse_date(raw.get("publication_date")),
            journal=source.get("display_name"),
            publisher=source.get("publisher"),
            volume=biblio.get("volume"),
            issue=biblio.get("issue"),
            concepts=concepts,
            topics=topics,
            keywords=keywords,
            mesh_terms=mesh_terms,
            is_open_access=open_access.get("is_oa", False),
            open_access_url=open_access.get("oa_url"),
            landing_page_url=primary_location.get("landing_page_url"),
            cited_by_count=raw.get("cited_by_count", 0),
            collected_at=datetime.utcnow(),
        )


    # === Part 5: Main Search Method ===

    async def search_papers(
        self,
        config: CrawlerConfig,
    ) -> AsyncGenerator[list[Paper], None]:
        """
        Search for papers and yield them in batches.

        CURSOR PAGINATION EXPLAINED:
        ────────────────────────────
        Unlike offset pagination (page 1, page 2...), cursor pagination uses
        a "bookmark" to track position. This is better because:

        1. Offset problem: If new papers are added while you're paginating,
           you might get duplicates or miss papers.

        2. Cursor solution: The cursor is a snapshot of your position.
           New papers don't affect your traversal.

        Flow:
            cursor="*" (start) → API returns next_cursor="abc123"
            cursor="abc123"   → API returns next_cursor="def456"
            cursor="def456"   → API returns next_cursor=None (done!)

        WHY ASYNC GENERATOR?
        ────────────────────
        Instead of loading all 1,000 papers into memory at once, we "yield"
        batches of ~200 papers. The caller processes each batch before we
        fetch the next. Memory efficient!

        Args:
            config: Crawler configuration (concepts, dates, max_results)

        Yields:
            Batches of Paper objects (typically 200 papers per batch)
        """
        # Safety check: ensure client is initialized
        if not self._client:
            raise RuntimeError(
                "Client not initialized. Use 'async with OpenAlexClient() as client:'"
            )

        # Build the filter string from config
        filter_string = self._build_filter_string(config)

        # Initialize pagination
        cursor = "*"              # "*" means "start from beginning"
        total_fetched = 0         # Raw papers from API
        total_parsed = 0          # Successfully parsed papers

        logger.info(
            "search_started",
            filter=filter_string,
            max_results=config.max_results,
        )

        # --- Main pagination loop ---
        while cursor and total_fetched < config.max_results:

            # Calculate how many to fetch this batch
            remaining = config.max_results - total_fetched
            per_page = min(config.per_page, remaining)  # Don't fetch more than needed

            # Build request parameters
            params = {
                "filter": filter_string,
                "per-page": per_page,
                "cursor": cursor,
            }

            # Add email for polite pool (10x faster rate limit)
            if self.email:
                params["mailto"] = self.email

            try:
                # --- Make API request ---
                response = await self._client.get(
                    f"{self.BASE_URL}/works",
                    params=params,
                )
                response.raise_for_status()  # Raise exception for 4xx/5xx
                data = response.json()

                # --- Extract results ---
                raw_papers = data.get("results", [])
                if not raw_papers:
                    # No more results, exit loop
                    break

                # --- Parse papers ---
                papers = []
                for raw in raw_papers:
                    paper = self._parse_paper(raw)
                    if paper:  # None means paper was skipped (no abstract)
                        papers.append(paper)

                # --- Yield this batch ---
                if papers:
                    yield papers

                # --- Update counters ---
                total_fetched += len(raw_papers)
                total_parsed += len(papers)

                # --- Get next cursor ---
                # If None, we've reached the end
                cursor = data.get("meta", {}).get("next_cursor")

                logger.info(
                    "batch_completed",
                    batch_raw=len(raw_papers),
                    batch_parsed=len(papers),
                    total_fetched=total_fetched,
                    total_parsed=total_parsed,
                    has_next=cursor is not None,
                )

                # --- Rate limiting ---
                # Polite pool: max 10 requests/second
                # We sleep 1/10 = 0.1 seconds between requests
                await asyncio.sleep(1 / config.requests_per_second)

            except httpx.HTTPStatusError as e:
                if e.response.status_code == 429:
                    # Rate limited! Back off and retry
                    logger.warning("rate_limited", retry_after_seconds=60)
                    await asyncio.sleep(60)
                    continue  # Retry same request
                raise  # Re-raise other HTTP errors

        # --- Done! ---
        logger.info(
            "search_completed",
            total_fetched=total_fetched,
            total_parsed=total_parsed,
            skipped=total_fetched - total_parsed,
        )


# === Example Usage ===

async def main():
    """
    Example: Fetch 10 oncology papers to test the client.

    Run with: python openalex_client.py
    """
    # Create config for prototype (1,000 papers, but we'll test with 10)
    config = CrawlerConfig(
        concept_ids=["C126322002", "C502942594"],  # Oncology, Cancer
        from_date=date(2024, 1, 1),
        max_results=10,  # Small number for testing
        per_page=10,
    )

    print("Starting OpenAlex paper search...")
    print(f"Concepts: {config.concept_ids}")
    print(f"From date: {config.from_date}")
    print(f"Max results: {config.max_results}")
    print("-" * 50)

    paper_count = 0

    async with OpenAlexClient(email="test@example.com") as client:
        async for batch in client.search_papers(config):
            for paper in batch:
                paper_count += 1
                print(f"\n[{paper_count}] {paper.title[:70]}...")
                print(f"    ID: {paper.openalex_id}")
                print(f"    Authors: {', '.join(a.name for a in paper.authors[:3])}")
                print(f"    Journal: {paper.journal}")
                print(f"    Citations: {paper.cited_by_count}")

    print("-" * 50)
    print(f"Total papers fetched: {paper_count}")


if __name__ == "__main__":
    asyncio.run(main())
