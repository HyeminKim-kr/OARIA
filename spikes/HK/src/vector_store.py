"""
OAR-31: Vector Store Implementation

Abstraction layer for vector storage supporting ChromaDB (dev) and Qdrant (prod).
Handles embedding storage, ANN search, and metadata filtering.

Author: HK
Created: 2025-12-30
Jira: OAR-31
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, Any
import json
import numpy as np


@dataclass
class SearchResult:
    """A single search result with score and metadata."""
    id: str
    score: float
    text: str
    metadata: dict

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "score": self.score,
            "text": self.text,
            "metadata": self.metadata,
        }


class VectorStore(ABC):
    """
    Abstract base class for vector stores.

    Design Decision: Why abstraction?
    - Allows switching between ChromaDB (local dev) and Qdrant (production)
    - Consistent interface regardless of backend
    - Easy testing with mock implementations
    """

    @abstractmethod
    def add(
        self,
        ids: list[str],
        embeddings: list[list[float]],
        texts: list[str],
        metadatas: list[dict],
    ) -> None:
        """Add vectors with metadata to the store."""
        pass

    @abstractmethod
    def search(
        self,
        query_embedding: list[float],
        top_k: int = 10,
        filter_dict: Optional[dict] = None,
    ) -> list[SearchResult]:
        """Search for similar vectors."""
        pass

    @abstractmethod
    def delete(self, ids: list[str]) -> None:
        """Delete vectors by ID."""
        pass

    @abstractmethod
    def count(self) -> int:
        """Get total vector count."""
        pass

    @abstractmethod
    def clear(self) -> None:
        """Clear all vectors."""
        pass


class ChromaDBStore(VectorStore):
    """
    ChromaDB-based vector store for development.

    Why ChromaDB for development?
    - Zero configuration (embedded mode)
    - No Docker/server needed
    - SQLite-based persistence
    - Good for <100k vectors
    - Fast local iteration

    Limitations:
    - Single-machine only
    - Slower than Qdrant at scale
    - Limited filtering capabilities
    """

    def __init__(
        self,
        collection_name: str = "oaria_papers",
        persist_directory: str = "./chroma_db",
    ):
        try:
            import chromadb
            from chromadb.config import Settings
        except ImportError:
            raise ImportError("chromadb required. Install with: pip install chromadb")

        self.collection_name = collection_name
        self.persist_directory = persist_directory

        # Initialize client with persistence
        self.client = chromadb.Client(Settings(
            chroma_db_impl="duckdb+parquet",
            persist_directory=persist_directory,
            anonymized_telemetry=False,
        ))

        # Get or create collection
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},  # Use cosine similarity
        )

    def add(
        self,
        ids: list[str],
        embeddings: list[list[float]],
        texts: list[str],
        metadatas: list[dict],
    ) -> None:
        """Add vectors to ChromaDB."""
        # ChromaDB handles duplicates by ID (upsert behavior)
        self.collection.add(
            ids=ids,
            embeddings=embeddings,
            documents=texts,
            metadatas=metadatas,
        )

    def search(
        self,
        query_embedding: list[float],
        top_k: int = 10,
        filter_dict: Optional[dict] = None,
    ) -> list[SearchResult]:
        """Search ChromaDB for similar vectors."""
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            where=filter_dict,
            include=["documents", "metadatas", "distances"],
        )

        search_results = []
        if results["ids"] and results["ids"][0]:
            for i, id_ in enumerate(results["ids"][0]):
                # ChromaDB returns distances, convert to similarity
                # For cosine distance: similarity = 1 - distance
                distance = results["distances"][0][i] if results["distances"] else 0
                score = 1 - distance

                search_results.append(SearchResult(
                    id=id_,
                    score=score,
                    text=results["documents"][0][i] if results["documents"] else "",
                    metadata=results["metadatas"][0][i] if results["metadatas"] else {},
                ))

        return search_results

    def delete(self, ids: list[str]) -> None:
        """Delete vectors by ID."""
        self.collection.delete(ids=ids)

    def count(self) -> int:
        """Get total vector count."""
        return self.collection.count()

    def clear(self) -> None:
        """Clear all vectors."""
        # Delete and recreate collection
        self.client.delete_collection(self.collection_name)
        self.collection = self.client.create_collection(
            name=self.collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    def persist(self) -> None:
        """Persist to disk (ChromaDB-specific)."""
        self.client.persist()


class QdrantStore(VectorStore):
    """
    Qdrant-based vector store for production.

    Why Qdrant for production?
    - Designed for billion-scale vector search
    - Native hybrid search (dense + sparse)
    - Rich filtering capabilities
    - Horizontal scaling
    - Better performance at scale

    Requirements:
    - Qdrant server running (Docker or cloud)
    - qdrant-client package
    """

    def __init__(
        self,
        collection_name: str = "oaria_papers",
        host: str = "localhost",
        port: int = 6333,
        embedding_dim: int = 768,
        recreate: bool = False,
    ):
        try:
            from qdrant_client import QdrantClient
            from qdrant_client.http import models
            self.models = models
        except ImportError:
            raise ImportError("qdrant-client required. Install with: pip install qdrant-client")

        self.collection_name = collection_name
        self.embedding_dim = embedding_dim

        # Connect to Qdrant
        self.client = QdrantClient(host=host, port=port)

        # Check if collection exists
        collections = self.client.get_collections().collections
        exists = any(c.name == collection_name for c in collections)

        if recreate and exists:
            self.client.delete_collection(collection_name)
            exists = False

        if not exists:
            self._create_collection()

    def _create_collection(self):
        """Create Qdrant collection with optimal settings."""
        self.client.create_collection(
            collection_name=self.collection_name,
            vectors_config=self.models.VectorParams(
                size=self.embedding_dim,
                distance=self.models.Distance.COSINE,
            ),
            # Optimize for search speed
            hnsw_config=self.models.HnswConfigDiff(
                m=16,  # Number of edges per node
                ef_construct=100,  # Construction-time accuracy
            ),
            # Enable payload indexing for filtering
            optimizers_config=self.models.OptimizersConfigDiff(
                indexing_threshold=10000,  # Index after 10k vectors
            ),
        )

        # Create payload indexes for common filter fields
        self.client.create_payload_index(
            collection_name=self.collection_name,
            field_name="paper_id",
            field_schema=self.models.PayloadSchemaType.KEYWORD,
        )

    def add(
        self,
        ids: list[str],
        embeddings: list[list[float]],
        texts: list[str],
        metadatas: list[dict],
    ) -> None:
        """Add vectors to Qdrant."""
        points = []
        for i, (id_, emb, text, meta) in enumerate(zip(ids, embeddings, texts, metadatas)):
            # Qdrant requires numeric IDs or UUIDs
            # We'll store the string ID in payload and use hash for point ID
            point_id = abs(hash(id_)) % (2**63)  # Positive int64

            payload = {
                "string_id": id_,
                "text": text,
                **meta,
            }

            points.append(self.models.PointStruct(
                id=point_id,
                vector=emb,
                payload=payload,
            ))

        # Batch upsert
        self.client.upsert(
            collection_name=self.collection_name,
            points=points,
        )

    def search(
        self,
        query_embedding: list[float],
        top_k: int = 10,
        filter_dict: Optional[dict] = None,
    ) -> list[SearchResult]:
        """Search Qdrant for similar vectors."""
        # Convert filter dict to Qdrant filter
        qdrant_filter = None
        if filter_dict:
            conditions = []
            for key, value in filter_dict.items():
                conditions.append(
                    self.models.FieldCondition(
                        key=key,
                        match=self.models.MatchValue(value=value),
                    )
                )
            qdrant_filter = self.models.Filter(must=conditions)

        results = self.client.search(
            collection_name=self.collection_name,
            query_vector=query_embedding,
            limit=top_k,
            query_filter=qdrant_filter,
            with_payload=True,
        )

        search_results = []
        for hit in results:
            payload = hit.payload or {}
            search_results.append(SearchResult(
                id=payload.get("string_id", str(hit.id)),
                score=hit.score,
                text=payload.get("text", ""),
                metadata={k: v for k, v in payload.items() if k not in ["string_id", "text"]},
            ))

        return search_results

    def delete(self, ids: list[str]) -> None:
        """Delete vectors by string ID."""
        # Convert string IDs to point IDs
        point_ids = [abs(hash(id_)) % (2**63) for id_ in ids]
        self.client.delete(
            collection_name=self.collection_name,
            points_selector=self.models.PointIdsList(points=point_ids),
        )

    def count(self) -> int:
        """Get total vector count."""
        info = self.client.get_collection(self.collection_name)
        return info.points_count

    def clear(self) -> None:
        """Clear all vectors by recreating collection."""
        self.client.delete_collection(self.collection_name)
        self._create_collection()


class InMemoryStore(VectorStore):
    """
    In-memory vector store for testing.

    No external dependencies, pure Python + numpy.
    Good for unit tests and small-scale experiments.
    """

    def __init__(self, embedding_dim: int = 768):
        self.embedding_dim = embedding_dim
        self.vectors: dict[str, np.ndarray] = {}
        self.texts: dict[str, str] = {}
        self.metadatas: dict[str, dict] = {}

    def add(
        self,
        ids: list[str],
        embeddings: list[list[float]],
        texts: list[str],
        metadatas: list[dict],
    ) -> None:
        """Add vectors to memory."""
        for id_, emb, text, meta in zip(ids, embeddings, texts, metadatas):
            self.vectors[id_] = np.array(emb, dtype=np.float32)
            self.texts[id_] = text
            self.metadatas[id_] = meta

    def search(
        self,
        query_embedding: list[float],
        top_k: int = 10,
        filter_dict: Optional[dict] = None,
    ) -> list[SearchResult]:
        """Brute-force search (slow but correct)."""
        query = np.array(query_embedding, dtype=np.float32)

        # Normalize query for cosine similarity
        query = query / (np.linalg.norm(query) + 1e-8)

        scores = []
        for id_, vec in self.vectors.items():
            # Apply filter if provided
            if filter_dict:
                meta = self.metadatas.get(id_, {})
                if not all(meta.get(k) == v for k, v in filter_dict.items()):
                    continue

            # Cosine similarity (vectors should already be normalized)
            vec_norm = vec / (np.linalg.norm(vec) + 1e-8)
            score = float(np.dot(query, vec_norm))
            scores.append((id_, score))

        # Sort by score descending
        scores.sort(key=lambda x: x[1], reverse=True)

        results = []
        for id_, score in scores[:top_k]:
            results.append(SearchResult(
                id=id_,
                score=score,
                text=self.texts.get(id_, ""),
                metadata=self.metadatas.get(id_, {}),
            ))

        return results

    def delete(self, ids: list[str]) -> None:
        """Delete vectors by ID."""
        for id_ in ids:
            self.vectors.pop(id_, None)
            self.texts.pop(id_, None)
            self.metadatas.pop(id_, None)

    def count(self) -> int:
        """Get total vector count."""
        return len(self.vectors)

    def clear(self) -> None:
        """Clear all vectors."""
        self.vectors.clear()
        self.texts.clear()
        self.metadatas.clear()


def create_vector_store(
    backend: str = "memory",
    **kwargs,
) -> VectorStore:
    """
    Factory function to create vector store.

    Args:
        backend: "memory", "chroma", or "qdrant"
        **kwargs: Backend-specific arguments

    Returns:
        VectorStore instance
    """
    if backend == "memory":
        return InMemoryStore(**kwargs)
    elif backend == "chroma":
        return ChromaDBStore(**kwargs)
    elif backend == "qdrant":
        return QdrantStore(**kwargs)
    else:
        raise ValueError(f"Unknown backend: {backend}. Use 'memory', 'chroma', or 'qdrant'.")


if __name__ == "__main__":
    # Demo with in-memory store
    print("=== Vector Store Demo ===\n")

    store = create_vector_store("memory", embedding_dim=384)

    # Add some vectors
    ids = ["doc1", "doc2", "doc3"]
    # Fake embeddings (normally from embedder)
    embeddings = [
        [0.1] * 384,
        [0.2] * 384,
        [0.15] * 384,
    ]
    texts = [
        "EGFR mutations in lung cancer",
        "Immunotherapy for melanoma",
        "EGFR inhibitors treatment response",
    ]
    metadatas = [
        {"paper_id": "W1", "topic": "egfr"},
        {"paper_id": "W2", "topic": "immunotherapy"},
        {"paper_id": "W3", "topic": "egfr"},
    ]

    store.add(ids, embeddings, texts, metadatas)
    print(f"Added {store.count()} vectors\n")

    # Search
    query = [0.12] * 384  # Similar to doc1 and doc3
    results = store.search(query, top_k=2)

    print("Search results:")
    for r in results:
        print(f"  {r.id}: {r.score:.3f} - {r.text}")

    # Search with filter
    print("\nFiltered search (topic=egfr):")
    results = store.search(query, top_k=2, filter_dict={"topic": "egfr"})
    for r in results:
        print(f"  {r.id}: {r.score:.3f} - {r.text}")
