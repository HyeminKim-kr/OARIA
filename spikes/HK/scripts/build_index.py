#!/usr/bin/env python3
"""
Build Index Script

Indexes papers from PostgreSQL into Qdrant vector database.
This is the "offline" indexing pipeline for RAG.

Usage:
    # Create collection and index all papers
    python scripts/build_index.py

    # Recreate collection (delete existing)
    python scripts/build_index.py --recreate

    # Index specific number of papers
    python scripts/build_index.py --limit 1000

    # Use custom Qdrant host
    python scripts/build_index.py --qdrant-host localhost --qdrant-port 6333

Author: HK
Created: 2025-12-30
Spec: F-03 Section 6.1
"""

import argparse
import logging
import sys
import os
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.rag import PaperIndexer, Paper, IndexStats

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
)
logger = logging.getLogger(__name__)


def get_sample_papers() -> list[Paper]:
    """
    Get sample papers for testing/demo.

    In production, this would fetch from PostgreSQL.
    """
    return [
        Paper(
            openalex_id="W2741809807",
            title="EGFR mutations predict response to gefitinib in non-small cell lung cancer",
            abstract="""
            Background: Epidermal growth factor receptor (EGFR) mutations have been identified
            as predictive biomarkers for response to EGFR tyrosine kinase inhibitors (TKIs).

            Methods: We analyzed EGFR mutation status in 200 patients with advanced NSCLC
            treated with gefitinib. Response rates and progression-free survival were compared
            between mutation-positive and mutation-negative groups.

            Results: EGFR mutations were detected in 45 patients (22.5%). The response rate
            was significantly higher in mutation-positive patients (71.1% vs 10.5%, p<0.001).
            Median progression-free survival was 9.2 months for mutation-positive patients
            compared to 2.8 months for mutation-negative patients.

            Conclusions: EGFR mutation testing should be performed in all NSCLC patients
            considered for EGFR TKI therapy. Gefitinib demonstrates remarkable efficacy
            in patients with EGFR-mutant tumors.
            """,
            doi="10.1016/j.example.2020.01.001",
            pmid="12345678",
            authors=["Kim J", "Lee S", "Park H"],
            journal="Journal of Clinical Oncology",
            publication_date=datetime(2020, 3, 15).date(),
            cited_by_count=150,
            is_open_access=True,
            concepts=[{"name": "EGFR"}, {"name": "Lung cancer"}, {"name": "Targeted therapy"}],
        ),
        Paper(
            openalex_id="W2741809808",
            title="Third-generation EGFR TKIs overcome T790M resistance in NSCLC",
            abstract="""
            Background: Acquired resistance to first and second-generation EGFR TKIs
            frequently occurs through the T790M mutation. Third-generation TKIs like
            osimertinib are designed to target this resistance mechanism.

            Methods: This phase III trial compared osimertinib to platinum-pemetrexed
            chemotherapy in patients with T790M-positive advanced NSCLC who had progressed
            on prior EGFR TKI therapy.

            Results: Osimertinib significantly improved progression-free survival compared
            to chemotherapy (10.1 vs 4.4 months, HR 0.30, p<0.001). The response rate was
            71% for osimertinib versus 31% for chemotherapy. Grade 3 or higher adverse
            events occurred in 23% of patients receiving osimertinib.

            Conclusions: Osimertinib is effective treatment for T790M-positive NSCLC
            with a favorable safety profile compared to chemotherapy.
            """,
            doi="10.1016/j.example.2021.02.002",
            pmid="23456789",
            authors=["Park H", "Choi M", "Kim J"],
            journal="New England Journal of Medicine",
            publication_date=datetime(2021, 6, 20).date(),
            cited_by_count=320,
            is_open_access=True,
            concepts=[{"name": "Osimertinib"}, {"name": "T790M"}, {"name": "NSCLC"}],
        ),
        Paper(
            openalex_id="W2741809809",
            title="Immunotherapy in lung cancer: current status and future directions",
            abstract="""
            Immunotherapy has revolutionized the treatment landscape of non-small cell
            lung cancer (NSCLC). Immune checkpoint inhibitors targeting PD-1/PD-L1 have
            demonstrated durable responses in a subset of patients.

            Pembrolizumab and nivolumab are approved for first-line and second-line
            treatment of advanced NSCLC. PD-L1 expression level (≥50% or ≥1%) is used
            as a biomarker to select patients for pembrolizumab monotherapy.

            Combination strategies with chemotherapy or dual checkpoint inhibition
            have shown improved efficacy compared to monotherapy. Key ongoing research
            focuses on identifying additional biomarkers beyond PD-L1, overcoming
            resistance mechanisms, and developing novel immunotherapy targets.

            Future directions include exploring combinations with targeted therapies,
            adoptive cell therapy, and cancer vaccines.
            """,
            doi="10.1016/j.example.2022.03.003",
            pmid="34567890",
            authors=["Lee S", "Park H", "Kim J", "Choi M"],
            journal="Nature Reviews Clinical Oncology",
            publication_date=datetime(2022, 9, 10).date(),
            cited_by_count=280,
            is_open_access=False,
            concepts=[{"name": "Immunotherapy"}, {"name": "PD-1"}, {"name": "Lung cancer"}],
        ),
    ]


