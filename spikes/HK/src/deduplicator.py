"""
Paper Deduplication Logic for OARIA Paper Crawler (F-02)

Author: Hyemin Kim (AI Lead)
Task: OAR-100

Why OpenAlex ID instead of PMID? (ADR-001)
- OpenAlex ID is always present (PMID can be null)
- Already used as PRIMARY KEY in our schema (OAR-73)
- Covers ALL papers, not just PubMed-indexed ones
"""

# === IMPORTS ===

# Standard library
import asyncio
from typing import Optional

# Third-party
import structlog

# Our models (from OAR-20 schema work)
# Note: In production, this would be from src.models
# For spike, we import from the relative path
import sys
from pathlib import Path

# Add OAR-18/hk/src to path for Paper model
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "OAR-18" / "hk" / "src"))
from models import Paper

# Setup logger
logger = structlog.get_logger()


# === DEDUPLICATOR CLASS ===

class Deduplicator:
    """
    Handles paper deduplication before database insertion.

    WHY DEDUPLICATION MATTERS:
    ─────────────────────────
    When crawling papers over time, duplicates can occur:
    1. Re-crawl scenarios - Running crawler again fetches same papers
    2. Overlapping queries - Different searches return same papers
    3. Data updates - Same paper with updated metadata (citations)

    THREE-LAYER DEFENSE:
    ───────────────────
    Layer 1: Pre-filter in memory (efficiency)
    Layer 2: ON CONFLICT clause (race conditions)
    Layer 3: PRIMARY KEY constraint (safety net)

    Usage:
        # With database connection
        deduplicator = Deduplicator(db_connection)
        existing_ids = await deduplicator.get_existing_ids()
        new_papers, dup_count = deduplicator.filter_new_papers(papers, existing_ids)

        # Standalone (for testing without DB)
        deduplicator = Deduplicator()
        new_papers, dup_count = deduplicator.filter_new_papers(papers, existing_ids)
    """

    def __init__(self, db_connection=None):
        """
        Initialize deduplicator.

        Args:
            db_connection: Database connection (asyncpg, databases, etc.)
                          Optional for unit testing.
        """
        self.db = db_connection

    # === Part 1: Get Existing IDs ===

    async def get_existing_ids(self) -> set[str]:
        """
        Fetch all OpenAlex IDs from database.

        WHY SET INSTEAD OF LIST?
        ────────────────────────
        Set lookup is O(1), list lookup is O(n).
        For 50,000 papers:
        - List: 50,000 comparisons per check = SLOW
        - Set: 1 hash lookup per check = FAST

        Returns:
            Set of existing openalex_ids for O(1) lookup

        Raises:
            RuntimeError: If database connection not provided

        Performance:
            - Single query regardless of table size
            - 50,000 IDs ≈ 1 MB memory
            - Query time: < 100ms for 50K rows
        """
        if not self.db:
            raise RuntimeError(
                "Database connection required. "
                "Pass db_connection to __init__ or use filter_new_papers() directly."
            )

        logger.info("fetching_existing_ids")

        # Single query to get all IDs
        # This is more efficient than checking each paper individually
        query = "SELECT openalex_id FROM papers"

        try:
            rows = await self.db.fetch_all(query)
            existing_ids = {row["openalex_id"] for row in rows}

            logger.info(
                "existing_ids_fetched",
                count=len(existing_ids),
            )

            return existing_ids

        except Exception as e:
            logger.error("fetch_ids_failed", error=str(e))
            raise

    # === Part 2: Filter New Papers ===

    def filter_new_papers(
        self,
        papers: list[Paper],
        existing_ids: set[str],
    ) -> tuple[list[Paper], int]:
        """
        Filter out papers that already exist in database.

        HOW IT WORKS:
        ─────────────
        1. For each paper, check if openalex_id is in existing_ids set
        2. If yes → skip (duplicate)
        3. If no → keep (new paper)

        Args:
            papers: Papers fetched from OpenAlex API
            existing_ids: Set of openalex_ids already in database

        Returns:
            Tuple of (new_papers, duplicate_count)

        Performance:
            - O(n) where n = len(papers)
            - Each lookup is O(1) with set
            - 10,000 papers checked in ~5ms
        """
        new_papers = []
        duplicate_count = 0

        for paper in papers:
            if paper.openalex_id in existing_ids:
                duplicate_count += 1
            else:
                new_papers.append(paper)

        logger.info(
            "papers_filtered",
            total=len(papers),
            new=len(new_papers),
            duplicates=duplicate_count,
        )

        return new_papers, duplicate_count

    # === Part 3: Convenience Method ===

    async def filter_duplicates(self, papers: list[Paper]) -> list[Paper]:
        """
        Convenience method: fetch existing IDs and filter in one call.

        Use this for simple cases. For batch processing with multiple
        API calls, use get_existing_ids() once and filter_new_papers()
        for each batch (more efficient).

        Args:
            papers: Papers to check for duplicates

        Returns:
            List of new papers only
        """
        existing_ids = await self.get_existing_ids()
        new_papers, _ = self.filter_new_papers(papers, existing_ids)
        return new_papers

    # === Part 4: DOI-Based Secondary Dedup ===

    def filter_by_doi(
        self,
        papers: list[Paper],
        existing_dois: set[str],
    ) -> tuple[list[Paper], int]:
        """
        Secondary deduplication by DOI.

        WHY DOI AS SECONDARY KEY?
        ─────────────────────────
        Edge case: Same paper might have different OpenAlex IDs
        (rare, but possible during OpenAlex data updates).
        DOI is a persistent identifier that doesn't change.

        Args:
            papers: Papers to check (already filtered by openalex_id)
            existing_dois: Set of DOIs already in database

        Returns:
            Tuple of (unique_papers, doi_duplicate_count)
        """
        unique_papers = []
        doi_duplicate_count = 0

        for paper in papers:
            # Skip DOI check if paper has no DOI
            if paper.doi and paper.doi in existing_dois:
                doi_duplicate_count += 1
                logger.debug(
                    "doi_duplicate_found",
                    openalex_id=paper.openalex_id,
                    doi=paper.doi,
                )
            else:
                unique_papers.append(paper)

        if doi_duplicate_count > 0:
            logger.info(
                "doi_duplicates_filtered",
                count=doi_duplicate_count,
            )

        return unique_papers, doi_duplicate_count


