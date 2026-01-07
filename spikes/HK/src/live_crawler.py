"""
Live Paper Crawler - Watch OARIA in Action!

This script demonstrates all components working together:
- OAR-94: OpenAlex API client
- OAR-100: Deduplication
- OAR-101: Retry handling
- ADR-001b: Open Access Full-Text Collection

Only collects Open Access papers from trusted sources:
- PubMed Central (PMC) via Europe PMC
- arXiv
- bioRxiv
- medRxiv

Run with: python live_crawler.py --papers 20
"""

import asyncio
import sys
import time
import tempfile
import requests
from datetime import date, datetime
from pathlib import Path
from typing import Optional

import httpx
import asyncpg
import structlog

# Try to import pdfplumber for full-text extraction
try:
    import pdfplumber
    PDF_SUPPORT = True
except ImportError:
    PDF_SUPPORT = False

# Import text preprocessor
try:
    from text_preprocessor import preprocess_full_text
except ImportError:
    # Fallback: no preprocessing
    def preprocess_full_text(text):
        return text

# Trusted Open Access sources (ADR-001b)
TRUSTED_SOURCES = [
    "ncbi.nlm.nih.gov/pmc",
    "europepmc.org",
    "arxiv.org",
    "biorxiv.org",
    "medrxiv.org",
]

# Setup colored logging
structlog.configure(
    processors=[
        structlog.dev.ConsoleRenderer(colors=True)
    ]
)
logger = structlog.get_logger()


# === OPEN ACCESS HELPERS (ADR-001b) ===

def is_trusted_source(url: str) -> bool:
    """Check if URL is from a trusted Open Access source."""
    if not url:
        return False
    return any(source in url.lower() for source in TRUSTED_SOURCES)


def convert_to_pdf_url(url: str) -> str:
    """Convert article URL to direct PDF URL (ADR-001b)."""
    import re

    # PMC → Europe PMC API (returns actual PDF)
    if 'ncbi.nlm.nih.gov/pmc/articles/' in url:
        pmc_id = url.split('/articles/')[-1].strip('/').split('/')[0]
        if not pmc_id.startswith('PMC'):
            pmc_id = f'PMC{pmc_id}'
        return f'https://europepmc.org/backend/ptpmcrender.fcgi?accid={pmc_id}&blobtype=pdf'

    # Europe PMC article page
    if 'europepmc.org/article/' in url:
        parts = url.split('/')
        pmc_id = parts[-1] if parts[-1].startswith('PMC') else f'PMC{parts[-1]}'
        return f'https://europepmc.org/backend/ptpmcrender.fcgi?accid={pmc_id}&blobtype=pdf'

    # arXiv: https://arxiv.org/abs/2301.12345 → https://arxiv.org/pdf/2301.12345.pdf
    if 'arxiv.org/abs/' in url:
        arxiv_id = url.split('/abs/')[-1].strip('/')
        return f'https://arxiv.org/pdf/{arxiv_id}.pdf'
    if 'arxiv.org/pdf/' in url:
        return url if url.endswith('.pdf') else url + '.pdf'

    # bioRxiv: https://www.biorxiv.org/content/10.1101/2023.01.01.123456v1 → .full.pdf
    if 'biorxiv.org/content/' in url:
        base_url = url.rstrip('/')
        if not base_url.endswith('.pdf'):
            return base_url + '.full.pdf'
        return url

    # medRxiv: same pattern as bioRxiv
    if 'medrxiv.org/content/' in url:
        base_url = url.rstrip('/')
        if not base_url.endswith('.pdf'):
            return base_url + '.full.pdf'
        return url

    # Default: return as-is
    return url


# Browser-like headers to avoid 403 errors
PDF_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'application/pdf,*/*',
    'Accept-Language': 'en-US,en;q=0.9',
}


def extract_full_text(url: str) -> Optional[str]:
    """Download PDF, extract and preprocess full text."""
    if not PDF_SUPPORT:
        return None

    try:
        pdf_url = convert_to_pdf_url(url)
        response = requests.get(pdf_url, headers=PDF_HEADERS, timeout=60, allow_redirects=True)
        response.raise_for_status()

        # Verify we got a PDF
        content_type = response.headers.get('Content-Type', '')
        if 'pdf' not in content_type.lower() and len(response.content) < 1000:
            logger.warning("not_a_pdf", url=pdf_url, content_type=content_type)
            return None

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(response.content)
            tmp_path = tmp.name

        text_parts = []
        with pdfplumber.open(tmp_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)

        Path(tmp_path).unlink(missing_ok=True)

        if not text_parts:
            return None

        # Preprocess to clean garbled text, tables, headers
        raw_text = "\n\n".join(text_parts)
        clean_text = preprocess_full_text(raw_text)

        return clean_text if len(clean_text) > 100 else None

    except Exception as e:
        logger.warning("pdf_extraction_failed", url=url, error=str(e))
        return None


# === DISPLAY HELPERS ===

def clear_line():
    """Clear current line."""
    sys.stdout.write("\r" + " " * 80 + "\r")
    sys.stdout.flush()

