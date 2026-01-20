"""
Paper Indexer for Qdrant

Indexes papers from PostgreSQL into Qdrant vector database:
- Chunks text with overlap
- Generates BGE-M3 hybrid embeddings (dense + sparse)
- Upserts to Qdrant collection

Author: HK
Created: 2025-12-30
Spec: F-03 Section 6.1
"""

import logging
from typing import Optional, AsyncGenerator
from datetime import datetime

from qdrant_client import QdrantClient
from qdrant_client.models import (
    VectorParams,
    Distance,
    SparseVectorParams,
    SparseIndexParams,
    PointStruct,
    SparseVector,
)

from .models import Chunk, Paper, IndexStats
from .chunker import TextChunker
from .embedder import BGEM3Embedder

import uuid

# Import journal tier classification
import sys
sys.path.insert(0, str(__file__).rsplit("/", 2)[0])
try:
    from config.journal_tiers import get_journal_tier
except ImportError:
    # Fallback if config not available
    def get_journal_tier(journal_name):
        return "tier4"

logger = logging.getLogger(__name__)


class PaperIndexer:
    """
    Indexes papers into Qdrant for RAG retrieval.

    Design Decisions:
    -----------------
    1. WHY BATCH INDEXING?
       - Embedding models are more efficient with batches
       - Reduces round-trips to Qdrant
       - Better GPU utilization

    2. WHY TRACK INDEXED PAPERS?
       - Avoid re-indexing unchanged papers
       - Support incremental updates
       - Resume after failures

    3. WHY HYBRID VECTORS?
       - Dense for semantic search
       - Sparse for keyword matching
       - Best retrieval quality

    Usage:
        indexer = PaperIndexer()
        indexer.create_collection()  # Once at setup

        # Index papers
        stats = indexer.index_papers(papers)
        print(f"Indexed {stats.papers_indexed} papers")
    """

    COLLECTION_NAME = "oncology_papers"

    def __init__(
        self,
        qdrant_host: str = "localhost",
        qdrant_port: int = 6333,
        chunk_size: int = 512,
        chunk_overlap: int = 50,
    ):
        """
        Initialize indexer.

        Args:
            qdrant_host: Qdrant server host
            qdrant_port: Qdrant server port
            chunk_size: Target chunk size in tokens
            chunk_overlap: Overlap between chunks in tokens
        """
        self.qdrant = QdrantClient(host=qdrant_host, port=qdrant_port)
        self.chunker = TextChunker(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )
        self.embedder = BGEM3Embedder()

        logger.info(
            f"PaperIndexer initialized: "
            f"qdrant={qdrant_host}:{qdrant_port}, "
            f"chunk_size={chunk_size}, overlap={chunk_overlap}"
        )

    def create_collection(self, recreate: bool = False) -> bool:
        """
        Create Qdrant collection for hybrid search.

        Args:
            recreate: If True, delete existing collection first

        Returns:
            True if collection was created
        """
        collection_exists = self.qdrant.collection_exists(self.COLLECTION_NAME)

        if collection_exists:
            if recreate:
                logger.warning(f"Deleting existing collection: {self.COLLECTION_NAME}")
                self.qdrant.delete_collection(self.COLLECTION_NAME)
            else:
                logger.info(f"Collection already exists: {self.COLLECTION_NAME}")
                return False

        # Create collection with hybrid vector config
        self.qdrant.create_collection(
            collection_name=self.COLLECTION_NAME,
            # Dense vector config (BGE-M3: 1024 dims)
            vectors_config={
                "dense": VectorParams(
                    size=1024,
                    distance=Distance.COSINE,
                )
            },
            # Sparse vector config for hybrid search
            sparse_vectors_config={
                "sparse": SparseVectorParams(
                    index=SparseIndexParams(
                        on_disk=False,  # Keep in memory for speed
                    )
                )
            },
        )

        logger.info(f"Created collection: {self.COLLECTION_NAME}")
        return True

    def _create_point(
        self,
        chunk: Chunk,
        dense_vector: list[float],
        sparse_indices: list[int],
        sparse_values: list[float],
    ) -> PointStruct:
        """
        Create a Qdrant point from a chunk and its embeddings.

        Args:
            chunk: The text chunk
            dense_vector: 1024-dim dense embedding
            sparse_indices: Sparse vector token IDs
            sparse_values: Sparse vector weights

        Returns:
            PointStruct ready for upsert
        """
        # Get journal tier classification
        journal_name = chunk.metadata.get("journal")
        journal_tier = get_journal_tier(journal_name)

        # Convert chunk_id to UUID (Qdrant requires integer or UUID IDs)
        point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, chunk.chunk_id))

        return PointStruct(
            id=point_id,
            vector={
                "dense": dense_vector,
                "sparse": SparseVector(
                    indices=sparse_indices,
                    values=sparse_values,
                )
            },
            payload={
                # Text content
                "text": chunk.text,
                "chunk_id": chunk.chunk_id,  # Original string ID for reference
                "chunk_index": chunk.chunk_index,

                # Paper identifiers (source-appropriate)
                "paper_id": chunk.paper_id,
                "openalex_id": chunk.paper_id,  # Alias
                "doi": chunk.metadata.get("doi"),
                "pmid": chunk.metadata.get("pmid"),  # PMC only
                "arxiv_id": chunk.metadata.get("arxiv_id"),  # arXiv only

                # Paper metadata
                "title": chunk.metadata.get("title", ""),
                "authors": chunk.metadata.get("authors", []),
                "journal": journal_name,
                "journal_tier": journal_tier,  # NEW: tier1/tier2/tier3/tier4
                "publication_date": chunk.metadata.get("publication_date"),
                "source": chunk.metadata.get("source"),  # 'pmc', 'arxiv', 'biorxiv', 'medrxiv'

                # Filtering fields
                "publication_year": self._extract_year(
                    chunk.metadata.get("publication_date")
                ),
                "cited_by_count": chunk.metadata.get("cited_by_count", 0),
                "concepts": chunk.metadata.get("concepts", []),
            }
        )

    def _extract_year(self, date_str: Optional[str]) -> Optional[int]:
        """Extract year from date string."""
        if not date_str:
            return None
        try:
            if isinstance(date_str, str):
                return int(date_str[:4])
            return date_str.year
        except (ValueError, AttributeError):
            return None

    def index_paper(
        self,
        paper: Paper,
        batch_size: int = 32,
    ) -> int:
        """
        Index a single paper into Qdrant.

        REQUIRES full_text - papers without full-text are skipped.
        This ensures high-quality RAG with comprehensive content.

        Args:
            paper: Paper to index (must have full_text)
            batch_size: Batch size for embedding

        Returns:
            Number of chunks indexed (0 if no full_text)
        """
        # STRICT: Only index papers with full-text content
        if not paper.full_text or len(paper.full_text) < 500:
            logger.info(
                f"Skipping paper without full-text: {paper.openalex_id} "
                f"(full_text length: {len(paper.full_text) if paper.full_text else 0})"
            )
            return 0

        # Create metadata with source-appropriate identifiers
        metadata = {
            "title": paper.title,
            "doi": paper.doi,
            "pmid": paper.pmid,  # Only for PMC papers
            "arxiv_id": paper.arxiv_id,  # Only for arXiv papers
            "journal": paper.journal,
            "publication_date": str(paper.publication_date) if paper.publication_date else None,
            "authors": paper.authors[:5],  # Limit authors for payload size
            "cited_by_count": paper.cited_by_count,
            "source": paper.source,  # 'pmc', 'arxiv', 'biorxiv', 'medrxiv'
            "concepts": [c.get("name", "") for c in paper.concepts[:10]],
        }

        # Chunk the full-text paper
        chunks = self.chunker.chunk_full_text_paper(
            paper_id=paper.openalex_id,
            title=paper.title,
            full_text=paper.full_text,
            metadata=metadata,
        )

        if not chunks:
            return 0

        # Embed chunks
        chunk_embeddings = self.embedder.embed_chunks(
            chunks,
            return_sparse=True,
            batch_size=batch_size,
        )

        # Create points
        points = []
        for ce in chunk_embeddings:
            point = self._create_point(
                chunk=ce.chunk,
                dense_vector=ce.dense_vector,
                sparse_indices=ce.sparse_indices or [],
                sparse_values=ce.sparse_values or [],
            )
            points.append(point)

        # Upsert to Qdrant
        if points:
            self.qdrant.upsert(
                collection_name=self.COLLECTION_NAME,
                points=points,
            )

        return len(points)

    def index_papers(
        self,
        papers: list[Paper],
        batch_size: int = 32,
    ) -> IndexStats:
        """
        Index multiple papers into Qdrant.

        Args:
            papers: Papers to index
            batch_size: Batch size for embedding

        Returns:
            IndexStats with indexing results
        """
        start_time = datetime.now()
        stats = IndexStats()
        stats.total_papers = len(papers)

        for paper in papers:
            try:
                chunks = self.index_paper(paper, batch_size)
                if chunks > 0:
                    stats.papers_indexed += 1
                    stats.total_chunks += chunks
                else:
                    stats.papers_skipped += 1

                if stats.papers_indexed % 100 == 0 and stats.papers_indexed > 0:
                    logger.info(
                        f"Indexing progress: {stats.papers_indexed}/{stats.total_papers} papers, "
                        f"{stats.total_chunks} chunks"
                    )

            except Exception as e:
                stats.errors.append(f"{paper.openalex_id}: {str(e)}")
                logger.error(f"Error indexing paper {paper.openalex_id}: {e}")

        stats.duration_seconds = (datetime.now() - start_time).total_seconds()

        logger.info(
            f"Indexing complete: {stats.papers_indexed} papers, "
            f"{stats.total_chunks} chunks, "
            f"{stats.duration_seconds:.1f}s"
        )

        return stats

    def index_papers_dict(
        self,
        papers: list[dict],
        batch_size: int = 32,
    ) -> IndexStats:
        """
        Index papers from dictionaries (e.g., from database query).

        REQUIRES full_text field - papers without full-text are skipped.

        Args:
            papers: List of paper dicts with REQUIRED 'full_text' field
            batch_size: Batch size for embedding

        Returns:
            IndexStats with indexing results
        """
        # Convert dicts to Paper models
        paper_models = []
        for p in papers:
            try:
                # Detect source from URL if not provided
                source = p.get("source")
                if not source:
                    url = p.get("open_access_url", "")
                    if "arxiv.org" in url:
                        source = "arxiv"
                    elif "biorxiv.org" in url:
                        source = "biorxiv"
                    elif "medrxiv.org" in url:
                        source = "medrxiv"
                    elif "pmc" in url.lower() or "europepmc" in url:
                        source = "pmc"

                paper = Paper(
                    openalex_id=p.get("openalex_id", p.get("id", "")),
                    title=p.get("title", ""),
                    abstract=p.get("abstract"),
                    full_text=p.get("full_text"),  # REQUIRED
                    doi=p.get("doi"),
                    pmid=p.get("pmid"),  # Only PMC papers have this
                    arxiv_id=p.get("arxiv_id"),  # Only arXiv papers
                    authors=p.get("authors", []),
                    journal=p.get("journal"),
                    publication_date=p.get("publication_date"),
                    cited_by_count=p.get("cited_by_count", 0),
                    is_open_access=True,  # All indexed papers must be OA
                    concepts=p.get("concepts", []),
                    source=source,
                )
                paper_models.append(paper)
            except Exception as e:
                logger.error(f"Error parsing paper dict: {e}")

        return self.index_papers(paper_models, batch_size)

    def get_collection_info(self) -> dict:
        """Get information about the collection."""
        try:
            info = self.qdrant.get_collection(self.COLLECTION_NAME)
            return {
                "name": self.COLLECTION_NAME,
                "points_count": info.points_count,
                "vectors_count": info.vectors_count,
                "indexed_vectors_count": info.indexed_vectors_count,
                "status": info.status.value,
            }
        except Exception as e:
            logger.error(f"Error getting collection info: {e}")
            return {"error": str(e)}

    def delete_paper(self, paper_id: str) -> bool:
        """
        Delete all chunks for a paper from the index.

        Args:
            paper_id: OpenAlex paper ID

        Returns:
            True if deletion was successful
        """
        try:
            from qdrant_client.models import Filter, FieldCondition, MatchValue

            self.qdrant.delete(
                collection_name=self.COLLECTION_NAME,
                points_selector=Filter(
                    must=[
                        FieldCondition(
                            key="paper_id",
                            match=MatchValue(value=paper_id)
                        )
                    ]
                ),
            )
            logger.info(f"Deleted paper from index: {paper_id}")
            return True
        except Exception as e:
            logger.error(f"Error deleting paper {paper_id}: {e}")
            return False


# Convenience functions
def create_index(
    qdrant_host: str = "localhost",
    qdrant_port: int = 6333,
    recreate: bool = False,
) -> bool:
    """Create Qdrant collection for paper indexing."""
    indexer = PaperIndexer(qdrant_host=qdrant_host, qdrant_port=qdrant_port)
    return indexer.create_collection(recreate=recreate)


def index_papers(
    papers: list[dict],
    qdrant_host: str = "localhost",
    qdrant_port: int = 6333,
) -> IndexStats:
    """Quick function to index papers."""
    indexer = PaperIndexer(qdrant_host=qdrant_host, qdrant_port=qdrant_port)
    return indexer.index_papers_dict(papers)


if __name__ == "__main__":
    print("=== Paper Indexer Demo ===\n")

    # Check Qdrant connection
    try:
        indexer = PaperIndexer()
        info = indexer.get_collection_info()
        if "error" in info:
            print(f"Qdrant not available: {info['error']}")
            print("\nTo start Qdrant: docker run -p 6333:6333 qdrant/qdrant")
        else:
            print(f"Collection info: {info}")
    except Exception as e:
        print(f"Error: {e}")
        print("\nMake sure Qdrant is running:")
        print("  docker run -p 6333:6333 qdrant/qdrant")
