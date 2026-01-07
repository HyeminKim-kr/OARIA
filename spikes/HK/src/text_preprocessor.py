"""
Full Text Preprocessor for OARIA

Cleans messy PDF-extracted text:
- Removes repeated headers/footers (NIH-PA Author Manuscript, etc.)
- Detects and removes garbled/reversed text
- Cleans up whitespace and formatting
- Removes broken table data
"""

import re
from typing import Optional


# Common PDF artifacts to remove
NOISE_PATTERNS = [
    # NIH/PMC headers
    r'NIH-PA\s*Author\s*Manuscript',
    r'NIH\s*Public\s*Access',
    r'Author\s*Manuscript',
    r';?\s*available\s*in\s*PMC\s*\d{4}\s*\w+\s*\d+\.?',
    r'Published\s*in\s*final\s*edited\s*form\s*as:?',

    # Journal metadata
    r'Clin\s*Cancer\s*Res\.\s*;',  # Broken journal refs
    r'doi:\s*[\d\.\/\-a-zA-Z]+',
    r'Volume\s*no:\s*\d+',
    r'Issue\s*no:\s*\d+',
    r'Year:\s*\d{4}',
    r'Article\s*designation:.*',
    r'Running\s*heading\s*title:.*',
    r'Journal\s*name:.*',
    r'Key\s*Words:.*',

    # Page numbers and navigation
    r'Page\s*\d+',
    r'et\s*al\.\s*Page\s*\d+',
    r'\d+\s*of\s*\d+',

    # Copyright/access notices
    r'Downloaded\s*from.*',
    r'This\s*article\s*is\s*protected\s*by\s*copyright.*',
    r'©\s*\d{4}.*',
    r'EvidEncE-BasEd\s*MEdicinE',

    # Common repeated headers
    r'Correspondence\s*to:.*',
    r'Corresponding\s*author:.*',
]

# Pattern for detecting reversed/garbled text (high ratio of consonant clusters)
GARBLED_PATTERN = re.compile(r'[bcdfghjklmnpqrstvwxz]{5,}', re.IGNORECASE)


def is_garbled_line(line: str) -> bool:
    """
    Detect if a line is garbled/reversed text.
    Garbled text often has unusual consonant clusters or reversed words.
    """
    if len(line) < 5:
        return False

    # Check for reversed text patterns (words ending with common prefixes)
    reversed_patterns = ['.senil', 'ni ', 'fo ', 'eht ', 'dna ', 'htiw ']
    line_lower = line.lower()
    if any(pat in line_lower for pat in reversed_patterns):
        return True

    # Check for high ratio of consonants without vowels
    words = line.split()
    if not words:
        return False

    garbled_words = 0
    for word in words:
        if len(word) > 3:
            # Check if word has very few vowels
            vowels = sum(1 for c in word.lower() if c in 'aeiou')
            if vowels == 0 or len(word) / (vowels + 1) > 4:
                garbled_words += 1

    # If more than 40% of words look garbled, mark the line
    return garbled_words / len(words) > 0.4


def is_table_fragment(line: str) -> bool:
    """
    Detect if a line is likely a broken table fragment.
    Tables often have many numbers, special chars, or very short segments.
    """
    if len(line) < 5:
        return True

    # High ratio of numbers and special characters
    non_alpha = sum(1 for c in line if not c.isalpha() and not c.isspace())
    if len(line) > 0 and non_alpha / len(line) > 0.6:
        return True

    # Many pipe or tab characters (table separators)
    if line.count('|') > 2 or line.count('\t') > 3:
        return True

    return False


def remove_noise_patterns(text: str) -> str:
    """Remove common PDF noise patterns."""
    for pattern in NOISE_PATTERNS:
        text = re.sub(pattern, '', text, flags=re.IGNORECASE)
    return text


def clean_whitespace(text: str) -> str:
    """Normalize whitespace."""
    # Replace multiple spaces with single space
    text = re.sub(r' +', ' ', text)
    # Replace multiple newlines with double newline (paragraph break)
    text = re.sub(r'\n{3,}', '\n\n', text)
    # Remove spaces at beginning/end of lines
    lines = [line.strip() for line in text.split('\n')]
    return '\n'.join(lines)


def remove_short_lines(text: str, min_length: int = 20) -> str:
    """Remove very short lines (often noise or fragments)."""
    lines = text.split('\n')
    filtered = []

    for line in lines:
        # Keep empty lines (paragraph breaks) and lines with enough content
        if line.strip() == '' or len(line.strip()) >= min_length:
            filtered.append(line)

    return '\n'.join(filtered)


def extract_sentences(text: str) -> list[str]:
    """Extract clean sentences from text."""
    # Split on sentence boundaries
    sentences = re.split(r'(?<=[.!?])\s+', text)

    clean_sentences = []
    for sent in sentences:
        sent = sent.strip()
        # Filter out non-sentences
        if len(sent) > 30 and sent[0].isupper() and sent[-1] in '.!?':
            clean_sentences.append(sent)

    return clean_sentences


def preprocess_full_text(text: str) -> str:
    """
    Main preprocessing function for PDF-extracted text.

    Args:
        text: Raw extracted text from PDF

    Returns:
        Cleaned text suitable for RAG indexing
    """
    if not text:
        return ""

    # Step 1: Remove noise patterns
    text = remove_noise_patterns(text)

    # Step 2: Process line by line
    lines = text.split('\n')
    clean_lines = []

    for line in lines:
        line = line.strip()

        # Skip empty lines (but keep track for paragraph breaks)
        if not line:
            if clean_lines and clean_lines[-1] != '':
                clean_lines.append('')
            continue

        # Skip garbled/reversed text
        if is_garbled_line(line):
            continue

        # Skip table fragments
        if is_table_fragment(line):
            continue

        clean_lines.append(line)

    # Step 3: Join and clean whitespace
    text = '\n'.join(clean_lines)
    text = clean_whitespace(text)

    # Step 4: Remove very short lines
    text = remove_short_lines(text, min_length=15)

    return text.strip()


def preprocess_for_chunking(text: str) -> str:
    """
    Prepare text for chunking/embedding.
    More aggressive cleaning for RAG pipeline.
    """
    # First do standard preprocessing
    text = preprocess_full_text(text)

    # Additional: merge hyphenated words at line breaks
    text = re.sub(r'-\n', '', text)

    # Remove reference numbers like [1], [2,3], etc.
    text = re.sub(r'\[\d+(?:,\s*\d+)*\]', '', text)

    # Remove figure/table references
    text = re.sub(r'\((?:Fig(?:ure)?|Table)\s*\.?\s*\d+[A-Za-z]?\)', '', text, flags=re.IGNORECASE)

    return text.strip()


# === CLI for testing ===
if __name__ == "__main__":
    # Test with sample garbled text
    sample = """
    NIH-PA Author Manuscript
    NIH-PA Author Manuscript

    This is a normal sentence that should be kept in the output.

    senil llec lamyhcnesem ni ecnatsiser RFGE

    Another good paragraph with actual content that makes sense.
    The preprocessing should keep this text intact.

    05 CI binitolrE 92.4 10.2 47.1

    Conclusion: This study demonstrates important findings.
    """

    print("=== Original ===")
    print(sample)
    print("\n=== Cleaned ===")
    print(preprocess_full_text(sample))
