"""
OAR-30: PubMedBERT Embedder Implementation

Generates 768-dimensional embeddings for text chunks using PubMedBERT.
Optimized for biomedical/oncology text with batch processing support.

Author: HK
Created: 2025-12-30
Jira: OAR-30
"""

import hashlib
import json
import os
from pathlib import Path
from typing import Optional, Union
import numpy as np

# Lazy imports for optional dependencies
_sentence_transformers = None
_torch = None


def _get_sentence_transformers():
    """Lazy import sentence-transformers."""
    global _sentence_transformers
    if _sentence_transformers is None:
        try:
            import sentence_transformers
            _sentence_transformers = sentence_transformers
        except ImportError:
            raise ImportError(
                "sentence-transformers required. Install with: pip install sentence-transformers"
            )
    return _sentence_transformers


def _get_torch():
    """Lazy import torch."""
    global _torch
    if _torch is None:
        try:
            import torch
            _torch = torch
        except ImportError:
            raise ImportError("PyTorch required. Install with: pip install torch")
    return _torch


class EmbeddingCache:
    """
    Simple file-based embedding cache.

    Why caching?
    - Embedding is computationally expensive (GPU-bound)
    - Same text = same embedding (deterministic)
    - Re-running pipeline shouldn't re-embed unchanged chunks
    - Saves significant time on incremental updates
    """

    def __init__(self, cache_dir: str = ".embedding_cache"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        self._memory_cache = {}  # In-memory for hot access

    def _hash_text(self, text: str, model_name: str) -> str:
        """Create unique hash for text + model combination."""
        content = f"{model_name}:{text}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def get(self, text: str, model_name: str) -> Optional[np.ndarray]:
        """Get cached embedding if exists."""
        key = self._hash_text(text, model_name)

        # Check memory cache first
        if key in self._memory_cache:
            return self._memory_cache[key]

        # Check disk cache
        cache_file = self.cache_dir / f"{key}.npy"
        if cache_file.exists():
            embedding = np.load(cache_file)
            self._memory_cache[key] = embedding
            return embedding

        return None

    def set(self, text: str, model_name: str, embedding: np.ndarray):
        """Cache embedding to memory and disk."""
        key = self._hash_text(text, model_name)

        # Memory cache
        self._memory_cache[key] = embedding

        # Disk cache
        cache_file = self.cache_dir / f"{key}.npy"
        np.save(cache_file, embedding)

    def clear(self):
        """Clear all cached embeddings."""
        self._memory_cache.clear()
        for f in self.cache_dir.glob("*.npy"):
            f.unlink()


class PubMedBERTEmbedder:
    """
    PubMedBERT-based text embedder for biomedical text.

    Design Decisions:
    -----------------
    1. WHY PubMedBERT?
       - Pre-trained on PubMed abstracts + PMC full-text
       - Domain-specific vocabulary for medical terms
       - Better semantic understanding of oncology concepts
       - Standard 768-dimensional output

    2. WHY sentence-transformers?
       - Optimized for generating embeddings (not just classification)
       - Built-in mean pooling for sentence-level embeddings
       - Easy batch processing
       - GPU acceleration out of the box

    3. WHY lazy loading?
       - Model is ~400MB, takes 5-10 seconds to load
       - Don't load until actually needed
       - Singleton pattern prevents multiple loads

    4. Alternative models supported:
       - microsoft/BiomedNLP-PubMedBERT-base-uncased-abstract-fulltext (default)
       - pritamdeka/S-PubMedBert-MS-MARCO (fine-tuned for retrieval)
       - BAAI/bge-base-en-v1.5 (general purpose, very good)
    """

    # Model options with their characteristics
    SUPPORTED_MODELS = {
        "pubmedbert": {
            "name": "microsoft/BiomedNLP-PubMedBERT-base-uncased-abstract-fulltext",
            "dim": 768,
            "description": "Original PubMedBERT, biomedical pre-training",
        },
        "pubmedbert-retrieval": {
            "name": "pritamdeka/S-PubMedBert-MS-MARCO",
            "dim": 768,
            "description": "PubMedBERT fine-tuned for retrieval tasks",
        },
        "bge-base": {
            "name": "BAAI/bge-base-en-v1.5",
            "dim": 768,
            "description": "BGE base model, excellent general performance",
        },
        "bge-small": {
            "name": "BAAI/bge-small-en-v1.5",
            "dim": 384,
            "description": "BGE small model, faster but lower quality",
        },
    }

    def __init__(
        self,
        model_key: str = "pubmedbert",
        device: Optional[str] = None,
        use_cache: bool = True,
        cache_dir: str = ".embedding_cache",
        batch_size: int = 32,
    ):
        """
        Initialize the embedder.

        Args:
            model_key: Key from SUPPORTED_MODELS or full HuggingFace model name
            device: 'cuda', 'mps', 'cpu', or None for auto-detect
            use_cache: Whether to cache embeddings
            cache_dir: Directory for embedding cache
            batch_size: Batch size for encoding
        """
        # Resolve model name
        if model_key in self.SUPPORTED_MODELS:
            self.model_name = self.SUPPORTED_MODELS[model_key]["name"]
            self.embedding_dim = self.SUPPORTED_MODELS[model_key]["dim"]
        else:
            self.model_name = model_key
            self.embedding_dim = 768  # Assume default

        self.batch_size = batch_size
        self.use_cache = use_cache
        self._model = None  # Lazy loaded

        # Determine device
        if device:
            self.device = device
        else:
            torch = _get_torch()
            if torch.cuda.is_available():
                self.device = "cuda"
            elif torch.backends.mps.is_available():
                self.device = "mps"
            else:
                self.device = "cpu"

        # Initialize cache
        if use_cache:
            self.cache = EmbeddingCache(cache_dir)
        else:
            self.cache = None

    @property
    def model(self):
        """Lazy load the model on first access."""
        if self._model is None:
            st = _get_sentence_transformers()
            print(f"Loading embedding model: {self.model_name}")
            print(f"Device: {self.device}")
            self._model = st.SentenceTransformer(self.model_name, device=self.device)
            print(f"Model loaded. Embedding dimension: {self._model.get_sentence_embedding_dimension()}")
            self.embedding_dim = self._model.get_sentence_embedding_dimension()
        return self._model

    def embed(self, text: str) -> np.ndarray:
        """
        Embed a single text.

        Args:
            text: Text to embed

        Returns:
            768-dimensional numpy array
        """
        # Check cache
        if self.cache:
            cached = self.cache.get(text, self.model_name)
            if cached is not None:
                return cached

        # Generate embedding
        embedding = self.model.encode(
            text,
            convert_to_numpy=True,
            normalize_embeddings=True,  # L2 normalize for cosine similarity
        )

        # Cache result
        if self.cache:
            self.cache.set(text, self.model_name, embedding)

        return embedding

    def embed_batch(
        self,
        texts: list[str],
        show_progress: bool = True,
    ) -> np.ndarray:
        """
        Embed multiple texts efficiently.

        Uses batching for GPU efficiency and checks cache for each text.

        Args:
            texts: List of texts to embed
            show_progress: Show progress bar

        Returns:
            numpy array of shape (n_texts, embedding_dim)
        """
        if not texts:
            return np.array([])

        n_texts = len(texts)
        embeddings = np.zeros((n_texts, self.embedding_dim), dtype=np.float32)
        texts_to_embed = []
        indices_to_embed = []

        # Check cache for each text
        for i, text in enumerate(texts):
            if self.cache:
                cached = self.cache.get(text, self.model_name)
                if cached is not None:
                    embeddings[i] = cached
                    continue
            texts_to_embed.append(text)
            indices_to_embed.append(i)

        # Embed uncached texts
        if texts_to_embed:
            print(f"Embedding {len(texts_to_embed)} texts ({n_texts - len(texts_to_embed)} from cache)")

            new_embeddings = self.model.encode(
                texts_to_embed,
                batch_size=self.batch_size,
                convert_to_numpy=True,
                normalize_embeddings=True,
                show_progress_bar=show_progress,
            )

            # Store results and cache
            for idx, text, emb in zip(indices_to_embed, texts_to_embed, new_embeddings):
                embeddings[idx] = emb
                if self.cache:
                    self.cache.set(text, self.model_name, emb)

        return embeddings

    def embed_chunks(
        self,
        chunks: list,
        text_field: str = "text",
        show_progress: bool = True,
    ) -> list[dict]:
        """
        Embed a list of chunk objects/dicts.

        Args:
            chunks: List of Chunk objects or dicts
            text_field: Field name containing text
            show_progress: Show progress bar

        Returns:
            List of dicts with 'embedding' field added
        """
        # Extract texts
        texts = []
        for chunk in chunks:
            if hasattr(chunk, text_field):
                texts.append(getattr(chunk, text_field))
            elif isinstance(chunk, dict):
                texts.append(chunk.get(text_field, ""))
            else:
                texts.append(str(chunk))

        # Batch embed
        embeddings = self.embed_batch(texts, show_progress=show_progress)

        # Attach embeddings to chunks
        results = []
        for chunk, embedding in zip(chunks, embeddings):
            if hasattr(chunk, "to_dict"):
                result = chunk.to_dict()
            elif isinstance(chunk, dict):
                result = chunk.copy()
            else:
                result = {"text": str(chunk)}

            result["embedding"] = embedding.tolist()
            results.append(result)

        return results

    def get_stats(self) -> dict:
        """Get embedder statistics."""
        return {
            "model_name": self.model_name,
            "embedding_dim": self.embedding_dim,
            "device": self.device,
            "batch_size": self.batch_size,
            "cache_enabled": self.cache is not None,
        }


# Convenience function
def embed_texts(
    texts: list[str],
    model_key: str = "pubmedbert",
) -> np.ndarray:
    """
    Simple function to embed texts.

    Args:
        texts: List of texts to embed
        model_key: Model to use

    Returns:
        numpy array of embeddings
    """
    embedder = PubMedBERTEmbedder(model_key=model_key)
    return embedder.embed_batch(texts)


if __name__ == "__main__":
    # Demo/test
    print("=== PubMedBERT Embedder Demo ===\n")

    # Test texts
    texts = [
        "EGFR mutations are common in non-small cell lung cancer.",
        "Immunotherapy has revolutionized cancer treatment.",
        "The patient presented with metastatic breast cancer.",
    ]

    # Use smaller model for demo (faster to load)
    embedder = PubMedBERTEmbedder(model_key="bge-small", use_cache=True)

    print(f"\nEmbedder config: {embedder.get_stats()}\n")

    # Single embedding
    print("Single embedding test:")
    emb = embedder.embed(texts[0])
    print(f"  Shape: {emb.shape}")
    print(f"  First 5 values: {emb[:5]}")
    print(f"  Norm (should be ~1.0): {np.linalg.norm(emb):.4f}\n")

    # Batch embedding
    print("Batch embedding test:")
    embeddings = embedder.embed_batch(texts)
    print(f"  Shape: {embeddings.shape}")

    # Similarity test
    print("\nSimilarity matrix:")
    similarities = np.dot(embeddings, embeddings.T)
    for i, t1 in enumerate(texts):
        print(f"  Text {i}: {t1[:50]}...")
        for j, t2 in enumerate(texts):
            print(f"    vs Text {j}: {similarities[i,j]:.3f}")