def fetch_papers_from_db(
    limit: int = None,
    database_url: str = None,
) -> list[Paper]:
    """
    Fetch papers with full-text from PostgreSQL database.

    Args:
        limit: Maximum number of papers to fetch
        database_url: PostgreSQL connection URL

    Returns:
        List of Paper objects
    """
    import psycopg2
    from psycopg2.extras import RealDictCursor
    import json

    # Database configuration
    db_config = {
        "host": "localhost",
        "port": 5432,
        "database": "oaria",
        "user": "oaria",
        "password": "oaria123",
    }

    logger.info("Connecting to PostgreSQL...")
    conn = psycopg2.connect(**db_config)
    cursor = conn.cursor(cursor_factory=RealDictCursor)

    # Only load papers with full-text (>= 500 chars)
    # Note: authors and concepts columns don't exist in current schema
    query = """
        SELECT
            openalex_id,
            title,
            abstract,
            full_text,
            doi,
            pmid,
            journal,
            publication_date,
            cited_by_count,
            is_open_access,
            open_access_url,
            source,
            arxiv_id
        FROM papers
        WHERE full_text IS NOT NULL
          AND LENGTH(full_text) >= 500
        ORDER BY publication_date DESC
    """

    if limit:
        query += f" LIMIT {limit}"

    cursor.execute(query)
    rows = cursor.fetchall()

    cursor.close()
    conn.close()

    logger.info(f"Loaded {len(rows)} papers from database")

    # Convert to Paper objects
    papers = []
    for row in rows:
        # Use source from database if available, otherwise detect from URL
        source = row.get("source")
        if not source:
            url = row.get("open_access_url", "") or ""
            if "arxiv.org" in url:
                source = "arxiv"
            elif "biorxiv.org" in url:
                source = "biorxiv"
            elif "medrxiv.org" in url:
                source = "medrxiv"
            elif "pmc" in url.lower() or "europepmc" in url:
                source = "pmc"
            else:
                source = "unknown"

        # Get arXiv ID from database or extract from URL
        arxiv_id = row.get("arxiv_id")
        if not arxiv_id and source == "arxiv":
            url = row.get("open_access_url", "") or ""
            if "arxiv.org/abs/" in url:
                arxiv_id = url.split("/abs/")[-1].split("v")[0]

        try:
            paper = Paper(
                openalex_id=row["openalex_id"],
                title=row["title"],
                abstract=row.get("abstract"),
                full_text=row.get("full_text"),  # IMPORTANT: Full-text!
                doi=row.get("doi"),
                pmid=row.get("pmid"),
                arxiv_id=arxiv_id,
                authors=[],  # Not available in current schema
                journal=row.get("journal"),
                publication_date=row.get("publication_date"),
                cited_by_count=row.get("cited_by_count", 0) or 0,
                is_open_access=row.get("is_open_access", True),
                concepts=[],  # Not available in current schema
                source=source,
            )
            papers.append(paper)
        except Exception as e:
            logger.warning(f"Error parsing paper {row.get('openalex_id')}: {e}")

    return papers


