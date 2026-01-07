"""
OAR-35: Citation Linker Implementation

Extracts citations from generated answers and maps them to paper metadata.
Enables verification of claims and links to source papers.

Author: HK
Created: 2025-12-30
Jira: OAR-35
"""

import re
from dataclasses import dataclass
from typing import Optional


@dataclass
class LinkedCitation:
    """
    A citation linked to its source paper.

    Contains all information needed to render a clickable citation
    with paper details.
    """
    citation_number: int      # [1], [2], etc.
    paper_id: str            # OpenAlex ID or other identifier
    paper_title: Optional[str] = None
    doi: Optional[str] = None
    pmid: Optional[str] = None
    journal: Optional[str] = None
    publication_date: Optional[str] = None
    text_snippet: str = ""   # The relevant text from this source
    relevance_score: float = 0.0
    url: Optional[str] = None  # Link to paper

    def to_dict(self) -> dict:
        return {
            "citation_number": self.citation_number,
            "paper_id": self.paper_id,
            "paper_title": self.paper_title,
            "doi": self.doi,
            "pmid": self.pmid,
            "journal": self.journal,
            "publication_date": self.publication_date,
            "text_snippet": self.text_snippet,
            "relevance_score": self.relevance_score,
            "url": self.url,
        }


@dataclass
class CitationValidation:
    """Result of validating citations in generated text."""
    total_citations: int
    valid_citations: list[int]
    invalid_citations: list[int]  # Citations not in source list
    unused_sources: list[int]     # Sources not cited
    is_valid: bool
    error_message: Optional[str] = None


