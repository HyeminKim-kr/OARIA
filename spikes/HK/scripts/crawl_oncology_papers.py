#!/usr/bin/env python3
"""
OARIA Oncology Paper Crawler

Collects full-text oncology papers from Open Access sources with priority ordering:
1. PMC/Europe PMC (70%) - Core peer-reviewed oncology
2. medRxiv (15%) - Clinical oncology preprints
3. bioRxiv (10%) - Cancer biology research
4. arXiv (5%) - Computational oncology

Features:
- Priority-based source collection
- Full-text extraction (mandatory)
- Progress tracking with resume capability
- Rate limiting for API compliance

Usage:
    python scripts/crawl_oncology_papers.py --target 1000
    python scripts/crawl_oncology_papers.py --target 1000 --resume

Author: HK
Created: 2025-12-30
"""

import argparse
import asyncio
import json
import logging
import re
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

import httpx
import psycopg2
import requests

# PDF extraction
try:
    import pdfplumber
    PDF_SUPPORT = True
except ImportError:
    PDF_SUPPORT = False
    print("WARNING: pdfplumber not installed. Run: pip install pdfplumber")

# Text preprocessing
try:
    sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
    from text_preprocessor import preprocess_full_text
    PREPROCESSOR_AVAILABLE = True
except ImportError:
    PREPROCESSOR_AVAILABLE = False
    def preprocess_full_text(text):
        return text

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)


# =============================================================================
# CONFIGURATION
# =============================================================================

@dataclass
class CrawlConfig:
    """Crawler configuration."""
    target_papers: int = 1000
    keyword: str = "oncology"

    # Distribution by source (must sum to 1.0)
    # Prioritize PMC for faster extraction (XML-based, not PDF)
    source_distribution: dict = field(default_factory=lambda: {
        "pmc": 0.88,      # 88% - PMC/Europe PMC (fastest, XML-based)
        "medrxiv": 0.10,  # 10% - medRxiv
        "biorxiv": 0.00,  # 0%  - bioRxiv (extraction issues)
        "arxiv": 0.02,    # 2%  - arXiv (at least 20 papers)
    })

    # API settings
    openalex_email: str = "oaria@research.com"
    rate_limit_delay: float = 0.1  # 10 requests/sec for OpenAlex
    pdf_download_delay: float = 0.2  # Reduced for parallel processing

    # Parallel processing
    parallel_workers: int = 8  # Number of concurrent extraction threads

    # Database
    db_host: str = "localhost"
    db_port: int = 5432
    db_user: str = "oaria"
    db_password: str = "oaria123"
    db_name: str = "oaria"

    # Progress file for resume
    progress_file: str = "crawl_progress.json"


@dataclass
class CrawlProgress:
    """Track crawling progress for resume capability."""
    target: int = 1000
    collected: dict = field(default_factory=lambda: {
        "pmc": 0, "medrxiv": 0, "biorxiv": 0, "arxiv": 0
    })
    failed: dict = field(default_factory=lambda: {
        "pmc": 0, "medrxiv": 0, "biorxiv": 0, "arxiv": 0
    })
    cursors: dict = field(default_factory=lambda: {
        "pmc": "*", "medrxiv": "*", "biorxiv": "*", "arxiv": "*"
    })
    started_at: str = ""
    last_updated: str = ""

    @property
    def total_collected(self) -> int:
        return sum(self.collected.values())

    @property
    def total_failed(self) -> int:
        return sum(self.failed.values())

    def save(self, filepath: str):
        self.last_updated = datetime.now().isoformat()
        with open(filepath, 'w') as f:
            json.dump({
                "target": self.target,
                "collected": self.collected,
                "failed": self.failed,
                "cursors": self.cursors,
                "started_at": self.started_at,
                "last_updated": self.last_updated,
            }, f, indent=2)

    @classmethod
    def load(cls, filepath: str) -> "CrawlProgress":
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
                return cls(**data)
        except FileNotFoundError:
            return cls(started_at=datetime.now().isoformat())


# =============================================================================
# SOURCE FILTERS FOR OPENALEX
# =============================================================================

