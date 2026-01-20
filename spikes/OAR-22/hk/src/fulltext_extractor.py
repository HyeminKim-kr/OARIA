"""
Full Text Extractor for Open Access Papers

Downloads PDFs from open access URLs and extracts text.

Run with: python fulltext_extractor.py --limit 10
"""

import sys
import time
import tempfile
import requests
import psycopg2
from pathlib import Path

# Try to import pdfplumber, install if missing
try:
    import pdfplumber
except ImportError:
    print("Installing pdfplumber...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "pdfplumber", "-q"])
    import pdfplumber


# === DATABASE ===

def get_connection():
    """Connect to PostgreSQL."""
    return psycopg2.connect(
        host="localhost",
        port=5432,
        user="oaria",
        password="oaria123",
        database="oaria"
    )


def ensure_fulltext_column():
    """Add full_text column if it doesn't exist."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        ALTER TABLE papers
        ADD COLUMN IF NOT EXISTS full_text TEXT
    """)
    conn.commit()
    cur.close()
    conn.close()
    print("  ✅ Database schema ready")


def get_open_access_papers(limit=10):
    """Get open access papers without full text."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT openalex_id, title, open_access_url
        FROM papers
        WHERE is_open_access = true
          AND open_access_url IS NOT NULL
          AND (full_text IS NULL OR full_text = '')
        LIMIT %s
    """, (limit,))
    papers = cur.fetchall()
    cur.close()
    conn.close()
    return papers


def save_full_text(openalex_id: str, full_text: str):
    """Save extracted full text to database."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        UPDATE papers
        SET full_text = %s
        WHERE openalex_id = %s
    """, (full_text, openalex_id))
    conn.commit()
    cur.close()
    conn.close()


# === PDF EXTRACTION ===

def download_pdf(url: str, timeout: int = 30) -> bytes:
    """Download PDF from URL."""
    headers = {
        "User-Agent": "OARIA Research Bot (mailto:oaria@example.com)"
    }
    response = requests.get(url, headers=headers, timeout=timeout, allow_redirects=True)
    response.raise_for_status()
    return response.content


def extract_text_from_pdf(pdf_bytes: bytes) -> str:
    """Extract text from PDF bytes using pdfplumber."""
    text_parts = []

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(pdf_bytes)
        tmp_path = tmp.name

    try:
        with pdfplumber.open(tmp_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)
    finally:
        Path(tmp_path).unlink(missing_ok=True)

    return "\n\n".join(text_parts)


# === MAIN ===

def extract_full_texts(limit: int = 10):
    """Main extraction function."""
    print("\n" + "=" * 60)
    print("  📄 FULL TEXT EXTRACTOR")
    print("=" * 60)

    # Ensure schema
    print("\n  📦 Checking database schema...")
    ensure_fulltext_column()

    # Get papers
    print(f"\n  🔍 Finding open access papers (limit: {limit})...")
    papers = get_open_access_papers(limit)

    if not papers:
        print("  ⚠️  No open access papers found without full text")
        return

    print(f"  ✅ Found {len(papers)} papers to process")

    # Process each paper
    stats = {"success": 0, "failed": 0}

    print("\n  🚀 Extracting full texts...\n")

    for i, (openalex_id, title, url) in enumerate(papers, 1):
        short_title = title[:40] + "..." if len(title) > 40 else title
        print(f"  [{i}/{len(papers)}] {short_title}")

        try:
            # Download PDF
            print(f"       📥 Downloading from {url[:50]}...")
            pdf_bytes = download_pdf(url)

            # Extract text
            print(f"       📝 Extracting text...")
            full_text = extract_text_from_pdf(pdf_bytes)

            if full_text and len(full_text) > 100:
                # Save to database
                save_full_text(openalex_id, full_text)
                stats["success"] += 1
                print(f"       ✅ Saved {len(full_text):,} characters")
            else:
                stats["failed"] += 1
                print(f"       ⚠️  No text extracted (PDF might be image-based)")

        except requests.exceptions.RequestException as e:
            stats["failed"] += 1
            print(f"       ❌ Download failed: {type(e).__name__}")

        except Exception as e:
            stats["failed"] += 1
            print(f"       ❌ Error: {type(e).__name__}: {str(e)[:50]}")

        # Rate limiting
        time.sleep(1)
        print()

    # Summary
    print("=" * 60)
    print(f"  📊 SUMMARY")
    print(f"     Success: {stats['success']}")
    print(f"     Failed:  {stats['failed']}")
    print("=" * 60)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Extract full text from open access papers")
    parser.add_argument("--limit", type=int, default=10, help="Max papers to process")
    args = parser.parse_args()

    extract_full_texts(limit=args.limit)
