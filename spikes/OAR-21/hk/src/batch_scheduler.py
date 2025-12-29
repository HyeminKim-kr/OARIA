"""
Batch Crawler Scheduler (OAR-21 / OAR-102)

Automates paper collection with scheduled batch crawling.

Features:
- Initial collection: Last 5 years of oncology papers
- Daily incremental: New papers since last run
- Configurable batch size and schedule
- Progress logging with statistics

Run with:
    python batch_scheduler.py --mode initial --years 5
    python batch_scheduler.py --mode incremental
    python batch_scheduler.py --mode scheduled
"""

import asyncio
import sys
import time
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Optional

import httpx
import asyncpg
import structlog

# Setup logging
structlog.configure(
    processors=[structlog.dev.ConsoleRenderer(colors=True)]
)
logger = structlog.get_logger()


# === DATA CLASSES ===

@dataclass
class CrawlStats:
    """Track crawl progress and statistics."""
    started_at: datetime = field(default_factory=datetime.now)
    ended_at: Optional[datetime] = None
    api_calls: int = 0
    papers_fetched: int = 0
    papers_parsed: int = 0
    papers_saved: int = 0
    duplicates_skipped: int = 0
    errors: int = 0
    rate_limits: int = 0

    def duration_seconds(self) -> float:
        end = self.ended_at or datetime.now()
        return (end - self.started_at).total_seconds()

    def to_dict(self) -> dict:
        return {
            "started_at": self.started_at.isoformat(),
            "ended_at": self.ended_at.isoformat() if self.ended_at else None,
            "duration_seconds": self.duration_seconds(),
            "api_calls": self.api_calls,
            "papers_fetched": self.papers_fetched,
            "papers_parsed": self.papers_parsed,
            "papers_saved": self.papers_saved,
            "duplicates_skipped": self.duplicates_skipped,
            "errors": self.errors,
            "rate_limits": self.rate_limits,
        }


@dataclass
class SchedulerConfig:
    """Scheduler configuration."""
    # Database
    db_host: str = "localhost"
    db_port: int = 5432
    db_user: str = "oaria"
    db_password: str = "oaria123"
    db_name: str = "oaria"

    # OpenAlex
    openalex_email: str = "oaria@example.com"
    concepts: list = field(default_factory=lambda: ["C126322002"])  # Oncology

    # Crawl settings
    batch_size: int = 200
    max_papers: int = 50000
    years_back: int = 5

    # Schedule (cron format)
    schedule_cron: str = "0 2 * * *"  # Daily at 2 AM


# === DATABASE ===

async def connect_db(config: SchedulerConfig) -> asyncpg.Connection:
    """Connect to PostgreSQL."""
    return await asyncpg.connect(
        host=config.db_host,
        port=config.db_port,
        user=config.db_user,
        password=config.db_password,
        database=config.db_name,
    )


async def get_existing_ids(conn: asyncpg.Connection) -> set:
    """Get existing paper IDs for deduplication."""
    rows = await conn.fetch("SELECT openalex_id FROM papers")
    return {row["openalex_id"] for row in rows}


async def get_last_crawl_date(conn: asyncpg.Connection) -> Optional[date]:
    """Get the date of the last successful crawl."""
    row = await conn.fetchrow("""
        SELECT MAX(collected_at)::date as last_date
        FROM papers
    """)
    return row["last_date"] if row else None


async def save_paper(conn: asyncpg.Connection, paper: dict) -> bool:
    """Save paper to database."""
    try:
        result = await conn.execute("""
            INSERT INTO papers (openalex_id, title, abstract, doi, pmid,
                              publication_date, journal, publisher,
                              is_open_access, open_access_url, cited_by_count)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
            ON CONFLICT (openalex_id) DO NOTHING
        """,
            paper["openalex_id"],
            paper["title"],
            paper["abstract"],
            paper.get("doi"),
            paper.get("pmid"),
            paper.get("publication_date"),
            paper.get("journal"),
            paper.get("publisher"),
            paper.get("is_open_access", False),
            paper.get("open_access_url"),
            paper.get("cited_by_count", 0),
        )
        return "INSERT" in result
    except Exception as e:
        logger.error("save_paper_error", error=str(e))
        return False


async def log_crawl(conn: asyncpg.Connection, stats: CrawlStats, status: str = "completed"):
    """Log crawl run to database."""
    await conn.execute("""
        INSERT INTO crawl_log (started_at, ended_at, papers_fetched, papers_saved, papers_skipped, status)
        VALUES ($1, $2, $3, $4, $5, $6)
    """,
        stats.started_at,
        stats.ended_at,
        stats.papers_fetched,
        stats.papers_saved,
        stats.duplicates_skipped,
        status,
    )