class CitationLinker:
    """
    Links citations in generated text to source paper metadata.

    Design Decisions:
    -----------------
    1. WHY citation linking?
       - Enables users to verify claims by checking sources
       - Provides click-through to original papers
       - Detects hallucinated citations (numbers not in sources)
       - Improves transparency and trust

    2. WHY [1], [2] format (not [PMID:...])?
       - Not all papers have PMIDs (OpenAlex includes many sources)
       - Simpler format, easier for LLM to follow
       - Maps to source position in context
       - Citation Linker resolves to actual IDs

    3. WHY validation?
       - Catch citations to non-existent sources (hallucination)
       - Identify sources that weren't used (potential quality issue)
       - Ensure every claim has proper backing

    4. WHY URL generation?
       - Enable one-click access to papers
       - Support DOI resolver, PubMed, OpenAlex links
       - Improve user experience
    """

    # Citation pattern: [1], [2], [1][2], etc.
    CITATION_PATTERN = re.compile(r'\[(\d+)\]')

    def __init__(self):
        """Initialize the citation linker."""
        pass

    def extract_citations(self, text: str) -> list[int]:
        """
        Extract all citation numbers from text.

        Args:
            text: Generated text containing [1], [2], etc.

        Returns:
            Sorted list of unique citation numbers
        """
        matches = self.CITATION_PATTERN.findall(text)
        return sorted(set(int(m) for m in matches))

    def extract_citation_positions(self, text: str) -> list[tuple[int, int, int]]:
        """
        Extract citation positions for highlighting.

        Args:
            text: Generated text

        Returns:
            List of (citation_number, start_pos, end_pos)
        """
        positions = []
        for match in self.CITATION_PATTERN.finditer(text):
            num = int(match.group(1))
            positions.append((num, match.start(), match.end()))
        return positions

    def _build_paper_url(
        self,
        paper_id: str,
        doi: Optional[str],
        pmid: Optional[str],
    ) -> Optional[str]:
        """
        Build URL to paper.

        Priority:
        1. DOI (most universal)
        2. PubMed (if PMID available)
        3. OpenAlex (fallback)
        """
        if doi:
            # Clean DOI (remove https://doi.org/ prefix if present)
            clean_doi = doi.replace("https://doi.org/", "").replace("http://doi.org/", "")
            return f"https://doi.org/{clean_doi}"

        if pmid:
            clean_pmid = pmid.replace("https://pubmed.ncbi.nlm.nih.gov/", "").strip("/")
            return f"https://pubmed.ncbi.nlm.nih.gov/{clean_pmid}/"

        if paper_id and paper_id.startswith("W"):
            # OpenAlex work ID
            return f"https://openalex.org/{paper_id}"

        return None

    def link_citations(
        self,
        generated_text: str,
        sources: list[dict],
    ) -> list[LinkedCitation]:
        """
        Link citations in text to source metadata.

        Args:
            generated_text: LLM-generated answer with [1], [2], etc.
            sources: List of source dicts (from generator.context_sources)

        Returns:
            List of LinkedCitation objects for each citation used
        """
        # Extract citations from text
        citation_numbers = self.extract_citations(generated_text)

        linked = []
        for num in citation_numbers:
            # Find corresponding source (1-indexed)
            source_idx = num - 1

            if 0 <= source_idx < len(sources):
                source = sources[source_idx]

                # Extract metadata
                metadata = source.get("metadata", {})

                linked.append(LinkedCitation(
                    citation_number=num,
                    paper_id=source.get("paper_id", metadata.get("paper_id", f"source_{num}")),
                    paper_title=metadata.get("title"),
                    doi=metadata.get("doi"),
                    pmid=metadata.get("pmid"),
                    journal=metadata.get("journal"),
                    publication_date=metadata.get("publication_date"),
                    text_snippet=source.get("text_preview", source.get("text", ""))[:300],
                    relevance_score=source.get("score", source.get("rerank_score", 0)),
                    url=self._build_paper_url(
                        source.get("paper_id", ""),
                        metadata.get("doi"),
                        metadata.get("pmid"),
                    ),
                ))
            else:
                # Citation to non-existent source (hallucination)
                linked.append(LinkedCitation(
                    citation_number=num,
                    paper_id=f"INVALID_{num}",
                    text_snippet="[Citation not found in sources]",
                ))

        return linked

    def validate_citations(
        self,
        generated_text: str,
        sources: list[dict],
    ) -> CitationValidation:
        """
        Validate that citations match available sources.

        Checks:
        1. All citation numbers refer to existing sources
        2. Identifies unused sources (potential quality issue)

        Args:
            generated_text: LLM-generated answer
            sources: List of source dicts

        Returns:
            CitationValidation with validation results
        """
        # Extract citations
        citation_numbers = self.extract_citations(generated_text)
        num_sources = len(sources)

        # Check validity
        valid = []
        invalid = []

        for num in citation_numbers:
            if 1 <= num <= num_sources:
                valid.append(num)
            else:
                invalid.append(num)

        # Find unused sources
        used_indices = set(valid)
        unused = [i for i in range(1, num_sources + 1) if i not in used_indices]

        # Determine overall validity
        is_valid = len(invalid) == 0
        error_message = None

        if invalid:
            error_message = f"Invalid citations: {invalid}. Only {num_sources} sources available."

        return CitationValidation(
            total_citations=len(citation_numbers),
            valid_citations=valid,
            invalid_citations=invalid,
            unused_sources=unused,
            is_valid=is_valid,
            error_message=error_message,
        )

    def format_citations_as_footnotes(
        self,
        linked_citations: list[LinkedCitation],
    ) -> str:
        """
        Format linked citations as footnote-style references.

        Args:
            linked_citations: List of LinkedCitation objects

        Returns:
            Formatted reference string
        """
        lines = ["\n---\n## References\n"]

        for cite in sorted(linked_citations, key=lambda x: x.citation_number):
            line = f"[{cite.citation_number}] "

            if cite.paper_title:
                line += f"**{cite.paper_title}**. "

            if cite.journal:
                line += f"_{cite.journal}_"

            if cite.publication_date:
                line += f" ({cite.publication_date})"

            if cite.url:
                line += f" [Link]({cite.url})"
            elif cite.doi:
                line += f" DOI: {cite.doi}"

            lines.append(line)

        return "\n".join(lines)

    def format_citations_as_html(
        self,
        linked_citations: list[LinkedCitation],
    ) -> str:
        """
        Format linked citations as HTML for web display.

        Args:
            linked_citations: List of LinkedCitation objects

        Returns:
            HTML string for citation list
        """
        html_parts = ['<div class="citation-list"><h3>References</h3><ol>']

        for cite in sorted(linked_citations, key=lambda x: x.citation_number):
            html_parts.append(f'<li id="cite-{cite.citation_number}">')

            if cite.paper_title:
                html_parts.append(f'<strong>{cite.paper_title}</strong>')

            if cite.journal:
                html_parts.append(f' <em>{cite.journal}</em>')

            if cite.publication_date:
                html_parts.append(f' ({cite.publication_date})')

            if cite.url:
                html_parts.append(f' <a href="{cite.url}" target="_blank">[Link]</a>')

            html_parts.append('</li>')

        html_parts.append('</ol></div>')
        return ''.join(html_parts)

    def enhance_text_with_links(
        self,
        text: str,
        linked_citations: list[LinkedCitation],
    ) -> str:
        """
        Replace [1], [2] in text with clickable links (HTML).

        Args:
            text: Original text with [1], [2], etc.
            linked_citations: Linked citation data

        Returns:
            HTML text with citation links
        """
        # Build lookup
        cite_lookup = {c.citation_number: c for c in linked_citations}

        def replace_citation(match):
            num = int(match.group(1))
            cite = cite_lookup.get(num)

            if cite and cite.url:
                title = cite.paper_title or f"Source {num}"
                return f'<a href="{cite.url}" title="{title}" class="citation-link">[{num}]</a>'
            elif cite and cite.paper_id.startswith("INVALID"):
                return f'<span class="citation-invalid">[{num}]</span>'
            else:
                return f'<a href="#cite-{num}" class="citation-link">[{num}]</a>'

        return self.CITATION_PATTERN.sub(replace_citation, text)


