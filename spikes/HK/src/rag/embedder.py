"""
BGE-M3 Embedder for Hybrid Search

Generates both dense and sparse embeddings for hybrid retrieval:
- Dense: 1024-dim semantic vectors
- Sparse: Lexical weights for keyword matching

Author: HK
Created: 2025-12-30
Spec: F-03 Section 3.2
"""

import os
import logging
from typing import Optional
import numpy as np

from .models import Chunk, EmbeddingResult, ChunkEmbedding

logger = logging.getLogger(__name__)

# Lazy imports for heavy dependencies
_model = None
_model_name = None


def _get_model(model_name: str = "BAAI/bge-m3"):
    """Lazy load BGE-M3 model."""
    global _model, _model_name

    if _model is not None and _model_name == model_name:
        return _model

    try:
        from FlagEmbedding import BGEM3FlagModel
        logger.info(f"Loading BGE-M3 model: {model_name}")
        _model = BGEM3FlagModel(model_name, use_fp16=True)
        _model_name = model_name
        logger.info("BGE-M3 model loaded successfully")
        return _model
    except ImportError:
        raise ImportError(
            "FlagEmbedding required for BGE-M3. Install with: pip install FlagEmbedding"
        )


class BGEM3Embedder:
    """
    BGE-M3 embedder for hybrid search.

    Design Decisions:
    -----------------
    1. WHY BGE-M3?
       - M3 = Multi-lingual, Multi-functionality, Multi-granularity
       - Produces BOTH dense AND sparse vectors
       - State-of-the-art on MTEB benchmark
       - Supports Korean and English

    2. WHY Hybrid (Dense + Sparse)?
       Dense (semantic):
         - "lung cancer" matches "pulmonary malignancy"
         - Understands meaning, not just words
         - Good for conceptual queries

       Sparse (lexical):
         - "EGFR" matches exactly "EGFR"
         - Finds specific terms reliably
         - Good for technical vocabulary

       Combined:
         - Best of both worlds
         - Higher precision AND recall

    3. WHY FP16?
       - Half precision reduces memory by 50%
       - Minimal quality loss (<1%)
       - Faster inference on GPU
       - Required for larger batch sizes

    Usage:
        embedder = BGEM3Embedder()

        # Single text
        result = embedder.embed("EGFR mutations in lung cancer")
        print(result.dense_vector)  # 1024-dim
        print(result.sparse_indices)  # Token IDs
        print(result.sparse_values)   # Token weights

        # Batch
        results = embedder.embed_batch(["text1", "text2"])
    """

    def __init__(
        self,
        model_name: str = "BAAI/bge-m3",
        use_fp16: bool = True,
        device: Optional[str] = None,
    ):
        """
        Initialize embedder.

        Args:
            model_name: HuggingFace model name
            use_fp16: Use half precision (recommended)
            device: Device to use (auto-detected if None)
        """
        self.model_name = model_name
        self.use_fp16 = use_fp16
        self.device = device

        self._model = None
        self.dense_dim = 1024  # BGE-M3 output dimension

    @property
    def model(self):
        """Lazy load model on first use."""
        if self._model is None:
            self._model = _get_model(self.model_name)
        return self._model

    def embed(
        self,
        text: str,
        return_sparse: bool = True,
    ) -> EmbeddingResult:
        """
        Embed a single text.

        Args:
            text: Text to embed
            return_sparse: Whether to compute sparse embeddings

        Returns:
            EmbeddingResult with dense and optional sparse vectors
        """
        results = self.embed_batch([text], return_sparse=return_sparse)
        return results[0]

    def embed_batch(
        self,
        texts: list[str],
        return_sparse: bool = True,
        show_progress: bool = False,
    ) -> list[EmbeddingResult]:
        """
        Embed multiple texts efficiently.

        Args:
            texts: List of texts to embed
            return_sparse: Whether to compute sparse embeddings
            show_progress: Show progress bar

        Returns:
            List of EmbeddingResult objects
        """
        if not texts:
            return []

        # Encode with BGE-M3
        output = self.model.encode(
            texts,
            return_dense=True,
            return_sparse=return_sparse,
            return_colbert_vecs=False,  # ColBERT not needed for our use case
        )

        results = []
        dense_vecs = output["dense_vecs"]

        for i, text in enumerate(texts):
            # Dense vector
            dense = dense_vecs[i].tolist()

            # Sparse vector (if requested)
            sparse_indices = None
            sparse_values = None

            if return_sparse and "lexical_weights" in output:
                sparse_dict = output["lexical_weights"][i]
                if sparse_dict:
                    sparse_indices = list(sparse_dict.keys())
                    sparse_values = list(sparse_dict.values())

            results.append(EmbeddingResult(
                text=text,
                dense_vector=dense,
                sparse_indices=sparse_indices,
                sparse_values=sparse_values,
                model=self.model_name,
            ))

        return results

    def embed_chunks(
        self,
        chunks: list[Chunk],
        return_sparse: bool = True,
        batch_size: int = 32,
    ) -> list[ChunkEmbedding]:
        """
        Embed chunks with their metadata preserved.

        Args:
            chunks: List of Chunk objects
            return_sparse: Whether to compute sparse embeddings
            batch_size: Batch size for encoding

        Returns:
            List of ChunkEmbedding objects
        """
        if not chunks:
            return []

        results = []
        texts = [chunk.text for chunk in chunks]

        # Process in batches
        for i in range(0, len(texts), batch_size):
            batch_texts = texts[i:i + batch_size]
            batch_chunks = chunks[i:i + batch_size]

            embeddings = self.embed_batch(batch_texts, return_sparse=return_sparse)

            for chunk, emb in zip(batch_chunks, embeddings):
                results.append(ChunkEmbedding(
                    chunk=chunk,
                    dense_vector=emb.dense_vector,
                    sparse_indices=emb.sparse_indices,
                    sparse_values=emb.sparse_values,
                ))

        return results

    def embed_query(self, query: str) -> tuple[list[float], tuple[list[int], list[float]]]:
        """
        Embed a query for search.

        Convenience method that returns vectors in the format
        expected by Qdrant hybrid search.

        Args:
            query: Search query

        Returns:
            Tuple of (dense_vector, (sparse_indices, sparse_values))
        """
        result = self.embed(query, return_sparse=True)
        sparse = (result.sparse_indices or [], result.sparse_values or [])
        return result.dense_vector, sparse

    def get_stats(self) -> dict:
        """Get embedder statistics."""
        return {
            "model": self.model_name,
            "dense_dim": self.dense_dim,
            "use_fp16": self.use_fp16,
            "loaded": self._model is not None,
        }