# === PAPER PARSING ===

def extract_abstract(raw: dict) -> Optional[str]:
    """Reconstruct abstract from inverted index."""
    inverted = raw.get("abstract_inverted_index")
    if not inverted:
        return None

    words = []
    for word, positions in inverted.items():
        for pos in positions:
            words.append((pos, word))

    words.sort(key=lambda x: x[0])
    return " ".join(word for _, word in words)


def parse_paper(raw: dict) -> Optional[dict]:
    """Parse OpenAlex response to paper dict."""
    abstract = extract_abstract(raw)
    if not abstract or len(abstract) < 50:
        return None

    openalex_id = raw.get("id", "").split("/")[-1]
    if not openalex_id:
        return None

    # Parse date
    pub_date = None
    if raw.get("publication_date"):
        try:
            pub_date = date.fromisoformat(raw["publication_date"])
        except:
            pass

    # Extract location info
    location = raw.get("primary_location") or {}
    source = location.get("source") or {}
    ids = raw.get("ids") or {}
    oa = raw.get("open_access") or {}

    return {
        "openalex_id": openalex_id,
        "title": raw.get("title") or "Untitled",
        "abstract": abstract,
        "doi": raw.get("doi"),
        "pmid": ids.get("pmid"),
        "publication_date": pub_date,
        "journal": source.get("display_name"),
        "publisher": source.get("publisher"),
        "is_open_access": oa.get("is_oa", False),
        "open_access_url": oa.get("oa_url"),
        "cited_by_count": raw.get("cited_by_count", 0),
    }


# === API FETCH WITH RETRY ===

async def fetch_with_retry(
    client: httpx.AsyncClient,
    url: str,
    params: dict,
    stats: CrawlStats,
    max_retries: int = 5
) -> Optional[dict]:
    """Fetch URL with exponential backoff retry."""
    for attempt in range(max_retries):
        try:
            stats.api_calls += 1
            response = await client.get(url, params=params)
            response.raise_for_status()
            return response.json()

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                stats.rate_limits += 1
                delay = 1 * (2 ** attempt)
                logger.warning("rate_limited", attempt=attempt, delay=delay)
                await asyncio.sleep(delay)
            else:
                stats.errors += 1
                raise

        except httpx.TimeoutException:
            logger.warning("timeout", attempt=attempt)
            await asyncio.sleep(5)

    stats.errors += 1
    return None


# === BATCH CRAWLER ===