def main():
    parser = argparse.ArgumentParser(
        description="Build Qdrant index from papers database",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Create collection and index sample papers (demo mode)
    python scripts/build_index.py

    # Recreate collection from scratch
    python scripts/build_index.py --recreate

    # Index with custom settings
    python scripts/build_index.py --qdrant-host localhost --qdrant-port 6333 --batch-size 50
        """,
    )

    parser.add_argument(
        "--qdrant-host",
        default="localhost",
        help="Qdrant server host (default: localhost)",
    )
    parser.add_argument(
        "--qdrant-port",
        type=int,
        default=6333,
        help="Qdrant server port (default: 6333)",
    )
    parser.add_argument(
        "--recreate",
        action="store_true",
        help="Delete existing collection and recreate",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximum number of papers to index",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=32,
        help="Batch size for embedding (default: 32)",
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=512,
        help="Chunk size in tokens (default: 512)",
    )
    parser.add_argument(
        "--chunk-overlap",
        type=int,
        default=50,
        help="Chunk overlap in tokens (default: 50)",
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Use sample papers for demo (no database required)",
    )

    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("OARIA Paper Indexer")
    logger.info("=" * 60)
    logger.info(f"Qdrant: {args.qdrant_host}:{args.qdrant_port}")
    logger.info(f"Chunk size: {args.chunk_size}, overlap: {args.chunk_overlap}")
    logger.info(f"Batch size: {args.batch_size}")
    logger.info("=" * 60)

    try:
        # Initialize indexer
        indexer = PaperIndexer(
            qdrant_host=args.qdrant_host,
            qdrant_port=args.qdrant_port,
            chunk_size=args.chunk_size,
            chunk_overlap=args.chunk_overlap,
        )

        # Create collection
        created = indexer.create_collection(recreate=args.recreate)
        if created:
            logger.info("Collection created successfully")
        else:
            logger.info("Using existing collection")

        # Get papers
        if args.demo:
            papers = get_sample_papers()
            logger.info(f"Using {len(papers)} sample papers for demo")
        else:
            papers = fetch_papers_from_db(limit=args.limit)
            logger.info(f"Fetched {len(papers)} papers from database")

        if not papers:
            logger.warning("No papers to index!")
            return

        # Calculate total text size
        total_chars = sum(len(p.full_text or "") for p in papers)
        logger.info(f"Total text to index: {total_chars / 1_000_000:.1f} MB")
        logger.info(f"Avg paper length: {total_chars // len(papers):,} chars")

        # Index papers
        logger.info("=" * 60)
        logger.info("Starting indexing (this may take a while)...")
        logger.info("Loading BGE-M3 model for embeddings...")
        stats = indexer.index_papers(papers, batch_size=args.batch_size)

        # Print results
        logger.info("=" * 60)
        logger.info("INDEXING COMPLETE")
        logger.info("=" * 60)
        logger.info(f"Total papers: {stats.total_papers}")
        logger.info(f"Papers indexed: {stats.papers_indexed}")
        logger.info(f"Papers skipped: {stats.papers_skipped}")
        logger.info(f"Total chunks: {stats.total_chunks}")
        logger.info(f"Duration: {stats.duration_seconds:.1f}s")

        if stats.errors:
            logger.warning(f"Errors: {len(stats.errors)}")
            for error in stats.errors[:5]:
                logger.warning(f"  - {error}")

        # Show collection info
        info = indexer.get_collection_info()
        logger.info("=" * 60)
        logger.info("COLLECTION INFO")
        logger.info("=" * 60)
        for key, value in info.items():
            logger.info(f"{key}: {value}")

    except Exception as e:
        logger.error(f"Indexing failed: {e}")
        logger.error("Make sure Qdrant is running: docker run -p 6333:6333 qdrant/qdrant")
        sys.exit(1)


if __name__ == "__main__":
    main()