# === Part 5: Batch Insert Helper ===

async def batch_insert_papers(
    db,
    papers: list[Paper],
    on_conflict: str = "DO NOTHING",
    batch_size: int = 100,
) -> tuple[int, int]:
    """
    Insert papers in batches with conflict handling.

    ON CONFLICT OPTIONS:
    ───────────────────
    - "DO NOTHING": Skip duplicates silently (simple dedup)
    - "DO UPDATE SET ...": Update specific fields (upsert)

    Args:
        db: Database connection
        papers: Papers to insert
        on_conflict: Conflict resolution strategy
        batch_size: Number of papers per batch

    Returns:
        Tuple of (inserted_count, skipped_count)
    """
    if not papers:
        return 0, 0

    inserted = 0
    skipped = 0

    # Process in batches to avoid memory issues
    for i in range(0, len(papers), batch_size):
        batch = papers[i:i + batch_size]

        for paper in batch:
            query = f"""
                INSERT INTO papers (
                    openalex_id, title, abstract, doi, pmid,
                    publication_date, journal, publisher,
                    is_open_access, open_access_url, cited_by_count,
                    collected_at
                )
                VALUES (
                    $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12
                )
                ON CONFLICT (openalex_id) {on_conflict}
            """

            try:
                await db.execute(
                    query,
                    paper.openalex_id,
                    paper.title,
                    paper.abstract,
                    paper.doi,
                    paper.pmid,
                    paper.publication_date,
                    paper.journal,
                    paper.publisher,
                    paper.is_open_access,
                    paper.open_access_url,
                    paper.cited_by_count,
                    paper.collected_at,
                )
                inserted += 1
            except Exception as e:
                # Log but don't fail on individual errors
                logger.warning(
                    "insert_failed",
                    paper=paper.openalex_id,
                    error=str(e),
                )
                skipped += 1

        logger.debug(
            "batch_inserted",
            batch_num=i // batch_size + 1,
            batch_size=len(batch),
        )

    logger.info(
        "batch_insert_completed",
        total=len(papers),
        inserted=inserted,
        skipped=skipped,
    )

    return inserted, skipped


# === Example Usage ===

async def main():
    """
    Example: Test deduplication logic without database.

    Run with: python deduplicator.py
    """
    from datetime import date, datetime

    print("Testing Deduplication Logic")
    print("-" * 50)

    # Create sample papers
    papers = [
        Paper(
            openalex_id="W001",
            title="Paper 1",
            abstract="This is the abstract for paper 1. " * 5,
            publication_date=date(2024, 1, 1),
            collected_at=datetime.utcnow(),
        ),
        Paper(
            openalex_id="W002",
            title="Paper 2",
            abstract="This is the abstract for paper 2. " * 5,
            publication_date=date(2024, 1, 2),
            collected_at=datetime.utcnow(),
        ),
        Paper(
            openalex_id="W003",
            title="Paper 3",
            abstract="This is the abstract for paper 3. " * 5,
            publication_date=date(2024, 1, 3),
            collected_at=datetime.utcnow(),
        ),
    ]

    # Simulate existing papers in database
    existing_ids = {"W001", "W003"}  # W002 is new

    print(f"Total papers from API: {len(papers)}")
    print(f"Existing IDs in DB: {existing_ids}")
    print("-" * 50)

    # Test deduplication
    deduplicator = Deduplicator()  # No DB for testing
    new_papers, dup_count = deduplicator.filter_new_papers(papers, existing_ids)

    print(f"New papers: {len(new_papers)}")
    print(f"Duplicates skipped: {dup_count}")
    print("-" * 50)

    for paper in new_papers:
        print(f"  NEW: {paper.openalex_id} - {paper.title}")

    print("-" * 50)
    print("Deduplication test completed!")


if __name__ == "__main__":
    asyncio.run(main())