SOURCE_FILTERS = {
    "pmc": {
        "name": "PMC/Europe PMC",
        "url_patterns": ["ncbi.nlm.nih.gov/pmc", "europepmc.org"],
        "openalex_filter": "open_access.oa_url:*ncbi.nlm.nih.gov*,open_access.oa_url:*europepmc*",
    },
    "medrxiv": {
        "name": "medRxiv",
        "url_patterns": ["medrxiv.org"],
        "openalex_filter": "open_access.oa_url:*medrxiv.org*",
    },
    "biorxiv": {
        "name": "bioRxiv",
        "url_patterns": ["biorxiv.org"],
        "openalex_filter": "open_access.oa_url:*biorxiv.org*",
    },
    "arxiv": {
        "name": "arXiv",
        "url_patterns": ["arxiv.org"],
        "openalex_filter": "open_access.oa_url:*arxiv.org*",
    },
}


# =============================================================================
# DATABASE
# =============================================================================

def get_db_connection(config: CrawlConfig):
    """Get database connection."""
    return psycopg2.connect(
        host=config.db_host,
        port=config.db_port,
        user=config.db_user,
        password=config.db_password,
        database=config.db_name,
    )


def ensure_schema(config: CrawlConfig):
    """Ensure database schema exists."""
    conn = get_db_connection(config)
    cur = conn.cursor()

    # Add columns if they don't exist
    cur.execute("ALTER TABLE papers ADD COLUMN IF NOT EXISTS full_text TEXT")
    cur.execute("ALTER TABLE papers ADD COLUMN IF NOT EXISTS source VARCHAR(20)")
    cur.execute("ALTER TABLE papers ADD COLUMN IF NOT EXISTS arxiv_id VARCHAR(50)")

    conn.commit()
    cur.close()
    conn.close()
    logger.info("Database schema verified")


def save_paper_to_db(config: CrawlConfig, paper: dict) -> bool:
    """Save paper with full-text to database."""
    conn = get_db_connection(config)
    cur = conn.cursor()

    try:
        cur.execute("""
            INSERT INTO papers (
                openalex_id, title, abstract, full_text, doi, pmid,
                publication_date, journal, publisher,
                is_open_access, open_access_url, cited_by_count, source
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (openalex_id) DO UPDATE SET
                full_text = EXCLUDED.full_text,
                source = EXCLUDED.source
        """, (
            paper["openalex_id"],
            paper["title"],
            paper.get("abstract"),
            paper["full_text"],  # REQUIRED
            paper.get("doi"),
            paper.get("pmid"),
            paper.get("publication_date"),
            paper.get("journal"),
            paper.get("publisher"),
            True,  # is_open_access
            paper.get("open_access_url"),
            paper.get("cited_by_count", 0),
            paper.get("source"),
        ))
        conn.commit()
        return True
    except Exception as e:
        logger.error(f"DB error: {e}")
        conn.rollback()
        return False
    finally:
        cur.close()
        conn.close()


def get_existing_ids(config: CrawlConfig) -> set:
    """Get set of already collected paper IDs."""
    conn = get_db_connection(config)
    cur = conn.cursor()
    cur.execute("SELECT openalex_id FROM papers WHERE full_text IS NOT NULL AND full_text != ''")
    ids = {row[0] for row in cur.fetchall()}
    cur.close()
    conn.close()
    return ids


# =============================================================================
# OPENALEX API
# =============================================================================

def parse_openalex_paper(raw: dict) -> Optional[dict]:
    """Parse OpenAlex response to paper dict."""
    # Reconstruct abstract from inverted index
    inverted = raw.get("abstract_inverted_index")
    abstract = None
    if inverted:
        words = []
        for word, positions in inverted.items():
            for pos in positions:
                words.append((pos, word))
        words.sort(key=lambda x: x[0])
        abstract = " ".join(word for _, word in words)

    openalex_id = raw.get("id", "").split("/")[-1]
    if not openalex_id:
        return None

    # Parse date
    pub_date = None
    if raw.get("publication_date"):
        try:
            from datetime import date
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
        "open_access_url": oa.get("oa_url"),
        "cited_by_count": raw.get("cited_by_count", 0),
    }