class BatchScheduler:
    """Batch crawler scheduler for automated paper collection."""

    def __init__(self, config: SchedulerConfig = None):
        self.config = config or SchedulerConfig()
        self.stats = CrawlStats()

    def _build_filter(self, from_date: Optional[date] = None) -> str:
        """Build OpenAlex filter string."""
        filters = [
            f"concepts.id:{self.config.concepts[0]}",
            "has_abstract:true",
            "type:article",
        ]

        if from_date:
            filters.append(f"from_publication_date:{from_date.isoformat()}")

        return ",".join(filters)

    def _print_progress(self, current: int, target: int, msg: str = ""):
        """Print progress bar."""
        pct = min(current / target * 100, 100)
        bar_len = 30
        filled = int(bar_len * current / target)
        bar = "█" * filled + "░" * (bar_len - filled)

        sys.stdout.write(f"\r  [{bar}] {current:,}/{target:,} ({pct:.1f}%) {msg}")
        sys.stdout.flush()

    def _print_stats(self):
        """Print current statistics."""
        s = self.stats
        print(f"\n\n  📊 Statistics:")
        print(f"     API Calls:    {s.api_calls:,}")
        print(f"     Fetched:      {s.papers_fetched:,}")
        print(f"     Parsed:       {s.papers_parsed:,}")
        print(f"     Saved:        {s.papers_saved:,}")
        print(f"     Duplicates:   {s.duplicates_skipped:,}")
        print(f"     Rate Limits:  {s.rate_limits:,}")
        print(f"     Duration:     {s.duration_seconds():.1f}s")

    async def run_initial_collection(self, years_back: int = None) -> CrawlStats:
        """
        Initial collection: Fetch papers from the last N years.

        Args:
            years_back: Number of years to look back (default from config)

        Returns:
            CrawlStats with collection results
        """
        years = years_back or self.config.years_back
        from_date = date.today() - timedelta(days=years * 365)

        print("\n" + "=" * 60)
        print(f"  🚀 INITIAL COLLECTION: Last {years} years")
        print(f"     From: {from_date}")
        print(f"     Target: {self.config.max_papers:,} papers")
        print("=" * 60)

        await self._crawl(
            filter_str=self._build_filter(from_date),
            max_papers=self.config.max_papers,
        )

        return self.stats

    async def run_incremental(self, since_date: date = None) -> CrawlStats:
        """
        Incremental collection: Fetch new papers since last run.

        Args:
            since_date: Start date (default: last crawl date or yesterday)

        Returns:
            CrawlStats with collection results
        """
        conn = await connect_db(self.config)

        if not since_date:
            since_date = await get_last_crawl_date(conn)
            if not since_date:
                since_date = date.today() - timedelta(days=1)

        await conn.close()

        print("\n" + "=" * 60)
        print(f"  📥 INCREMENTAL COLLECTION")
        print(f"     Since: {since_date}")
        print("=" * 60)

        await self._crawl(
            filter_str=self._build_filter(since_date),
            max_papers=10000,  # Daily limit
        )

        return self.stats

    async def _crawl(self, filter_str: str, max_papers: int):
        """Core crawl logic."""
        self.stats = CrawlStats()

        # Connect to database
        print("\n  📦 Connecting to database...")
        conn = await connect_db(self.config)
        print("  ✅ Connected")

        # Get existing IDs for deduplication
        print("  🔍 Loading existing papers...")
        existing_ids = await get_existing_ids(conn)
        print(f"  ✅ Found {len(existing_ids):,} existing papers")

        print(f"\n  🌐 Starting crawl (batch size: {self.config.batch_size})...")

        async with httpx.AsyncClient(timeout=30.0) as client:
            cursor = "*"
            batch_num = 0

            while self.stats.papers_saved < max_papers and cursor:
                batch_num += 1

                params = {
                    "filter": filter_str,
                    "per-page": self.config.batch_size,
                    "cursor": cursor,
                    "mailto": self.config.openalex_email,
                }

                # Fetch batch
                data = await fetch_with_retry(
                    client,
                    "https://api.openalex.org/works",
                    params,
                    self.stats,
                )

                if not data:
                    logger.error("fetch_failed", batch=batch_num)
                    break

                results = data.get("results", [])
                self.stats.papers_fetched += len(results)

                # Process papers
                for raw in results:
                    if self.stats.papers_saved >= max_papers:
                        break

                    paper = parse_paper(raw)
                    if not paper:
                        continue

                    self.stats.papers_parsed += 1

                    # Deduplication check
                    if paper["openalex_id"] in existing_ids:
                        self.stats.duplicates_skipped += 1
                        continue

                    # Save to database
                    if await save_paper(conn, paper):
                        self.stats.papers_saved += 1
                        existing_ids.add(paper["openalex_id"])

                # Progress
                self._print_progress(
                    self.stats.papers_saved,
                    max_papers,
                    f"Batch {batch_num}"
                )

                # Next cursor
                cursor = data.get("meta", {}).get("next_cursor")

                # Rate limiting
                await asyncio.sleep(0.1)

        # Complete
        self.stats.ended_at = datetime.now()

        # Log to database
        await log_crawl(conn, self.stats)
        await conn.close()

        self._print_stats()
        print("\n  ✅ Crawl complete!\n")


# === ENTRY POINT ===

async def main():
    import argparse

    parser = argparse.ArgumentParser(description="OARIA Batch Crawler Scheduler")
    parser.add_argument(
        "--mode",
        choices=["initial", "incremental", "test"],
        default="test",
        help="Crawl mode"
    )
    parser.add_argument("--years", type=int, default=5, help="Years back for initial")
    parser.add_argument("--papers", type=int, default=100, help="Max papers (for test)")

    args = parser.parse_args()

    config = SchedulerConfig()

    if args.mode == "test":
        config.max_papers = args.papers
        scheduler = BatchScheduler(config)
        await scheduler.run_initial_collection(years_back=1)

    elif args.mode == "initial":
        scheduler = BatchScheduler(config)
        await scheduler.run_initial_collection(years_back=args.years)

    elif args.mode == "incremental":
        scheduler = BatchScheduler(config)
        await scheduler.run_incremental()


if __name__ == "__main__":
    asyncio.run(main())