# Convenience function
def embed_texts(
    texts: list[str],
    return_sparse: bool = True,
) -> list[EmbeddingResult]:
    """Quick function to embed texts."""
    embedder = BGEM3Embedder()
    return embedder.embed_batch(texts, return_sparse=return_sparse)


if __name__ == "__main__":
    print("=== BGE-M3 Embedder Demo ===\n")

    # Check if FlagEmbedding is available
    try:
        from FlagEmbedding import BGEM3FlagModel
        has_flag = True
    except ImportError:
        has_flag = False
        print("FlagEmbedding not installed. Showing structure only.\n")

    if has_flag:
        embedder = BGEM3Embedder()

        # Single embedding
        text = "EGFR mutations predict response to tyrosine kinase inhibitors"
        result = embedder.embed(text)

        print(f"Text: {text[:50]}...")
        print(f"Dense vector: {len(result.dense_vector)} dimensions")
        print(f"  First 5 values: {result.dense_vector[:5]}")

        if result.sparse_indices:
            print(f"Sparse vector: {len(result.sparse_indices)} non-zero entries")
            print(f"  First 5 indices: {result.sparse_indices[:5]}")
            print(f"  First 5 values: {result.sparse_values[:5]}")

        # Query embedding
        query = "lung cancer treatment"
        dense, (indices, values) = embedder.embed_query(query)
        print(f"\nQuery '{query}':")
        print(f"  Dense: {len(dense)} dims")
        print(f"  Sparse: {len(indices)} entries")

    else:
        print("Structure overview:")
        print("""
BGEM3Embedder:
  - embed(text) -> EmbeddingResult
  - embed_batch(texts) -> list[EmbeddingResult]
  - embed_chunks(chunks) -> list[ChunkEmbedding]
  - embed_query(query) -> (dense_vec, (sparse_indices, sparse_values))

EmbeddingResult:
  - dense_vector: list[float]  # 1024 dimensions
  - sparse_indices: list[int]  # Token IDs
  - sparse_values: list[float] # Token weights
        """)