def fetch_papers_from_openalex(
    config: CrawlConfig,
    source: str,
    cursor: str = "*",
    limit: int = 50,
) -> tuple[list[dict], Optional[str]]:
    """
    Fetch papers from OpenAlex for a specific source.

    Returns:
        Tuple of (papers, next_cursor)
    """
    source_config = SOURCE_FILTERS[source]

    # Build filter
    base_filter = f"has_abstract:true,type:article,open_access.is_oa:true"

    # For specific sources, we filter by URL pattern
    if source == "pmc":
        # PMC is tricky - filter by repository
        url_filter = "locations.source.type:repository"
    else:
        url_filter = ""

    params = {
        "search": config.keyword,
        "filter": base_filter,
        "per-page": limit,
        "cursor": cursor,
        "mailto": config.openalex_email,
        "sort": "publication_date:asc",  # Oldest first (more likely to have full-text)
    }

    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.get("https://api.openalex.org/works", params=params)
            response.raise_for_status()
            data = response.json()

        papers = []
        for raw in data.get("results", []):
            paper = parse_openalex_paper(raw)
            if paper and paper.get("open_access_url"):
                # Check if URL matches source
                url = paper["open_access_url"].lower()
                if any(pattern in url for pattern in source_config["url_patterns"]):
                    paper["source"] = source
                    papers.append(paper)

        next_cursor = data.get("meta", {}).get("next_cursor")
        return papers, next_cursor

    except Exception as e:
        logger.error(f"OpenAlex API error for {source}: {e}")
        return [], cursor


# =============================================================================
# PDF EXTRACTION
# =============================================================================

def convert_to_pdf_url(url: str) -> str:
    """Convert article URL to PDF URL."""
    # PMC
    if 'ncbi.nlm.nih.gov/pmc/articles/' in url:
        pmc_id = url.split('/articles/')[-1].strip('/')
        if not pmc_id.startswith('PMC'):
            pmc_id = f'PMC{pmc_id}'
        return f'https://europepmc.org/backend/ptpmcrender.fcgi?accid={pmc_id}&blobtype=pdf'

    # Europe PMC
    if 'europepmc.org/article/' in url:
        parts = url.split('/')
        pmc_id = parts[-1] if parts[-1].startswith('PMC') else f'PMC{parts[-1]}'
        return f'https://europepmc.org/backend/ptpmcrender.fcgi?accid={pmc_id}&blobtype=pdf'

    # arXiv
    if 'arxiv.org' in url:
        arxiv_match = re.search(r'arxiv\.org/(abs|pdf)/(\d+\.\d+)', url)
        if arxiv_match:
            arxiv_id = arxiv_match.group(2)
            return f'https://arxiv.org/pdf/{arxiv_id}.pdf'
        arxiv_old_match = re.search(r'arxiv\.org/(abs|pdf)/([a-z-]+/\d+)', url)
        if arxiv_old_match:
            arxiv_id = arxiv_old_match.group(2)
            return f'https://arxiv.org/pdf/{arxiv_id}.pdf'

    # bioRxiv / medRxiv
    if 'biorxiv.org' in url or 'medrxiv.org' in url:
        base_url = url.split('?')[0]
        if not base_url.endswith('.pdf'):
            return f'{base_url}.full.pdf'
        return base_url

    return url


