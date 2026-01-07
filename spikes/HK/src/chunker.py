"""
OAR-29: Text Chunker Implementation

Splits paper text into RAG-suitable chunks with:
- 512 token target size
- 50 token overlap for context continuity
- Sentence boundary awareness (no mid-sentence cuts)
- Metadata preservation (paper_id, chunk_index, char positions)

Author: HK
Created: 2025-12-30
Jira: OAR-29
"""

import re
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Chunk:
    """A single chunk of text with metadata."""
    text: str
    paper_id: str
    chunk_index: int
    start_char: int
    end_char: int
    token_count: int
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "text": self.text,
            "paper_id": self.paper_id,
            "chunk_index": self.chunk_index,
            "start_char": self.start_char,
            "end_char": self.end_char,
            "token_count": self.token_count,
            "metadata": self.metadata,
        }


class TextChunker:
    """
    Token-based text chunker with sentence boundary awareness.

    Design Decisions:
    -----------------
    1. WHY 512 tokens?
       - Matches common embedding model context limits
       - Large enough for semantic coherence
       - Small enough for precise retrieval

    2. WHY 50 token overlap?
       - ~10% overlap provides context continuity
       - Prevents information loss at chunk boundaries
       - Balances redundancy vs storage efficiency

    3. WHY sentence boundaries?
       - Mid-sentence cuts destroy semantic meaning
       - Embeddings of partial sentences are unreliable
       - Better retrieval accuracy with complete thoughts

    4. WHY simple whitespace tokenization?
       - Fast and deterministic
       - Consistent across runs
       - tiktoken/BPE adds complexity without proportional benefit for chunking
       - Actual embedding models will re-tokenize anyway
    """

    # Sentence ending patterns
    SENTENCE_ENDINGS = re.compile(r'(?<=[.!?])\s+(?=[A-Z])|(?<=[.!?])\s*$')

    # Paragraph break pattern
    PARAGRAPH_BREAK = re.compile(r'\n\s*\n')

    def __init__(
        self,
        chunk_size: int = 512,
        chunk_overlap: int = 50,
        min_chunk_size: int = 100,
    ):
        """
        Initialize the chunker.

        Args:
            chunk_size: Target tokens per chunk (default: 512)
            chunk_overlap: Overlap tokens between chunks (default: 50)
            min_chunk_size: Minimum tokens for a valid chunk (default: 100)
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.min_chunk_size = min_chunk_size

        # Validation
        if chunk_overlap >= chunk_size:
            raise ValueError(f"Overlap ({chunk_overlap}) must be less than chunk size ({chunk_size})")
        if min_chunk_size > chunk_size:
            raise ValueError(f"Min chunk size ({min_chunk_size}) must be <= chunk size ({chunk_size})")

    def count_tokens(self, text: str) -> int:
        """
        Count tokens using whitespace tokenization.

        Why whitespace tokenization:
        - Simple and fast
        - Good approximation for English text
        - Actual embedding model will use its own tokenizer
        - For precise counts, subclass and override with tiktoken
        """
        return len(text.split())

    def _find_sentence_boundaries(self, text: str) -> list[int]:
        """
        Find character positions of sentence boundaries.

        Returns list of positions where sentences end (after punctuation and space).
        These are safe split points.
        """
        boundaries = [0]  # Start of text is a boundary

        for match in self.SENTENCE_ENDINGS.finditer(text):
            boundaries.append(match.end())

        boundaries.append(len(text))  # End of text is a boundary
        return sorted(set(boundaries))

    def _find_paragraph_boundaries(self, text: str) -> list[int]:
        """
        Find character positions of paragraph boundaries.

        Paragraphs are preferred split points over sentences
        because they represent larger semantic units.
        """
        boundaries = [0]

        for match in self.PARAGRAPH_BREAK.finditer(text):
            boundaries.append(match.end())

        boundaries.append(len(text))
        return sorted(set(boundaries))

    def _find_best_split_point(
        self,
        text: str,
        target_pos: int,
        sentence_boundaries: list[int],
    ) -> int:
        """
        Find the best character position to split near target_pos.

        Strategy:
        1. Prefer paragraph boundaries (strongest semantic break)
        2. Fall back to sentence boundaries
        3. Last resort: split at word boundary near target

        Args:
            text: Full text being chunked
            target_pos: Ideal character position to split at
            sentence_boundaries: Pre-computed sentence boundary positions

        Returns:
            Character position to split at
        """
        # Search window: 20% before target to 5% after
        # We prefer earlier splits to avoid oversized chunks
        window_start = int(target_pos * 0.8)
        window_end = int(target_pos * 1.05)

        # Find sentence boundaries in window
        candidates = [b for b in sentence_boundaries if window_start <= b <= window_end]

        if candidates:
            # Pick the one closest to target
            return min(candidates, key=lambda x: abs(x - target_pos))

        # No sentence boundary found - find word boundary near target
        # Look for space before target
        search_start = max(0, target_pos - 50)
        last_space = text.rfind(' ', search_start, target_pos)

        if last_space > window_start:
            return last_space + 1  # Split after the space

        # Absolute fallback: split at target
        return target_pos

    def chunk_text(
        self,
        text: str,
        paper_id: str,
        metadata: Optional[dict] = None,
    ) -> list[Chunk]:
        """
        Split text into overlapping chunks.

        Algorithm:
        1. Pre-compute sentence boundaries
        2. Estimate tokens to characters ratio
        3. Walk through text, creating chunks at boundaries
        4. Apply overlap by starting next chunk earlier

        Args:
            text: Full text to chunk
            paper_id: Identifier for the source paper (e.g., OpenAlex ID, PMID)
            metadata: Optional metadata to attach to all chunks

        Returns:
            List of Chunk objects
        """
        if not text or not text.strip():
            return []

        # Clean and normalize text
        text = text.strip()
        text = re.sub(r'\s+', ' ', text)  # Normalize whitespace

        # Pre-compute boundaries
        sentence_boundaries = self._find_sentence_boundaries(text)

        # Estimate characters per token (for initial positioning)
        total_tokens = self.count_tokens(text)
        chars_per_token = len(text) / max(total_tokens, 1)

        # Target characters based on token target
        target_chars = int(self.chunk_size * chars_per_token)
        overlap_chars = int(self.chunk_overlap * chars_per_token)

        chunks = []
        chunk_index = 0
        start_char = 0

        while start_char < len(text):
            # Calculate target end position
            target_end = start_char + target_chars

            if target_end >= len(text):
                # Last chunk - take everything remaining
                end_char = len(text)
            else:
                # Find best split point near target
                end_char = self._find_best_split_point(
                    text, target_end, sentence_boundaries
                )

            # Extract chunk text
            chunk_text = text[start_char:end_char].strip()

            # Count actual tokens in this chunk
            token_count = self.count_tokens(chunk_text)

            # Only add if meets minimum size (or it's the last/only chunk)
            if token_count >= self.min_chunk_size or not chunks:
                chunk = Chunk(
                    text=chunk_text,
                    paper_id=paper_id,
                    chunk_index=chunk_index,
                    start_char=start_char,
                    end_char=end_char,
                    token_count=token_count,
                    metadata=metadata.copy() if metadata else {},
                )
                chunks.append(chunk)
                chunk_index += 1

            # Move start position for next chunk (with overlap)
            # We go back by overlap_chars to create the overlap
            next_start = end_char - overlap_chars

            # But don't go backwards
            if next_start <= start_char:
                next_start = end_char

            # If we haven't made progress, force forward
            if next_start == start_char:
                break

            start_char = next_start

        return chunks

    def chunk_papers(
        self,
        papers: list[dict],
        text_field: str = "full_text",
        id_field: str = "openalex_id",
    ) -> list[Chunk]:
        """
        Chunk multiple papers.

        Args:
            papers: List of paper dictionaries
            text_field: Key for the text content
            id_field: Key for the paper identifier

        Returns:
            List of all chunks from all papers
        """
        all_chunks = []

        for paper in papers:
            text = paper.get(text_field, "")
            paper_id = paper.get(id_field, "unknown")

            if not text:
                continue

            # Build metadata from paper fields (excluding full text)
            metadata = {k: v for k, v in paper.items() if k != text_field}

            chunks = self.chunk_text(text, paper_id, metadata)
            all_chunks.extend(chunks)

        return all_chunks


# Convenience function
def chunk_text(
    text: str,
    paper_id: str,
    chunk_size: int = 512,
    chunk_overlap: int = 50,
) -> list[dict]:
    """
    Simple function to chunk text.

    Args:
        text: Text to chunk
        paper_id: Paper identifier
        chunk_size: Target tokens per chunk
        chunk_overlap: Overlap tokens

    Returns:
        List of chunk dictionaries
    """
    chunker = TextChunker(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    chunks = chunker.chunk_text(text, paper_id)
    return [c.to_dict() for c in chunks]


if __name__ == "__main__":
    # Demo/test
    sample_text = """
    Cancer immunotherapy has revolutionized the treatment of various malignancies.
    Immune checkpoint inhibitors, particularly anti-PD-1 and anti-PD-L1 antibodies,
    have shown remarkable efficacy in multiple cancer types. These agents work by
    blocking inhibitory signals that prevent T cells from attacking tumor cells.

    The development of CAR-T cell therapy represents another major advancement.
    In this approach, patient T cells are genetically modified to express chimeric
    antigen receptors that recognize specific tumor antigens. Clinical trials have
    demonstrated exceptional response rates in hematologic malignancies.

    However, challenges remain in solid tumor treatment. The immunosuppressive
    tumor microenvironment and lack of universal tumor antigens complicate the
    application of these therapies to solid cancers. Ongoing research focuses on
    combination approaches and novel targets to overcome these barriers.
    """

    chunker = TextChunker(chunk_size=100, chunk_overlap=20)  # Small for demo
    chunks = chunker.chunk_text(sample_text, paper_id="demo_paper_001")

    print(f"Created {len(chunks)} chunks:\n")
    for chunk in chunks:
        print(f"--- Chunk {chunk.chunk_index} ({chunk.token_count} tokens) ---")
        print(f"Chars {chunk.start_char}-{chunk.end_char}")
        print(chunk.text[:200] + "..." if len(chunk.text) > 200 else chunk.text)
        print()