def print_header():
    """Print fancy header."""
    print()
    print("╔" + "═" * 58 + "╗")
    print("║" + " " * 15 + "🔬 OARIA Paper Crawler" + " " * 21 + "║")
    print("║" + " " * 12 + "Oncology AI Research Intelligence" + " " * 11 + "║")
    print("╚" + "═" * 58 + "╝")
    print()

def print_section(title: str):
    """Print section header."""
    print(f"\n{'─' * 60}")
    print(f"  {title}")
    print(f"{'─' * 60}")

def print_progress(current: int, total: int, paper_title: str, status: str = "saving"):
    """Print progress bar with status."""
    pct = current / total * 100
    bar_len = 25
    filled = int(bar_len * current / total)
    bar = "█" * filled + "░" * (bar_len - filled)

    # Truncate title
    title = paper_title[:35] + "..." if len(paper_title) > 35 else paper_title

    # Status emoji
    emoji = "💾" if status == "saving" else "🔍" if status == "parsing" else "📡"

    clear_line()
    sys.stdout.write(f"  [{bar}] {current}/{total} ({pct:.0f}%) {emoji} {title}")
    sys.stdout.flush()

def print_stats_live(stats: dict):
    """Print live statistics."""
    print(f"\n\n  📊 Live Stats: API:{stats['API Calls']} | "
          f"Fetched:{stats['Papers Fetched']} | "
          f"Parsed:{stats['Papers Parsed']} | "
          f"Saved:{stats['Papers Saved']} | "
          f"Skipped:{stats['Duplicates Skipped']}")

def print_final_stats(stats: dict, duration: float):
    """Print final statistics box."""
    print("\n")
    print("╔" + "═" * 58 + "╗")
    print("║" + " " * 20 + "📊 FINAL STATISTICS" + " " * 19 + "║")
    print("╠" + "═" * 58 + "╣")
    print(f"║  🌐 API Calls:        {stats['API Calls']:<35}║")
    print(f"║  📥 Papers Fetched:   {stats['Papers Fetched']:<35}║")
    print(f"║  🔓 Open Access:      {stats['Open Access']:<35}║")
    print(f"║  📝 Trusted Source:   {stats['Trusted Source']:<35}║")
    print(f"║  💾 Papers Saved:     {stats['Papers Saved']:<35}║")
    print(f"║  📄 Full Text:        {stats['Full Text Extracted']:<35}║")
    print(f"║  🔄 Duplicates:       {stats['Duplicates Skipped']:<35}║")
    print(f"║  ⚠️  Rate Limits:      {stats['Rate Limits Hit']:<35}║")
    print(f"║  ⏱️  Duration:         {duration:.1f}s{' ' * 32}║")
    print("╚" + "═" * 58 + "╝")


# === DATABASE ===

async def connect_db() -> Optional[asyncpg.Connection]:
    """Connect to PostgreSQL."""
    try:
        conn = await asyncpg.connect(
            host="localhost",
            port=5432,
            user="oaria",
            password="oaria123",
            database="oaria",
        )
        return conn
    except Exception as e:
        print(f"  ❌ Database connection failed: {e}")
        return None


async def get_existing_ids(conn: asyncpg.Connection) -> set:
    """Get existing paper IDs for deduplication (OAR-100)."""
    rows = await conn.fetch("SELECT openalex_id FROM papers")
    return {row["openalex_id"] for row in rows}