def extract_full_text(url: str) -> Optional[str]:
    """Download PDF and extract full text."""
    if not PDF_SUPPORT:
        return None

    try:
        pdf_url = convert_to_pdf_url(url)

        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Accept": "application/pdf,*/*",
        }

        response = requests.get(pdf_url, headers=headers, timeout=60, allow_redirects=True)
        response.raise_for_status()

        # Check if we got a PDF
        content_type = response.headers.get('content-type', '')
        if 'pdf' not in content_type.lower() and not response.content[:4] == b'%PDF':
            return None

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(response.content)
            tmp_path = tmp.name

        text_parts = []
        try:
            with pdfplumber.open(tmp_path) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text_parts.append(page_text)
        finally:
            Path(tmp_path).unlink(missing_ok=True)

        raw_text = "\n\n".join(text_parts)

        # Apply preprocessing if available
        if PREPROCESSOR_AVAILABLE:
            processed_text = preprocess_full_text(raw_text)
        else:
            processed_text = raw_text

        # Check minimum length
        if len(processed_text) < 500:
            return None

        return processed_text

    except Exception as e:
        logger.debug(f"PDF extraction failed: {e}")
        return None


# =============================================================================
# MAIN CRAWLER
# =============================================================================

def calculate_targets(config: CrawlConfig, progress: CrawlProgress) -> dict:
    """Calculate how many more papers needed per source."""
    targets = {}
    for source, ratio in config.source_distribution.items():
        target = int(config.target_papers * ratio)
        collected = progress.collected.get(source, 0)
        remaining = max(0, target - collected)
        targets[source] = remaining
    return targets


def extract_paper_worker(paper: dict) -> tuple[dict, Optional[str]]:
    """Worker function to extract full text from a paper."""
    try:
        full_text = extract_full_text(paper["open_access_url"])
        return paper, full_text
    except Exception as e:
        logger.debug(f"Extraction error: {e}")
        return paper, None


def crawl_source(
    config: CrawlConfig,
    progress: CrawlProgress,
    source: str,
    target_count: int,
    existing_ids: set,
) -> int:
    """Crawl papers from a single source with PARALLEL processing."""
    source_name = SOURCE_FILTERS[source]["name"]
    logger.info(f"\n{'='*60}")
    logger.info(f"Crawling {source_name} - Target: {target_count} papers (parallel: {config.parallel_workers} workers)")
    logger.info(f"{'='*60}")

    collected = 0
    cursor = progress.cursors.get(source, "*")
    consecutive_failures = 0
    max_consecutive_failures = 20  # Increased for parallel processing

    while collected < target_count:
        # Fetch batch from OpenAlex
        papers, next_cursor = fetch_papers_from_openalex(
            config, source, cursor, limit=50
        )

        if not papers:
            if not next_cursor:
                logger.warning(f"No more papers available from {source_name}")
                break
            cursor = next_cursor
            progress.cursors[source] = cursor
            progress.save(config.progress_file)
            continue

        # Filter out already collected papers
        papers_to_process = [
            p for p in papers
            if p["openalex_id"] not in existing_ids
        ]

        if not papers_to_process:
            # All papers in this batch already collected, move to next
            if next_cursor:
                cursor = next_cursor
                progress.cursors[source] = cursor
            continue

        logger.info(f"  Processing batch of {len(papers_to_process)} papers in parallel...")

        # PARALLEL EXTRACTION using ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=config.parallel_workers) as executor:
            futures = {
                executor.submit(extract_paper_worker, paper): paper
                for paper in papers_to_process
            }

            batch_success = 0
            batch_failed = 0

            for future in as_completed(futures):
                if collected >= target_count:
                    break

                paper, full_text = future.result()

                if full_text:
                    paper["full_text"] = full_text

                    # Save to database
                    if save_paper_to_db(config, paper):
                        collected += 1
                        batch_success += 1
                        progress.collected[source] = progress.collected.get(source, 0) + 1
                        existing_ids.add(paper["openalex_id"])
                        consecutive_failures = 0

                        logger.info(
                            f"  ✓ Collected #{progress.total_collected}: "
                            f"{paper['title'][:40]}... ({len(full_text):,} chars)"
                        )
                    else:
                        batch_failed += 1
                        progress.failed[source] = progress.failed.get(source, 0) + 1
                else:
                    batch_failed += 1
                    progress.failed[source] = progress.failed.get(source, 0) + 1
                    consecutive_failures += 1

        logger.info(f"  Batch result: {batch_success} success, {batch_failed} failed")

        # Check consecutive failures
        if consecutive_failures >= max_consecutive_failures:
            logger.warning(f"Too many consecutive failures for {source_name}, moving on")
            break

        # Update cursor and save progress
        if next_cursor:
            cursor = next_cursor
            progress.cursors[source] = cursor
        else:
            logger.info(f"Reached end of {source_name} results")
            break

        progress.save(config.progress_file)

        # Small delay between batches
        time.sleep(0.5)

    logger.info(f"\n{source_name}: Collected {collected}/{target_count} papers")
    return collected


def run_crawler(config: CrawlConfig, resume: bool = False):
    """Main crawler entry point."""
    import sys
    print("\n" + "="*60)
    print("  OARIA Oncology Paper Crawler")
    print("  Full-Text Only | Priority-Based Collection")
    print("="*60 + "\n")
    sys.stdout.flush()

    # Check PDF support
    if not PDF_SUPPORT:
        print("ERROR: pdfplumber is required. Install with: pip install pdfplumber")
        return

    print("Checking database schema...")
    sys.stdout.flush()
    # Ensure database schema
    ensure_schema(config)
    print("✓ Database schema OK")
    sys.stdout.flush()

    # Load or create progress
    print("Loading progress...")
    sys.stdout.flush()
    if resume and Path(config.progress_file).exists():
        progress = CrawlProgress.load(config.progress_file)
        print(f"Resuming from previous run: {progress.total_collected} papers collected")
    else:
        progress = CrawlProgress(
            target=config.target_papers,
            started_at=datetime.now().isoformat()
        )

    # Get existing paper IDs
    print("Checking existing papers in database...")
    sys.stdout.flush()
    existing_ids = get_existing_ids(config)
    print(f"Found {len(existing_ids)} existing papers with full-text")
    sys.stdout.flush()

    # Calculate targets per source
    targets = calculate_targets(config, progress)

    print("\nCollection Plan:")
    print("-" * 40)
    for source, target in targets.items():
        source_name = SOURCE_FILTERS[source]["name"]
        collected = progress.collected.get(source, 0)
        print(f"  {source_name:20} : {collected:4} / {int(config.target_papers * config.source_distribution[source]):4} (need {target})")
    print("-" * 40)
    print(f"  {'TOTAL':20} : {progress.total_collected:4} / {config.target_papers:4}")
    print()
    sys.stdout.flush()

    # Crawl each source in priority order
    source_order = ["pmc", "medrxiv", "biorxiv", "arxiv"]

    for source in source_order:
        target = targets.get(source, 0)
        if target > 0:
            crawl_source(config, progress, source, target, existing_ids)
            progress.save(config.progress_file)

    # Final summary
    print("\n" + "="*60)
    print("  CRAWL COMPLETE")
    print("="*60)
    print(f"\nTotal Papers Collected: {progress.total_collected}")
    print(f"Total Extraction Failures: {progress.total_failed}")
    print("\nBy Source:")
    for source in source_order:
        source_name = SOURCE_FILTERS[source]["name"]
        collected = progress.collected.get(source, 0)
        failed = progress.failed.get(source, 0)
        print(f"  {source_name:20} : {collected:4} collected, {failed:4} failed")

    # Cleanup progress file if complete
    if progress.total_collected >= config.target_papers:
        print(f"\n✓ Target of {config.target_papers} papers reached!")
        # Keep progress file for reference


def main():
    parser = argparse.ArgumentParser(
        description="OARIA Oncology Paper Crawler - Full-Text Collection"
    )
    parser.add_argument(
        "--target", "-t",
        type=int,
        default=1000,
        help="Target number of papers to collect (default: 1000)"
    )
    parser.add_argument(
        "--keyword", "-k",
        type=str,
        default="oncology",
        help="Search keyword (default: oncology)"
    )
    parser.add_argument(
        "--resume", "-r",
        action="store_true",
        help="Resume from previous crawl progress"
    )
    parser.add_argument(
        "--pdf-delay",
        type=float,
        default=1.0,
        help="Delay between PDF downloads in seconds (default: 1.0)"
    )

    args = parser.parse_args()

    config = CrawlConfig(
        target_papers=args.target,
        keyword=args.keyword,
        pdf_download_delay=args.pdf_delay,
    )

    run_crawler(config, resume=args.resume)


if __name__ == "__main__":
    main()
