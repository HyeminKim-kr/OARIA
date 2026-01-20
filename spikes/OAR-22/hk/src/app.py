"""
OARIA Paper Viewer - Simple Frontend

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

# Page config
st.set_page_config(
    page_title="OARIA Paper Viewer",
    page_icon="🔬",
    layout="wide"
)

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
    """Crawl papers from OpenAlex API by keyword."""
    papers = []
    cursor = "*"

    with httpx.Client(timeout=30.0) as client:
        while len(papers) < max_papers and cursor:
            params = {
                "search": keyword,
                "filter": "has_abstract:true,type:article",
                "per-page": min(25, max_papers - len(papers)),
                "cursor": cursor,
                "mailto": "demo@oaria.com",
            }

            response = client.get("https://api.openalex.org/works", params=params)
            response.raise_for_status()
            data = response.json()

            for raw in data.get("results", []):
                paper = parse_openalex_paper(raw)
                if paper:
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
    """Get open access papers without full text (prioritize PMC/arXiv URLs)."""
    conn = get_connection()
    cur = conn.cursor()
    # Prioritize PMC, europepmc, arXiv URLs - these actually allow downloads
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
              OR open_access_url LIKE '%%pmc.%%'
          )
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
    """Convert article URL to PDF URL via Europe PMC (more reliable)."""
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

    return url


def download_and_extract_pdf(url: str) -> str:
    """Download PDF and extract text."""
    if not PDF_SUPPORT:
        return "PDF extraction not available. Install pdfplumber: pip install pdfplumber"

    # Convert to PDF URL if needed
    pdf_url = convert_to_pdf_url(url)

    headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}
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

    return "\n\n".join(text_parts)


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

# Header
st.title("🔬 OARIA Paper Viewer")
st.markdown("**Oncology AI Research Intelligence Assistant** - Collected Papers")

st.divider()

# Stats row
try:
    stats = get_stats()

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("📚 Total Papers", stats["total"])

    with col2:
        st.metric("🔓 Open Access", stats["open_access"])

    with col3:
        st.metric("📊 Avg Citations", stats["avg_citations"])

    with col4:
        if stats["latest"]:
            st.metric("🕐 Last Updated", stats["latest"].strftime("%Y-%m-%d %H:%M"))
        else:
            st.metric("🕐 Last Updated", "N/A")

    st.divider()

    # Ensure full_text column exists
    try:
        ensure_fulltext_column()
    except:
        pass

    # Three tabs: Crawl New, Search Existing, Full Text
    tab1, tab2, tab3 = st.tabs(["🌐 Crawl New Papers", "🔍 Search Database", "📄 Full Text"])

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
        st.subheader("Full Text Extraction")
        st.markdown("Extract full text from Open Access papers (PDFs)")

        if not PDF_SUPPORT:
            st.warning("⚠️ pdfplumber not installed. Run: `pip install pdfplumber`")
        else:
            # Stats
            ft_stats = get_fulltext_stats()
            col1, col2 = st.columns(2)
            with col1:
                st.metric("📄 Papers with Full Text", ft_stats["with_fulltext"])
            with col2:
                st.metric("🔓 Open Access Available", ft_stats["oa_total"])

            st.divider()

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
                                    full_text = download_and_extract_pdf(url)
                                    if full_text and len(full_text) > 100:
                                        save_full_text(oa_id, full_text)
                                        st.success(f"✅ Extracted {len(full_text):,} characters!")
                                        st.text_area("Preview", full_text[:2000], height=200)
                                    else:
                                        st.warning("Could not extract text (PDF might be image-based)")
                                except Exception as e:
                                    st.error(f"Error: {e}")
            else:
                st.info("✅ All open access papers have been extracted, or no open access papers available.")

            st.divider()

            # View existing full texts
            st.subheader("📖 View Extracted Full Texts")
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

# Footer
st.divider()
st.markdown("""
<div style='text-align: center; color: gray;'>
    <small>OARIA Paper Crawler Demo | OAR-22 | Built with Streamlit</small>
</div>
""", unsafe_allow_html=True)
