"""
OARIA Paper Viewer - Simple Frontend (ADR-001b: Open Access Only)

View collected papers from the database.
Run with: streamlit run src/app.py
"""

import streamlit as st
import psycopg2
import pandas as pd
import httpx
import tempfile
import requests
from pathlib import Path
from datetime import datetime, date

# Try to import pdfplumber
try:
    import pdfplumber
    PDF_SUPPORT = True
except ImportError:
    PDF_SUPPORT = False

# Try to import text preprocessor
try:
    from text_preprocessor import preprocess_full_text
    PREPROCESSOR_AVAILABLE = True
except ImportError:
    PREPROCESSOR_AVAILABLE = False
    def preprocess_full_text(text):
        return text

# ADR-001b: Trusted Open Access sources
TRUSTED_SOURCES = [
    "ncbi.nlm.nih.gov/pmc",
    "europepmc.org",
    "arxiv.org",
    "biorxiv.org",
    "medrxiv.org",
]

def is_trusted_source(url: str) -> bool:
    """Check if URL is from a trusted Open Access source."""
    if not url:
        return False
    return any(source in url.lower() for source in TRUSTED_SOURCES)

# Page config
st.set_page_config(
    page_title="OARIA - Research Intelligence",
    page_icon="🧬",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# OARIA Brand Colors
OARIA_TEAL = "#0D9488"
OARIA_LIGHT_TEAL = "#14B8A6"
OARIA_CORAL = "#F97066"
OARIA_NAVY = "#1E293B"
OARIA_GRAY = "#94A3B8"

# Custom CSS with OARIA branding - Heavy use of brand colors
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@400;500;600;700&family=DM+Sans:wght@400;500;600&display=swap');

    /* Main app styling */
    .stApp {
        font-family: 'DM Sans', sans-serif;
    }

    /* Header styling */
    h1, h2, h3 {
        font-family: 'Outfit', sans-serif !important;
        color: #1E293B !important;
    }

    /* Hero header section */
    .hero-header {
        background: linear-gradient(135deg, #0D9488 0%, #0f766e 50%, #115e59 100%);
        padding: 3rem 2rem 2.5rem 2rem;
        border-radius: 20px;
        margin-bottom: 2rem;
        text-align: center;
        box-shadow: 0 10px 40px rgba(13, 148, 136, 0.3);
        position: relative;
        overflow: hidden;
    }

    .hero-header::before {
        content: '';
        position: absolute;
        top: -50%;
        left: -50%;
        width: 200%;
        height: 200%;
        background: radial-gradient(circle at 30% 30%, rgba(255,255,255,0.1) 0%, transparent 40%);
        pointer-events: none;
    }

    .hero-logo-text {
        font-family: 'Outfit', sans-serif;
        font-size: 4rem;
        font-weight: 700;
        color: white;
        letter-spacing: 0.15em;
        margin: 0;
        text-shadow: 0 4px 20px rgba(0,0,0,0.2);
    }

    .hero-tagline {
        font-family: 'DM Sans', sans-serif;
        color: rgba(255,255,255,0.8);
        font-size: 1rem;
        margin-top: 0.25rem;
        letter-spacing: 0.2em;
        text-transform: uppercase;
        font-weight: 500;
    }

    .hero-subtitle {
        color: rgba(255,255,255,0.6);
        font-size: 0.9rem;
        margin-top: 1rem;
    }

    /* Gate badges */
    .gate-badges {
        display: flex;
        justify-content: center;
        gap: 12px;
        margin-top: 1.5rem;
        flex-wrap: wrap;
    }

    .gate-badge {
        background: rgba(255,255,255,0.15);
        backdrop-filter: blur(10px);
        padding: 8px 16px;
        border-radius: 20px;
        display: flex;
        align-items: center;
        gap: 8px;
        border: 1px solid rgba(255,255,255,0.2);
    }

    .gate-badge span {
        color: white;
        font-size: 0.8rem;
        font-weight: 500;
    }

    /* Primary button styling */
    .stButton > button[kind="primary"] {
        background: linear-gradient(135deg, #0D9488 0%, #0f766e 100%) !important;
        border: none !important;
        font-weight: 600 !important;
        border-radius: 10px !important;
        box-shadow: 0 4px 15px rgba(13, 148, 136, 0.4) !important;
        transition: all 0.2s ease !important;
    }

    .stButton > button[kind="primary"]:hover {
        background: linear-gradient(135deg, #14B8A6 0%, #0D9488 100%) !important;
        box-shadow: 0 6px 20px rgba(13, 148, 136, 0.5) !important;
        transform: translateY(-2px) !important;
    }

    /* Tab styling with brand colors */
    .stTabs [data-baseweb="tab-list"] {
        gap: 4px;
        background: linear-gradient(135deg, #f0fdfa 0%, #ccfbf1 100%);
        padding: 6px;
        border-radius: 14px;
        border: 1px solid #99f6e4;
    }

    .stTabs [data-baseweb="tab"] {
        font-family: 'DM Sans', sans-serif;
        font-weight: 500;
        border-radius: 10px;
        color: #0f766e;
    }

    .stTabs [aria-selected="true"] {
        background: linear-gradient(135deg, #0D9488 0%, #0f766e 100%) !important;
        color: white !important;
        box-shadow: 0 4px 12px rgba(13, 148, 136, 0.3) !important;
    }

    /* Metric styling with brand colors */
    [data-testid="stMetricValue"] {
        font-family: 'Outfit', sans-serif;
        font-size: 2.2rem !important;
        color: #0D9488 !important;
        font-weight: 600 !important;
    }

    [data-testid="stMetricLabel"] {
        font-family: 'DM Sans', sans-serif;
        font-weight: 600;
        color: #0f766e !important;
    }

    /* Section label with brand color */
    .section-label {
        font-size: 0.75rem;
        font-weight: 700;
        color: #0D9488;
        text-transform: uppercase;
        letter-spacing: 0.15em;
        margin-bottom: 1rem;
        padding-bottom: 0.5rem;
        border-bottom: 2px solid #14B8A6;
        display: inline-block;
    }

    /* Stats card styling */
    .stats-wrapper {
        background: linear-gradient(135deg, #f0fdfa 0%, #ffffff 100%);
        border-radius: 16px;
        padding: 1.5rem;
        border: 1px solid #99f6e4;
        margin-bottom: 1.5rem;
    }

    /* Footer with brand colors */
    .oaria-footer {
        text-align: center;
        padding: 2rem;
        background: linear-gradient(135deg, #0D9488 0%, #0f766e 100%);
        margin-top: 3rem;
        border-radius: 20px;
    }

    .oaria-footer p {
        color: rgba(255,255,255,0.9);
        margin: 0;
    }

    .oaria-footer-brand {
        font-family: 'Outfit', sans-serif;
        font-size: 1.5rem;
        font-weight: 700;
        color: white;
        letter-spacing: 0.1em;
    }

    /* Info cards */
    .info-card {
        background: white;
        padding: 20px;
        border-radius: 12px;
        border-left: 4px solid #0D9488;
        box-shadow: 0 2px 12px rgba(13, 148, 136, 0.1);
    }

    /* Hide Streamlit branding */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}

    /* Subheader styling */
    .stSubheader {
        color: #0f766e !important;
    }

    /* Text area styling */
    .stTextArea textarea {
        border: 2px solid #e2e8f0;
        border-radius: 10px;
    }

    .stTextArea textarea:focus {
        border-color: #0D9488;
        box-shadow: 0 0 0 3px rgba(13, 148, 136, 0.1);
    }

    /* Select box styling */
    .stSelectbox > div > div {
        border-radius: 10px;
    }

    /* Expander styling */
    .streamlit-expanderHeader {
        font-family: 'DM Sans', sans-serif;
        font-weight: 600;
        background: linear-gradient(135deg, #f0fdfa 0%, #ffffff 100%);
        border-radius: 10px;
        border-left: 3px solid #0D9488;
    }

    /* DataFrame styling */
    .stDataFrame {
        border-radius: 12px;
        overflow: hidden;
        border: 1px solid #e2e8f0;
    }

    /* Success/Info/Warning/Error messages */
    .stSuccess {
        background: linear-gradient(135deg, #f0fdf4 0%, #dcfce7 100%) !important;
        border-left-color: #0D9488 !important;
    }

    .stInfo {
        background: linear-gradient(135deg, #f0fdfa 0%, #ccfbf1 100%) !important;
        border-left-color: #14B8A6 !important;
    }

    /* Metric container styling */
    [data-testid="stMetricValue"] > div {
        background: linear-gradient(135deg, #0D9488 0%, #14B8A6 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
    }

    /* Input fields */
    .stTextInput > div > div > input {
        border: 2px solid #e2e8f0;
        border-radius: 10px;
        transition: all 0.2s ease;
    }

    .stTextInput > div > div > input:focus {
        border-color: #0D9488 !important;
        box-shadow: 0 0 0 3px rgba(13, 148, 136, 0.15) !important;
    }

    /* Number input */
    .stNumberInput > div > div > input {
        border: 2px solid #e2e8f0;
        border-radius: 10px;
    }

    .stNumberInput > div > div > input:focus {
        border-color: #0D9488 !important;
        box-shadow: 0 0 0 3px rgba(13, 148, 136, 0.15) !important;
    }

    /* Slider */
    .stSlider > div > div > div > div {
        background: linear-gradient(135deg, #0D9488 0%, #14B8A6 100%) !important;
    }

    /* Checkbox */
    .stCheckbox > label > div[data-testid="stMarkdownContainer"] {
        color: #1E293B;
    }

    /* Divider */
    hr {
        border-color: #e2e8f0 !important;
        margin: 1.5rem 0 !important;
    }

    /* Spinner */
    .stSpinner > div {
        border-top-color: #0D9488 !important;
    }

    /* Balloons - teal themed */
    .stBalloons > div > div {
        filter: hue-rotate(150deg);
    }

    /* Code block */
    .stCodeBlock {
        border-radius: 10px;
        border-left: 4px solid #0D9488;
    }

    /* Select box hover */
    .stSelectbox > div > div:hover {
        border-color: #0D9488;
    }

    /* Progress bar */
    .stProgress > div > div {
        background: linear-gradient(135deg, #0D9488 0%, #14B8A6 100%) !important;
    }

    /* Warning styling */
    .stWarning {
        background: linear-gradient(135deg, #fffbeb 0%, #fef3c7 100%) !important;
        border-left-color: #F97066 !important;
    }

    /* Subheader */
    .stMarkdown h2, .stMarkdown h3 {
        color: #0f766e !important;
        border-bottom: 2px solid #ccfbf1;
        padding-bottom: 0.5rem;
    }
</style>
""", unsafe_allow_html=True)

# Database connection
@st.cache_resource
def get_connection():
    """Connect to PostgreSQL."""
    return psycopg2.connect(
        host="localhost",
        port=5432,
        user="oaria",
        password="oaria123",
        database="oaria"
    )

def get_papers(limit=100, keyword=None):
    """Fetch papers from database with optional keyword filter."""
    conn = get_connection()

    if keyword and keyword.strip():
        # Search in title and abstract
        query = """
            SELECT
                openalex_id,
                title,
                abstract,
                doi,
                journal,
                publication_date,
                cited_by_count,
                is_open_access,
                collected_at
            FROM papers
            WHERE title ILIKE %s OR abstract ILIKE %s
            ORDER BY cited_by_count DESC
            LIMIT %s
        """
        search_term = f"%{keyword.strip()}%"
        df = pd.read_sql(query, conn, params=(search_term, search_term, limit))
    else:
        query = """
            SELECT
                openalex_id,
                title,
                abstract,
                doi,
                journal,
                publication_date,
                cited_by_count,
                is_open_access,
                collected_at
            FROM papers
            ORDER BY collected_at DESC
            LIMIT %s
        """
        df = pd.read_sql(query, conn, params=(limit,))
    return df

def crawl_papers_by_keyword(keyword: str, max_papers: int = 20):
    """Crawl Open Access papers from OpenAlex API by keyword (ADR-001b)."""
    papers = []
    cursor = "*"

    with httpx.Client(timeout=30.0) as client:
        while len(papers) < max_papers and cursor:
            params = {
                "search": keyword,
                "filter": "has_abstract:true,type:article,open_access.is_oa:true",  # ADR-001b
                "per-page": min(50, (max_papers - len(papers)) * 3),  # Fetch more to filter
                "cursor": cursor,
                "mailto": "demo@oaria.com",
            }

            response = client.get("https://api.openalex.org/works", params=params)
            response.raise_for_status()
            data = response.json()

            for raw in data.get("results", []):
                if len(papers) >= max_papers:
                    break
                paper = parse_openalex_paper(raw)
                if paper:
                    # ADR-001b: Only accept trusted sources
                    if is_trusted_source(paper.get("open_access_url")):
                        papers.append(paper)

            cursor = data.get("meta", {}).get("next_cursor")

    return papers


def parse_openalex_paper(raw: dict):
    """Parse OpenAlex response to paper dict."""
    # Reconstruct abstract from inverted index
    inverted = raw.get("abstract_inverted_index")
    if not inverted:
        return None

    words = []
    for word, positions in inverted.items():
        for pos in positions:
            words.append((pos, word))
    words.sort(key=lambda x: x[0])
    abstract = " ".join(word for _, word in words)

    if len(abstract) < 50:
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


def save_papers_to_db(papers: list):
    """Save papers to database, skip duplicates."""
    conn = get_connection()
    cur = conn.cursor()
    saved = 0
    skipped = 0

    for paper in papers:
        try:
            cur.execute("""
                INSERT INTO papers (openalex_id, title, abstract, doi, pmid,
                                  publication_date, journal, publisher,
                                  is_open_access, open_access_url, cited_by_count)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (openalex_id) DO NOTHING
            """,
                (paper["openalex_id"], paper["title"], paper["abstract"],
                 paper.get("doi"), paper.get("pmid"), paper.get("publication_date"),
                 paper.get("journal"), paper.get("publisher"),
                 paper.get("is_open_access", False), paper.get("open_access_url"),
                 paper.get("cited_by_count", 0))
            )
            if cur.rowcount > 0:
                saved += 1
            else:
                skipped += 1
        except Exception as e:
            skipped += 1

    conn.commit()
    cur.close()
    return saved, skipped


def ensure_fulltext_column():
    """Add full_text column if it doesn't exist."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("ALTER TABLE papers ADD COLUMN IF NOT EXISTS full_text TEXT")
    cur.execute("ALTER TABLE papers ADD COLUMN IF NOT EXISTS open_access_url TEXT")
    conn.commit()
    cur.close()


def get_open_access_papers_for_extraction(limit=20):
    """
    Get open access papers without full text.

    Supports all trusted Open Access sources:
    - PMC (ncbi.nlm.nih.gov/pmc, europepmc.org)
    - arXiv (arxiv.org)
    - bioRxiv (biorxiv.org)
    - medRxiv (medrxiv.org)
    """
    conn = get_connection()
    cur = conn.cursor()
    # Include all trusted Open Access sources
    cur.execute("""
        SELECT openalex_id, title, open_access_url
        FROM papers
        WHERE is_open_access = true
          AND open_access_url IS NOT NULL
          AND open_access_url != ''
          AND (full_text IS NULL OR full_text = '')
          AND (
              open_access_url LIKE '%%ncbi.nlm.nih.gov%%'
              OR open_access_url LIKE '%%europepmc.org%%'
              OR open_access_url LIKE '%%arxiv.org%%'
              OR open_access_url LIKE '%%biorxiv.org%%'
              OR open_access_url LIKE '%%medrxiv.org%%'
              OR open_access_url LIKE '%%pmc.%%'
          )
        ORDER BY
            CASE
                WHEN open_access_url LIKE '%%ncbi.nlm.nih.gov%%' THEN 1
                WHEN open_access_url LIKE '%%europepmc.org%%' THEN 2
                WHEN open_access_url LIKE '%%arxiv.org%%' THEN 3
                WHEN open_access_url LIKE '%%biorxiv.org%%' THEN 4
                WHEN open_access_url LIKE '%%medrxiv.org%%' THEN 5
                ELSE 6
            END
        LIMIT %s
    """, (limit,))
    papers = cur.fetchall()
    cur.close()
    return papers


def get_paper_with_fulltext(openalex_id: str):
    """Get a single paper with full text."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT openalex_id, title, abstract, full_text, open_access_url, is_open_access
        FROM papers
        WHERE openalex_id = %s
    """, (openalex_id,))
    paper = cur.fetchone()
    cur.close()
    if paper:
        return {
            "openalex_id": paper[0],
            "title": paper[1],
            "abstract": paper[2],
            "full_text": paper[3],
            "open_access_url": paper[4],
            "is_open_access": paper[5]
        }
    return None


def convert_to_pdf_url(url: str) -> str:
    """
    Convert article URL to PDF URL for Open Access sources.

    Supported sources:
    - PMC/Europe PMC (ncbi.nlm.nih.gov, europepmc.org)
    - arXiv (arxiv.org)
    - bioRxiv (biorxiv.org)
    - medRxiv (medrxiv.org)
    """
    import re

    # PMC: https://www.ncbi.nlm.nih.gov/pmc/articles/2127453 -> use Europe PMC
    if 'ncbi.nlm.nih.gov/pmc/articles/' in url:
        pmc_id = url.split('/articles/')[-1].strip('/')
        if not pmc_id.startswith('PMC'):
            pmc_id = f'PMC{pmc_id}'
        # Use Europe PMC which reliably serves PDFs
        return f'https://europepmc.org/backend/ptpmcrender.fcgi?accid={pmc_id}&blobtype=pdf'

    # Europe PMC article page
    if 'europepmc.org/article/' in url:
        # Extract PMC ID from URL like europepmc.org/article/PMC/12345
        parts = url.split('/')
        pmc_id = parts[-1] if parts[-1].startswith('PMC') else f'PMC{parts[-1]}'
        return f'https://europepmc.org/backend/ptpmcrender.fcgi?accid={pmc_id}&blobtype=pdf'

    # arXiv: https://arxiv.org/abs/2301.12345 -> https://arxiv.org/pdf/2301.12345.pdf
    if 'arxiv.org' in url:
        # Handle various arxiv URL formats
        # /abs/2301.12345 or /pdf/2301.12345
        arxiv_match = re.search(r'arxiv\.org/(abs|pdf)/(\d+\.\d+)', url)
        if arxiv_match:
            arxiv_id = arxiv_match.group(2)
            return f'https://arxiv.org/pdf/{arxiv_id}.pdf'
        # Old format: arxiv.org/abs/hep-th/9901001
        arxiv_old_match = re.search(r'arxiv\.org/(abs|pdf)/([a-z-]+/\d+)', url)
        if arxiv_old_match:
            arxiv_id = arxiv_old_match.group(2)
            return f'https://arxiv.org/pdf/{arxiv_id}.pdf'

    # bioRxiv: https://www.biorxiv.org/content/10.1101/2023.01.01.123456v1
    # -> https://www.biorxiv.org/content/10.1101/2023.01.01.123456v1.full.pdf
    if 'biorxiv.org' in url:
        # Remove any trailing parameters
        base_url = url.split('?')[0]
        if not base_url.endswith('.pdf'):
            return f'{base_url}.full.pdf'
        return base_url

    # medRxiv: https://www.medrxiv.org/content/10.1101/2023.01.01.23456789v1
    # -> https://www.medrxiv.org/content/10.1101/2023.01.01.23456789v1.full.pdf
    if 'medrxiv.org' in url:
        base_url = url.split('?')[0]
        if not base_url.endswith('.pdf'):
            return f'{base_url}.full.pdf'
        return base_url

    return url


def download_and_extract_pdf(url: str, apply_preprocessing: bool = True) -> tuple:
    """Download PDF and extract text. Returns (raw_text, processed_text)."""
    if not PDF_SUPPORT:
        error_msg = "PDF extraction not available. Install pdfplumber: pip install pdfplumber"
        return error_msg, error_msg

    # Convert to PDF URL if needed
    pdf_url = convert_to_pdf_url(url)

    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/pdf,*/*",
    }
    response = requests.get(pdf_url, headers=headers, timeout=60, allow_redirects=True)
    response.raise_for_status()

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

    if apply_preprocessing and PREPROCESSOR_AVAILABLE:
        processed_text = preprocess_full_text(raw_text)
    else:
        processed_text = raw_text

    return raw_text, processed_text


def save_full_text(openalex_id: str, full_text: str):
    """Save extracted full text to database."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("UPDATE papers SET full_text = %s WHERE openalex_id = %s", (full_text, openalex_id))
    conn.commit()
    cur.close()


def get_fulltext_stats():
    """Get full text extraction statistics."""
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM papers WHERE full_text IS NOT NULL AND full_text != ''")
    with_fulltext = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM papers WHERE is_open_access = true AND open_access_url IS NOT NULL")
    oa_total = cur.fetchone()[0]

    cur.close()
    return {"with_fulltext": with_fulltext, "oa_total": oa_total}


def get_stats():
    """Get database statistics."""
    conn = get_connection()
    cur = conn.cursor()

    # Total papers
    cur.execute("SELECT COUNT(*) FROM papers")
    total = cur.fetchone()[0]

    # Open access count
    cur.execute("SELECT COUNT(*) FROM papers WHERE is_open_access = true")
    open_access = cur.fetchone()[0]

    # Average citations
    cur.execute("SELECT AVG(cited_by_count) FROM papers")
    avg_citations = cur.fetchone()[0] or 0

    # Latest collection
    cur.execute("SELECT MAX(collected_at) FROM papers")
    latest = cur.fetchone()[0]

    cur.close()
    return {
        "total": total,
        "open_access": open_access,
        "avg_citations": round(avg_citations, 1),
        "latest": latest
    }

# Hero Header with Large Logo
hero_html = """
<div class="hero-header">
    <div style="display: flex; align-items: center; justify-content: center; gap: 32px; margin-bottom: 16px;">
        <svg width="120" height="120" viewBox="0 0 100 100" fill="none" xmlns="http://www.w3.org/2000/svg">
            <circle cx="50" cy="50" r="45" stroke="rgba(255,255,255,0.2)" stroke-width="2" fill="none"/>
            <circle cx="50" cy="50" r="45" stroke="white" stroke-width="3" stroke-dasharray="71 212" stroke-linecap="round" fill="none"/>
            <circle cx="50" cy="50" r="34" stroke="rgba(255,255,255,0.2)" stroke-width="2" fill="none"/>
            <circle cx="50" cy="50" r="34" stroke="rgba(255,255,255,0.8)" stroke-width="3" stroke-dasharray="54 159" stroke-linecap="round" fill="none" transform="rotate(60 50 50)"/>
            <circle cx="50" cy="50" r="23" stroke="rgba(255,255,255,0.2)" stroke-width="2" fill="none"/>
            <circle cx="50" cy="50" r="23" stroke="#F97066" stroke-width="3" stroke-dasharray="36 108" stroke-linecap="round" fill="none" transform="rotate(120 50 50)"/>
            <circle cx="50" cy="50" r="10" fill="white"/>
            <circle cx="50" cy="50" r="5" fill="#0D9488"/>
        </svg>
        <div style="text-align: center;">
            <h1 style="font-family: 'Outfit', sans-serif; font-size: 4.2rem; font-weight: 700; color: white; letter-spacing: 0.15em; margin: 0; text-shadow: 0 4px 20px rgba(0,0,0,0.2);">OARIA</h1>
            <p style="font-family: 'DM Sans', sans-serif; color: rgba(255,255,255,0.7); font-size: 0.65rem; margin-top: 4px; letter-spacing: 0.18em; text-transform: uppercase; font-weight: 500; white-space: nowrap;">Oncology AI Research Intelligence Assistant</p>
        </div>
    </div>
    <div class="gate-badges">
        <div class="gate-badge">
            <div style="width: 10px; height: 10px; background: white; border-radius: 50%; box-shadow: 0 0 8px rgba(255,255,255,0.5);"></div>
            <span>Gate 1: Domain</span>
        </div>
        <div class="gate-badge">
            <div style="width: 10px; height: 10px; background: rgba(255,255,255,0.8); border-radius: 50%; box-shadow: 0 0 8px rgba(255,255,255,0.4);"></div>
            <span>Gate 2: Retrieval</span>
        </div>
        <div class="gate-badge">
            <div style="width: 10px; height: 10px; background: #F97066; border-radius: 50%; box-shadow: 0 0 8px rgba(249,112,102,0.5);"></div>
            <span>Gate 3: Quality</span>
        </div>
    </div>
</div>
"""
st.markdown(hero_html, unsafe_allow_html=True)

# Stats row with branded styling
try:
    stats = get_stats()

    # Stats section with styled container
    st.markdown('<div class="section-label">Database Overview</div>', unsafe_allow_html=True)

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("📚 Total Papers", f"{stats['total']:,}")

    with col2:
        st.metric("🔓 Open Access", f"{stats['open_access']:,}")

    with col3:
        st.metric("📊 Avg Citations", f"{stats['avg_citations']:,.0f}")

    with col4:
        if stats["latest"]:
            st.metric("🕐 Last Updated", stats["latest"].strftime("%Y-%m-%d"))
        else:
            st.metric("🕐 Last Updated", "N/A")

    st.markdown("<div style='margin-bottom: 1.5rem;'></div>", unsafe_allow_html=True)

    # Ensure full_text column exists
    try:
        ensure_fulltext_column()
    except:
        pass

    # Section header
    st.markdown('<div class="section-label">Paper Management</div>', unsafe_allow_html=True)

    # Three tabs: Crawl New, Search Existing, Full Text
    tab1, tab2, tab3 = st.tabs(["🌐 Crawl Papers", "🔍 Search & Browse", "📄 Full Text & Preprocessing"])

    with tab1:
        st.subheader("Crawl Papers from OpenAlex")
        st.markdown("Enter a keyword to fetch papers directly from OpenAlex API")

        col1, col2 = st.columns([3, 1])

        with col1:
            crawl_keyword = st.text_input(
                "Keyword",
                placeholder="e.g., EGFR, immunotherapy, breast cancer...",
                key="crawl_keyword"
            )

        with col2:
            num_papers = st.number_input("Papers to fetch", min_value=5, max_value=100, value=20)

        if st.button("🚀 Crawl Papers", type="primary", use_container_width=True):
            if crawl_keyword:
                with st.spinner(f"Crawling papers for '{crawl_keyword}'..."):
                    try:
                        papers = crawl_papers_by_keyword(crawl_keyword, num_papers)
                        if papers:
                            saved, skipped = save_papers_to_db(papers)
                            st.success(f"✅ Fetched {len(papers)} papers | Saved: {saved} | Duplicates: {skipped}")
                            st.balloons()
                            st.rerun()
                        else:
                            st.warning("No papers found for this keyword")
                    except Exception as e:
                        st.error(f"Error: {e}")
            else:
                st.warning("Please enter a keyword")

    with tab2:
        st.subheader("Search Existing Papers")
        st.markdown("Filter papers already in the database")

        keyword = st.text_input(
            "Filter by keyword",
            placeholder="Filter existing papers...",
            key="search_keyword"
        )

    with tab3:
        st.subheader("Full Text Extraction & Preprocessing")
        st.markdown("""
        <p style="color: #64748b;">
            Extract full text from Open Access papers via Europe PMC. View before/after preprocessing comparison
            to see how the text cleaner removes noise, headers, and garbled content.
        </p>
        """, unsafe_allow_html=True)

        if not PDF_SUPPORT:
            st.warning("⚠️ pdfplumber not installed. Run: `pip install pdfplumber`")
        else:
            # Stats
            ft_stats = get_fulltext_stats()
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("📄 Papers with Full Text", ft_stats["with_fulltext"])
            with col2:
                st.metric("🔓 Open Access Available", ft_stats["oa_total"])
            with col3:
                st.metric("🧹 Preprocessor", "✅ Active" if PREPROCESSOR_AVAILABLE else "❌ Missing")

            st.divider()

            # Sub-tabs for different functions
            subtab1, subtab2, subtab3 = st.tabs(["🔄 Extract New", "👁️ Before/After Compare", "📖 View Full Texts"])

            with subtab1:
                # Get papers available for extraction
                papers_to_extract = get_open_access_papers_for_extraction(limit=10)

                if papers_to_extract:
                    st.markdown(f"**{len(papers_to_extract)} papers ready for extraction:**")

                    for oa_id, title, url in papers_to_extract:
                        with st.expander(f"📄 {title[:60]}..."):
                            st.markdown(f"**URL:** {url}")
                            if st.button(f"Extract Full Text", key=f"extract_{oa_id}"):
                                with st.spinner("Downloading and extracting PDF..."):
                                    try:
                                        raw_text, processed_text = download_and_extract_pdf(url)
                                        if processed_text and len(processed_text) > 100:
                                            save_full_text(oa_id, processed_text)
                                            st.success(f"✅ Extracted {len(processed_text):,} characters!")
                                            st.text_area("Preview", processed_text[:2000], height=200)
                                        else:
                                            st.warning("Could not extract text (PDF might be image-based)")
                                    except Exception as e:
                                        st.error(f"Error: {e}")
                else:
                    st.info("✅ All open access papers have been extracted, or no open access papers available.")

            with subtab2:
                st.markdown("### 🔬 Text Preprocessing Comparison")
                st.markdown("See how the preprocessor cleans PDF-extracted text")

                # Get papers with URLs for live comparison (all supported sources)
                conn = get_connection()
                cur = conn.cursor()
                cur.execute("""
                    SELECT openalex_id, title, open_access_url
                    FROM papers
                    WHERE open_access_url IS NOT NULL
                      AND (
                          open_access_url LIKE '%%ncbi.nlm.nih.gov%%'
                          OR open_access_url LIKE '%%europepmc.org%%'
                          OR open_access_url LIKE '%%arxiv.org%%'
                          OR open_access_url LIKE '%%biorxiv.org%%'
                          OR open_access_url LIKE '%%medrxiv.org%%'
                      )
                    LIMIT 20
                """)
                papers_for_compare = cur.fetchall()
                cur.close()

                if papers_for_compare:
                    selected_paper = st.selectbox(
                        "Select a paper to compare",
                        options=[(p[0], p[1], p[2]) for p in papers_for_compare],
                        format_func=lambda x: x[1][:70] + "..." if len(x[1]) > 70 else x[1],
                        key="compare_select"
                    )

                    if selected_paper and st.button("🔄 Extract & Compare", type="primary"):
                        with st.spinner("Downloading PDF and extracting text..."):
                            try:
                                raw_text, processed_text = download_and_extract_pdf(selected_paper[2])

                                if raw_text and len(raw_text) > 100:
                                    # Stats
                                    raw_len = len(raw_text)
                                    proc_len = len(processed_text)
                                    reduction = ((raw_len - proc_len) / raw_len * 100) if raw_len > 0 else 0

                                    st.success(f"✅ Extracted successfully!")

                                    # Stats row
                                    stat_col1, stat_col2, stat_col3 = st.columns(3)
                                    with stat_col1:
                                        st.metric("Raw Text", f"{raw_len:,} chars")
                                    with stat_col2:
                                        st.metric("Processed Text", f"{proc_len:,} chars")
                                    with stat_col3:
                                        st.metric("Reduction", f"-{reduction:.1f}%")

                                    st.divider()

                                    # Side-by-side comparison
                                    left_col, right_col = st.columns(2)

                                    with left_col:
                                        st.markdown("""
                                        <div style="background: #FEF2F2; padding: 12px 16px; border-radius: 8px; border-left: 4px solid #F97066; margin-bottom: 12px;">
                                            <p style="font-weight: 600; color: #1E293B; margin: 0;">📄 BEFORE (Raw PDF)</p>
                                            <p style="font-size: 0.85rem; color: #64748b; margin: 4px 0 0 0;">Unprocessed text with noise, headers, and artifacts</p>
                                        </div>
                                        """, unsafe_allow_html=True)
                                        st.text_area(
                                            "Raw Text",
                                            raw_text,
                                            height=500,
                                            key="raw_text_area",
                                            label_visibility="collapsed"
                                        )

                                    with right_col:
                                        st.markdown("""
                                        <div style="background: #F0FDF4; padding: 12px 16px; border-radius: 8px; border-left: 4px solid #0D9488; margin-bottom: 12px;">
                                            <p style="font-weight: 600; color: #1E293B; margin: 0;">✨ AFTER (Preprocessed)</p>
                                            <p style="font-size: 0.85rem; color: #64748b; margin: 4px 0 0 0;">Cleaned text ready for RAG indexing</p>
                                        </div>
                                        """, unsafe_allow_html=True)
                                        st.text_area(
                                            "Processed Text",
                                            processed_text,
                                            height=500,
                                            key="processed_text_area",
                                            label_visibility="collapsed"
                                        )

                                    # What was removed - styled cards
                                    st.divider()
                                    st.markdown("""
                                    <p style="font-size: 0.75rem; font-weight: 600; color: #94A3B8; text-transform: uppercase; letter-spacing: 0.1em; margin-bottom: 1rem;">
                                        What the Preprocessor Removes
                                    </p>
                                    """, unsafe_allow_html=True)

                                    rem_col1, rem_col2, rem_col3 = st.columns(3)
                                    with rem_col1:
                                        st.markdown("""
                                        <div style="background: #f8fafc; padding: 16px; border-radius: 8px; border: 1px solid #e2e8f0;">
                                            <p style="font-weight: 600; color: #0D9488; margin: 0 0 8px 0;">📋 Headers & Footers</p>
                                            <p style="font-size: 0.85rem; color: #64748b; margin: 0;">NIH-PA Author Manuscript, Page numbers, Download notices</p>
                                        </div>
                                        """, unsafe_allow_html=True)
                                    with rem_col2:
                                        st.markdown("""
                                        <div style="background: #f8fafc; padding: 16px; border-radius: 8px; border: 1px solid #e2e8f0;">
                                            <p style="font-weight: 600; color: #F97066; margin: 0 0 8px 0;">🔀 Garbled Text</p>
                                            <p style="font-size: 0.85rem; color: #64748b; margin: 0;">Reversed words (eht→the), consonant clusters, corrupted chars</p>
                                        </div>
                                        """, unsafe_allow_html=True)
                                    with rem_col3:
                                        st.markdown("""
                                        <div style="background: #f8fafc; padding: 16px; border-radius: 8px; border: 1px solid #e2e8f0;">
                                            <p style="font-weight: 600; color: #14B8A6; margin: 0 0 8px 0;">📊 Table Fragments</p>
                                            <p style="font-size: 0.85rem; color: #64748b; margin: 0;">Broken table data, pipe separators, short fragments</p>
                                        </div>
                                        """, unsafe_allow_html=True)
                                else:
                                    st.warning("Could not extract text from this PDF")
                            except Exception as e:
                                st.error(f"Error: {e}")
                else:
                    st.info("No papers with PMC URLs available for comparison")

            with subtab3:
                # View existing full texts
                st.markdown("### 📖 View Extracted Full Texts")
                conn = get_connection()
                cur = conn.cursor()
                cur.execute("""
                    SELECT openalex_id, title
                    FROM papers
                    WHERE full_text IS NOT NULL AND full_text != ''
                    LIMIT 20
                """)
                papers_with_ft = cur.fetchall()
                cur.close()

                if papers_with_ft:
                    selected = st.selectbox(
                        "Select a paper to view full text",
                        options=[p[0] for p in papers_with_ft],
                        format_func=lambda x: next((p[1][:60] + "..." for p in papers_with_ft if p[0] == x), x)
                    )

                    if selected:
                        paper = get_paper_with_fulltext(selected)
                        if paper and paper["full_text"]:
                            st.markdown(f"### {paper['title']}")
                            st.markdown(f"**Length:** {len(paper['full_text']):,} characters")
                            st.text_area("Full Text", paper["full_text"], height=400)
                else:
                    st.info("No full texts extracted yet. Extract some papers above!")

    # Common controls
    col1, col2 = st.columns(2)

    with col1:
        limit = st.slider("Max results", 10, 500, 50)

    with col2:
        show_abstract = st.checkbox("Show abstracts", value=False)

    # Load papers
    df = get_papers(limit=limit, keyword=keyword)

    # Show search info
    if keyword:
        st.info(f"🔎 Filtering for: **{keyword}** (sorted by citations)")

    if len(df) == 0:
        st.warning("No papers found in database. Run the crawler first!")
        st.code("python src/live_crawler.py --papers 20")
    else:
        st.subheader(f"📄 Papers ({len(df)} shown)")

        # Display options
        if not show_abstract:
            display_df = df.drop(columns=['abstract'])
        else:
            display_df = df.copy()
            # Truncate abstracts for display
            display_df['abstract'] = display_df['abstract'].apply(
                lambda x: x[:200] + '...' if x and len(x) > 200 else x
            )

        # Format dates
        if 'publication_date' in display_df.columns:
            display_df['publication_date'] = pd.to_datetime(display_df['publication_date']).dt.strftime('%Y-%m-%d')

        if 'collected_at' in display_df.columns:
            display_df['collected_at'] = pd.to_datetime(display_df['collected_at']).dt.strftime('%Y-%m-%d %H:%M')

        # Rename columns for display
        display_df = display_df.rename(columns={
            'openalex_id': 'OpenAlex ID',
            'title': 'Title',
            'abstract': 'Abstract',
            'doi': 'DOI',
            'journal': 'Journal',
            'publication_date': 'Published',
            'cited_by_count': 'Citations',
            'is_open_access': 'Open Access',
            'collected_at': 'Collected'
        })

        # Show dataframe
        st.dataframe(
            display_df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Title": st.column_config.TextColumn(width="large"),
                "Citations": st.column_config.NumberColumn(format="%d"),
                "Open Access": st.column_config.CheckboxColumn(),
            }
        )

        # Paper detail expander
        st.divider()
        st.subheader("📖 Paper Details")

        paper_titles = df['title'].tolist()
        selected_title = st.selectbox("Select a paper to view details", paper_titles)

        if selected_title:
            paper = df[df['title'] == selected_title].iloc[0]

            col1, col2 = st.columns([2, 1])

            with col1:
                st.markdown(f"### {paper['title']}")
                st.markdown(f"**Journal:** {paper['journal'] or 'N/A'}")
                st.markdown(f"**Published:** {paper['publication_date'] or 'N/A'}")
                if paper['doi']:
                    st.markdown(f"**DOI:** [{paper['doi']}](https://doi.org/{paper['doi']})")

            with col2:
                st.metric("Citations", paper['cited_by_count'])
                if paper['is_open_access']:
                    st.success("🔓 Open Access")
                else:
                    st.info("🔒 Not Open Access")

            st.markdown("**Abstract:**")
            st.markdown(paper['abstract'] or "No abstract available")

except Exception as e:
    st.error(f"Database connection error: {e}")
    st.info("Make sure PostgreSQL is running:")
    st.code("docker-compose up -d")

# Footer with OARIA branding
footer_html = """
<div class="oaria-footer">
    <div style="margin-bottom: 12px; display: flex; align-items: center; justify-content: center; gap: 16px;">
        <svg width="40" height="40" viewBox="0 0 40 40" fill="none" xmlns="http://www.w3.org/2000/svg">
            <circle cx="20" cy="20" r="18" stroke="rgba(255,255,255,0.3)" stroke-width="1.5" fill="none"/>
            <circle cx="20" cy="20" r="18" stroke="white" stroke-width="2" stroke-dasharray="28 85" stroke-linecap="round" fill="none"/>
            <circle cx="20" cy="20" r="13" stroke="rgba(255,255,255,0.3)" stroke-width="1.5" fill="none"/>
            <circle cx="20" cy="20" r="13" stroke="rgba(255,255,255,0.8)" stroke-width="2" stroke-dasharray="21 62" stroke-linecap="round" fill="none" transform="rotate(60 20 20)"/>
            <circle cx="20" cy="20" r="8" stroke="rgba(255,255,255,0.3)" stroke-width="1.5" fill="none"/>
            <circle cx="20" cy="20" r="8" stroke="#F97066" stroke-width="2" stroke-dasharray="13 38" stroke-linecap="round" fill="none" transform="rotate(120 20 20)"/>
            <circle cx="20" cy="20" r="4" fill="white"/>
        </svg>
        <span class="oaria-footer-brand">OARIA</span>
    </div>
    <p style="color: rgba(255,255,255,0.9); margin-bottom: 8px; font-size: 0.9rem;">Triple Gate Research Intelligence</p>
    <div style="display: flex; justify-content: center; gap: 16px; font-size: 0.75rem; color: rgba(255,255,255,0.6);">
        <span>Paper Crawler</span>
        <span>•</span>
        <span>Full Text Extraction</span>
        <span>•</span>
        <span>Text Preprocessing</span>
    </div>
    <p style="font-size: 0.7rem; margin-top: 12px; color: rgba(255,255,255,0.4);">HK Spike • Built with Streamlit</p>
</div>
"""
st.markdown(footer_html, unsafe_allow_html=True)