# Convenience functions
def link_and_validate_citations(
    generated_text: str,
    sources: list[dict],
) -> tuple[list[LinkedCitation], CitationValidation]:
    """
    Link and validate citations in one call.

    Args:
        generated_text: LLM output
        sources: Source documents

    Returns:
        Tuple of (linked_citations, validation_result)
    """
    linker = CitationLinker()
    linked = linker.link_citations(generated_text, sources)
    validation = linker.validate_citations(generated_text, sources)
    return linked, validation


if __name__ == "__main__":
    print("=== Citation Linker Demo ===\n")

    # Sample generated text
    generated_text = """
    EGFR inhibitors have shown significant efficacy in treating non-small cell lung cancer (NSCLC).

    First-generation EGFR TKIs such as erlotinib and gefitinib demonstrate response rates of
    60-70% in EGFR-mutant patients [1]. These mutations are found in approximately 15% of
    Western NSCLC patients and up to 50% in Asian populations [2].

    Third-generation TKIs like osimertinib address resistance mechanisms and showed superior
    survival in the FLAURA trial [3]. However, combination approaches may be needed for
    optimal outcomes [1][3].

    Some studies suggest additional biomarkers may predict response [4].
    """

    # Sample sources (as would come from generator)
    sources = [
        {
            "number": 1,
            "paper_id": "W2963284341",
            "score": 0.92,
            "text_preview": "Erlotinib and gefitinib are first-generation EGFR TKIs...",
            "metadata": {
                "title": "EGFR TKIs in NSCLC: A Comprehensive Review",
                "doi": "10.1016/j.lungcan.2020.01.001",
                "journal": "Lung Cancer",
                "publication_date": "2020-03",
            }
        },
        {
            "number": 2,
            "paper_id": "W2891234567",
            "score": 0.88,
            "text_preview": "EGFR mutations are found in 15% of Western populations...",
            "metadata": {
                "title": "Epidemiology of EGFR Mutations",
                "doi": "10.1200/JCO.2019.12345",
                "pmid": "31234567",
                "journal": "Journal of Clinical Oncology",
                "publication_date": "2019-06",
            }
        },
        {
            "number": 3,
            "paper_id": "W3012345678",
            "score": 0.85,
            "text_preview": "Osimertinib in the FLAURA trial showed superior OS...",
            "metadata": {
                "title": "FLAURA Trial Results",
                "doi": "10.1056/NEJMoa1913662",
                "journal": "NEJM",
                "publication_date": "2020-01",
            }
        },
    ]

    linker = CitationLinker()

    # Extract citations
    citations = linker.extract_citations(generated_text)
    print(f"Citations found: {citations}\n")

    # Validate
    validation = linker.validate_citations(generated_text, sources)
    print("Validation:")
    print(f"  Valid citations: {validation.valid_citations}")
    print(f"  Invalid citations: {validation.invalid_citations}")
    print(f"  Unused sources: {validation.unused_sources}")
    print(f"  Is valid: {validation.is_valid}")
    if validation.error_message:
        print(f"  Error: {validation.error_message}")
    print()

    # Link citations
    linked = linker.link_citations(generated_text, sources)
    print("Linked Citations:")
    for cite in linked:
        status = "✅" if not cite.paper_id.startswith("INVALID") else "❌"
        print(f"  {status} [{cite.citation_number}] {cite.paper_id}")
        if cite.paper_title:
            print(f"      Title: {cite.paper_title}")
        if cite.url:
            print(f"      URL: {cite.url}")
    print()

    # Format as footnotes
    print("=== Formatted References ===")
    print(linker.format_citations_as_footnotes(linked))