async def save_paper(conn: asyncpg.Connection, paper: dict) -> bool:
    """Save paper to database with full text."""
    try:
        await conn.execute("""
            INSERT INTO papers (openalex_id, title, abstract, doi, pmid,
                              publication_date, journal, publisher,
                              is_open_access, open_access_url, cited_by_count, full_text)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
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
            paper.get("full_text"),
        )
        return True
    except Exception as e:
        logger.error("save_paper_error", error=str(e))
        return False


# === ABSTRACT RECONSTRUCTION (OAR-99) ===

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


# === PAPER PARSER (OAR-99) ===

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

    # Extract IDs
    ids = raw.get("ids") or {}

    # Open access
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


# === RETRY HANDLER (OAR-101) ===

async def fetch_with_retry(client: httpx.AsyncClient, url: str, params: dict, stats: dict, max_retries: int = 5) -> dict:
    """Fetch URL with exponential backoff retry."""
    for attempt in range(max_retries):
        try:
            response = await client.get(url, params=params)
            response.raise_for_status()
            return response.json()

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                stats["Rate Limits Hit"] += 1
                delay = 1 * (2 ** attempt)  # Exponential backoff
                print(f"\n  ⚠️  Rate limited! Waiting {delay}s (attempt {attempt+1}/{max_retries})...")
                await asyncio.sleep(delay)
            else:
                raise

        except httpx.TimeoutException:
            print(f"\n  ⏳ Timeout! Retrying (attempt {attempt+1}/{max_retries})...")
            await asyncio.sleep(5)

    raise Exception("Max retries exceeded")


# === MAIN CRAWLER ===

async def crawl_papers(max_papers: int = 20):
    """
    Main crawler function - ties everything together!

    Components used:
    - OAR-94: OpenAlex API client
    - OAR-99: Paper parsing
    - OAR-100: Deduplication
    - OAR-101: Retry handling
    """
    start_time = time.time()
    print_header()

    # Stats
    stats = {
        "API Calls": 0,
        "Papers Fetched": 0,
        "Open Access": 0,
        "Trusted Source": 0,
        "Papers Parsed": 0,
        "Duplicates Skipped": 0,
        "Papers Saved": 0,
        "Full Text Extracted": 0,
        "Rate Limits Hit": 0,
    }

    # Connect to database
    print_section("🔌 CONNECTING")
    print("  📦 Connecting to PostgreSQL...")
    conn = await connect_db()
    if not conn:
        print("  ❌ Failed to connect to database!")
        print("     Run: docker-compose up -d")
        return
    print("  ✅ Connected to PostgreSQL (localhost:5432)")

    # Get existing IDs for deduplication (OAR-100)
    print("\n  🔍 Checking existing papers for deduplication...")
    existing_ids = await get_existing_ids(conn)
    print(f"  ✅ Found {len(existing_ids)} existing papers in database")

    # Start crawling
    print_section(f"🚀 CRAWLING (target: {max_papers} papers)")

    async with httpx.AsyncClient(timeout=30.0) as client:
        cursor = "*"
        batch_num = 0

        while stats["Papers Saved"] < max_papers and cursor:
            batch_num += 1

            # Build request (OAR-94 + ADR-001b: Open Access only)
            params = {
                "filter": "concepts.id:C126322002,has_abstract:true,open_access.is_oa:true",
                "per-page": 10,
                "cursor": cursor,
                "mailto": "demo@example.com",
            }

            print(f"\n  📡 Batch {batch_num}: Fetching from OpenAlex API...")

            # Fetch with retry (OAR-101)
            stats["API Calls"] += 1
            try:
                data = await fetch_with_retry(client, "https://api.openalex.org/works", params, stats)
            except Exception as e:
                print(f"  ❌ Fetch failed: {e}")
                break

            # Process results
            results = data.get("results", [])
            stats["Papers Fetched"] += len(results)
            print(f"  📥 Received {len(results)} papers")

            for raw in results:
                if stats["Papers Saved"] >= max_papers:
                    break

                # Parse paper (OAR-99)
                paper = parse_paper(raw)
                if not paper:
                    continue

                stats["Papers Parsed"] += 1

                # ADR-001b: Check Open Access
                if not paper.get("is_open_access"):
                    continue
                stats["Open Access"] += 1

                # ADR-001b: Check trusted source
                oa_url = paper.get("open_access_url")
                if not is_trusted_source(oa_url):
                    continue
                stats["Trusted Source"] += 1

                # Deduplication check (OAR-100)
                if paper["openalex_id"] in existing_ids:
                    stats["Duplicates Skipped"] += 1
                    print_progress(stats["Papers Saved"], max_papers, f"[DUP] {paper['title']}", "skipping")
                    await asyncio.sleep(0.05)
                    continue

                # ADR-001b: Extract full text from PDF
                if oa_url and PDF_SUPPORT:
                    print_progress(stats["Papers Saved"], max_papers, f"[PDF] {paper['title'][:30]}...", "extracting")
                    full_text = extract_full_text(oa_url)
                    if full_text and len(full_text) > 100:
                        paper["full_text"] = full_text
                        stats["Full Text Extracted"] += 1

                # Save to database
                if await save_paper(conn, paper):
                    stats["Papers Saved"] += 1
                    existing_ids.add(paper["openalex_id"])
                    print_progress(stats["Papers Saved"], max_papers, paper["title"], "saving")
                    await asyncio.sleep(0.1)  # Small delay for visual effect

            # Get next cursor
            cursor = data.get("meta", {}).get("next_cursor")

            # Rate limit (polite pool)
            await asyncio.sleep(0.1)

    # Done!
    duration = time.time() - start_time
    print("\n")
    print_section("✅ CRAWL COMPLETE")
    print_final_stats(stats, duration)

    # Show sample papers
    print("\n  📄 Sample Papers Saved:")
    rows = await conn.fetch("""
        SELECT title, journal, cited_by_count
        FROM papers
        ORDER BY collected_at DESC
        LIMIT 5
    """)
    for i, row in enumerate(rows, 1):
        title = row["title"][:45] + "..." if len(row["title"]) > 45 else row["title"]
        journal = row["journal"][:20] if row["journal"] else "N/A"
        print(f"     {i}. {title}")
        print(f"        📰 {journal} | 📊 {row['cited_by_count']:,} citations")

    await conn.close()

    print("\n  💡 Check database:")
    print("     docker exec oaria-postgres psql -U oaria -c 'SELECT COUNT(*) FROM papers;'")
    print()


# === ENTRY POINT ===

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="OARIA Live Crawler Demo")
    parser.add_argument("--papers", type=int, default=20, help="Number of papers to crawl")
    args = parser.parse_args()

    asyncio.run(crawl_papers(max_papers=args.papers))
