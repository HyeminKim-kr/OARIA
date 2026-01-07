"""
Text Chunker for RAG Pipeline

Splits paper text into overlapping chunks optimized for:
- Embedding quality (512 tokens)
- Context preservation (50 token overlap)
- Sentence boundary awareness

Author: HK
Created: 2025-12-30
Spec: F-03 Section 3.1
"""

import re
from typing import Optional
from .models import Chunk


class TextChunker:
    """
    Token-based text chunker with sentence boundary awareness.

    Design Decisions:
    -----------------
    1. WHY 512 tokens?
       - Matches BGE-M3's optimal input size
       - Balances context vs specificity
       - Fits in most model context windows

    2. WHY 50 token overlap?
       - Prevents losing context at chunk boundaries
       - ~10% overlap is industry standard
       - Helps with sentence-spanning queries

    3. WHY sentence boundaries?
       - Mid-sentence cuts harm retrieval quality
       - Better semantic coherence
       - More natural reading when displayed
    """

    # Approximate tokens per word (English)
    TOKENS_PER_WORD = 1.3

    def __init__(
        self,
        chunk_size: int = 512,
        chunk_overlap: int = 50,
        min_chunk_size: int = 100,
    ):
        """
        Initialize chunker.

        Args:
            chunk_size: Target chunk size in tokens (default 512)
            chunk_overlap: Overlap between chunks in tokens (default 50)
            min_chunk_size: Minimum chunk size to keep (default 100)
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.min_chunk_size = min_chunk_size

        # Convert to words for processing
        self.words_per_chunk = int(chunk_size / self.TOKENS_PER_WORD)
        self.overlap_words = int(chunk_overlap / self.TOKENS_PER_WORD)
        self.min_words = int(min_chunk_size / self.TOKENS_PER_WORD)

    def _split_into_sentences(self, text: str) -> list[str]:
        """Split text into sentences."""
        # Pattern: split on . ! ? followed by space and capital letter
        pattern = r'(?<=[.!?])\s+(?=[A-Z가-힣])'
        sentences = re.split(pattern, text)
        return [s.strip() for s in sentences if s.strip()]

    def _estimate_tokens(self, text: str) -> int:
        """Estimate token count for text."""
        words = len(text.split())
        return int(words * self.TOKENS_PER_WORD)

    def chunk_text(
        self,
        text: str,
        paper_id: str,
        metadata: Optional[dict] = None,
    ) -> list[Chunk]:
        """
        Split text into overlapping chunks.

        Args:
            text: Full text to chunk
            paper_id: Paper identifier for chunk IDs
            metadata: Optional metadata to attach to chunks

        Returns:
            List of Chunk objects
        """
        if not text or not text.strip():
            return []

        metadata = metadata or {}
        chunks = []

        # Split into sentences for boundary awareness
        sentences = self._split_into_sentences(text)

        if not sentences:
            return []

        current_chunk = []
        current_words = 0
        char_pos = 0

        for sentence in sentences:
            sentence_words = len(sentence.split())

            # If adding this sentence exceeds limit, finalize current chunk
            if current_words + sentence_words > self.words_per_chunk and current_chunk:
                chunk_text = " ".join(current_chunk)
                chunk_tokens = self._estimate_tokens(chunk_text)

                if chunk_tokens >= self.min_chunk_size:
                    chunks.append(Chunk(
                        chunk_id=f"{paper_id}_chunk_{len(chunks)}",
                        paper_id=paper_id,
                        chunk_index=len(chunks),
                        text=chunk_text,
                        token_count=chunk_tokens,
                        char_start=char_pos,
                        char_end=char_pos + len(chunk_text),
                        metadata=metadata,
                    ))

                # Keep overlap for next chunk
                overlap_text = []
                overlap_words = 0
                for s in reversed(current_chunk):
                    s_words = len(s.split())
                    if overlap_words + s_words <= self.overlap_words:
                        overlap_text.insert(0, s)
                        overlap_words += s_words
                    else:
                        break

                current_chunk = overlap_text
                current_words = overlap_words
                char_pos += len(chunk_text) - len(" ".join(overlap_text))

            current_chunk.append(sentence)
            current_words += sentence_words

        # Don't forget the last chunk
        if current_chunk:
            chunk_text = " ".join(current_chunk)
            chunk_tokens = self._estimate_tokens(chunk_text)

            if chunk_tokens >= self.min_chunk_size:
                chunks.append(Chunk(
                    chunk_id=f"{paper_id}_chunk_{len(chunks)}",
                    paper_id=paper_id,
                    chunk_index=len(chunks),
                    text=chunk_text,
                    token_count=chunk_tokens,
                    char_start=char_pos,
                    char_end=char_pos + len(chunk_text),
                    metadata=metadata,
                ))

        return chunks

    def chunk_full_text_paper(
        self,
        paper_id: str,
        title: str,
        full_text: str,
        metadata: Optional[dict] = None,
    ) -> list[Chunk]:
        """
        Chunk a full-text paper (REQUIRED: full_text must be provided).

        This is the primary method for OARIA RAG indexing.
        Full-text content is MANDATORY for high-quality research retrieval.

        Args:
            paper_id: Paper identifier (OpenAlex ID, DOI, or arXiv ID)
            title: Paper title
            full_text: Full paper text (REQUIRED, must be >500 chars)
            metadata: Optional metadata

        Returns:
            List of Chunk objects (empty if full_text is insufficient)
        """
        if not full_text or len(full_text) < 500:
            return []

        content = f"{title}\n\n{full_text}"
        return self.chunk_text(content, paper_id, metadata)

    def chunk_paper(
        self,
        paper_id: str,
        title: str,
        abstract: str,
        metadata: Optional[dict] = None,
        full_text: Optional[str] = None,
    ) -> list[Chunk]:
        """
        DEPRECATED: Use chunk_full_text_paper() instead.

        This method is kept for backward compatibility only.
        OARIA requires full-text papers for indexing.
        """
        # Redirect to full-text method if available
        if full_text and len(full_text) > 500:
            return self.chunk_full_text_paper(paper_id, title, full_text, metadata)

        # Legacy fallback (not recommended for OARIA)
        if abstract:
            content = f"{title}\n\n{abstract}"
        else:
            content = title

        return self.chunk_text(content, paper_id, metadata)

    def chunk_papers(
        self,
        papers: list[dict],
    ) -> list[Chunk]:
        """
        Chunk multiple full-text papers.

        REQUIRES full_text field - papers without full-text are skipped.

        Args:
            papers: List of paper dicts with 'openalex_id', 'title', 'full_text'

        Returns:
            List of all chunks from papers WITH full-text only
        """
        all_chunks = []
        skipped = 0

        for paper in papers:
            full_text = paper.get("full_text")

            # STRICT: Skip papers without full-text
            if not full_text or len(full_text) < 500:
                skipped += 1
                continue

            paper_id = paper.get("openalex_id", paper.get("id", "unknown"))
            title = paper.get("title", "")

            metadata = {
                "title": title,
                "doi": paper.get("doi"),
                "pmid": paper.get("pmid"),
                "journal": paper.get("journal"),
                "publication_date": paper.get("publication_date"),
                "authors": paper.get("authors", []),
            }

            chunks = self.chunk_full_text_paper(
                paper_id, title, full_text, metadata
            )
            all_chunks.extend(chunks)

        if skipped > 0:
            import logging
            logging.getLogger(__name__).info(
                f"Skipped {skipped} papers without full-text"
            )

        return all_chunks


# Convenience function
def chunk_text(
    text: str,
    paper_id: str = "unknown",
    chunk_size: int = 512,
    chunk_overlap: int = 50,
) -> list[Chunk]:
    """Quick function to chunk text."""
    chunker = TextChunker(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    return chunker.chunk_text(text, paper_id)


if __name__ == "__main__":
    print("=== Text Chunker Demo ===\n")

    sample_text = """
    EGFR mutations are found in approximately 15% of non-small cell lung cancer patients
    in Western populations and up to 50% in Asian populations. These mutations predict
    sensitivity to EGFR tyrosine kinase inhibitors such as erlotinib and gefitinib.

    First-generation EGFR TKIs have shown response rates of 60-70% in EGFR-mutant patients.
    However, acquired resistance typically develops within 9-13 months, often through the
    T790M secondary mutation.

    Third-generation TKIs like osimertinib can overcome T790M resistance and have shown
    superior overall survival compared to first-generation TKIs in the FLAURA trial.
    """

    chunker = TextChunker(chunk_size=100, chunk_overlap=20)  # Smaller for demo
    chunks = chunker.chunk_text(sample_text.strip(), "W12345")

    print(f"Created {len(chunks)} chunks:\n")
    for chunk in chunks:
        print(f"[{chunk.chunk_id}] ~{chunk.token_count} tokens")
        print(f"  {chunk.text[:80]}...")
        print()
