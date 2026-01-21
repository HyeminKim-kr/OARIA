"""인용 정보 생성 서비스

논문 메타데이터를 기반으로 다양한 인용 형식을 생성합니다.
LLM 없이 순수 템플릿 기반으로 동작합니다.

지원 형식:
- APA (American Psychological Association)
- MLA (Modern Language Association)
- Chicago
- Harvard
- Vancouver
- BibTeX
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.paper import Paper


@dataclass
class CitationResult:
    """인용 정보 결과"""

    format: str
    citation: str
    paper_id: str


class CitationService:
    """인용 정보 생성 서비스"""

    SUPPORTED_FORMATS = ["apa", "mla", "chicago", "harvard", "vancouver", "bibtex"]

    def generate(
        self,
        paper: "Paper",
        format: str = "apa",
    ) -> CitationResult:
        """인용 정보 생성

        Args:
            paper: Paper 모델 인스턴스
            format: 인용 형식 (apa, mla, chicago, harvard, vancouver, bibtex)

        Returns:
            CitationResult
        """
        format_lower = format.lower()
        if format_lower not in self.SUPPORTED_FORMATS:
            format_lower = "apa"

        # 저자 포맷팅
        authors = self._format_authors_from_paper(paper, format_lower)

        # 형식별 생성
        formatters = {
            "apa": self._generate_apa,
            "mla": self._generate_mla,
            "chicago": self._generate_chicago,
            "harvard": self._generate_harvard,
            "vancouver": self._generate_vancouver,
            "bibtex": self._generate_bibtex,
        }

        citation = formatters[format_lower](paper, authors)

        return CitationResult(
            format=format_lower,
            citation=citation,
            paper_id=paper.paper_id,
        )

    def _format_authors_from_paper(self, paper: "Paper", format: str) -> str:
        """Paper 모델에서 저자 정보 포맷팅"""
        if not paper.authors:
            return "Unknown Author"

        author_names = [a.author_name for a in paper.authors]

        if format == "apa":
            return self._format_authors_apa(author_names)
        elif format == "mla":
            return self._format_authors_mla(author_names)
        elif format == "chicago":
            return self._format_authors_chicago(author_names)
        elif format == "harvard":
            return self._format_authors_harvard(author_names)
        elif format == "vancouver":
            return self._format_authors_vancouver(author_names)
        elif format == "bibtex":
            return self._format_authors_bibtex(author_names)
        else:
            return ", ".join(author_names)

    def _format_authors_apa(self, names: list[str]) -> str:
        """APA 형식 저자 포맷팅: Last, F. M., & Last, F. M."""
        if not names:
            return "Unknown Author"

        formatted = []
        for name in names[:20]:  # APA는 최대 20명
            parts = name.split()
            if len(parts) >= 2:
                last = parts[-1]
                initials = " ".join(f"{p[0]}." for p in parts[:-1] if p)
                formatted.append(f"{last}, {initials}")
            else:
                formatted.append(name)

        if len(formatted) == 1:
            return formatted[0]
        elif len(formatted) == 2:
            return f"{formatted[0]}, & {formatted[1]}"
        else:
            return ", ".join(formatted[:-1]) + f", & {formatted[-1]}"

    def _format_authors_mla(self, names: list[str]) -> str:
        """MLA 형식: Last, First, et al."""
        if not names:
            return "Unknown Author"

        first_author = names[0]
        parts = first_author.split()
        if len(parts) >= 2:
            last = parts[-1]
            first = " ".join(parts[:-1])
            first_formatted = f"{last}, {first}"
        else:
            first_formatted = first_author

        if len(names) == 1:
            return first_formatted
        elif len(names) == 2:
            return f"{first_formatted}, and {names[1]}"
        else:
            return f"{first_formatted}, et al."

    def _format_authors_chicago(self, names: list[str]) -> str:
        """Chicago 형식: Last, First, and First Last."""
        if not names:
            return "Unknown Author"

        first_author = names[0]
        parts = first_author.split()
        if len(parts) >= 2:
            last = parts[-1]
            first = " ".join(parts[:-1])
            first_formatted = f"{last}, {first}"
        else:
            first_formatted = first_author

        if len(names) == 1:
            return first_formatted
        elif len(names) == 2:
            return f"{first_formatted}, and {names[1]}"
        elif len(names) <= 10:
            middle = ", ".join(names[1:-1])
            return f"{first_formatted}, {middle}, and {names[-1]}"
        else:
            return f"{first_formatted}, et al."

    def _format_authors_harvard(self, names: list[str]) -> str:
        """Harvard 형식: Last, F.M. and Last, F.M."""
        return self._format_authors_apa(names).replace("&", "and")

    def _format_authors_vancouver(self, names: list[str]) -> str:
        """Vancouver 형식: Last FM, Last FM."""
        if not names:
            return "Unknown Author"

        formatted = []
        for name in names[:6]:  # Vancouver는 최대 6명
            parts = name.split()
            if len(parts) >= 2:
                last = parts[-1]
                initials = "".join(f"{p[0]}" for p in parts[:-1] if p)
                formatted.append(f"{last} {initials}")
            else:
                formatted.append(name)

        if len(names) > 6:
            return ", ".join(formatted) + ", et al."
        return ", ".join(formatted)

    def _format_authors_bibtex(self, names: list[str]) -> str:
        """BibTeX 형식: Last, First and Last, First"""
        if not names:
            return "Unknown Author"

        formatted = []
        for name in names:
            parts = name.split()
            if len(parts) >= 2:
                last = parts[-1]
                first = " ".join(parts[:-1])
                formatted.append(f"{last}, {first}")
            else:
                formatted.append(name)

        return " and ".join(formatted)

    def _generate_apa(self, paper: "Paper", authors: str) -> str:
        """APA 7th edition 형식 생성"""
        year = paper.year or "n.d."
        title = paper.title or "Untitled"
        journal = paper.journal or "Unknown Journal"

        citation = f"{authors} ({year}). {title}. {journal}."

        if paper.doi:
            citation += f" https://doi.org/{paper.doi}"

        return citation

    def _generate_mla(self, paper: "Paper", authors: str) -> str:
        """MLA 9th edition 형식 생성"""
        title = paper.title or "Untitled"
        journal = paper.journal or "Unknown Journal"
        year = paper.year or "n.d."

        citation = f'{authors}. "{title}." {journal}, {year}.'

        if paper.doi:
            citation += f" doi:{paper.doi}."

        return citation

    def _generate_chicago(self, paper: "Paper", authors: str) -> str:
        """Chicago 17th edition 형식 생성"""
        title = paper.title or "Untitled"
        journal = paper.journal or "Unknown Journal"
        year = paper.year or "n.d."

        citation = f'{authors}. "{title}." {journal} ({year}).'

        if paper.doi:
            citation += f" https://doi.org/{paper.doi}."

        return citation

    def _generate_harvard(self, paper: "Paper", authors: str) -> str:
        """Harvard 형식 생성"""
        year = paper.year or "n.d."
        title = paper.title or "Untitled"
        journal = paper.journal or "Unknown Journal"

        citation = f"{authors} ({year}) '{title}', {journal}."

        if paper.doi:
            citation += f" doi: {paper.doi}."

        return citation

    def _generate_vancouver(self, paper: "Paper", authors: str) -> str:
        """Vancouver 형식 생성"""
        title = paper.title or "Untitled"
        journal = paper.journal or "Unknown Journal"
        year = paper.year or "n.d."

        citation = f"{authors}. {title}. {journal}. {year}."

        if paper.doi:
            citation += f" doi: {paper.doi}"

        return citation

    def _generate_bibtex(self, paper: "Paper", authors: str) -> str:
        """BibTeX 형식 생성"""
        # BibTeX 키 생성 (첫 저자 성 + 연도)
        first_author = paper.authors[0].author_name if paper.authors else "unknown"
        last_name = first_author.split()[-1].lower() if first_author else "unknown"
        year = paper.year or "nd"
        bib_key = f"{last_name}{year}"

        title = paper.title or "Untitled"
        journal = paper.journal or "Unknown Journal"

        bibtex = f"""@article{{{bib_key},
  author = {{{authors}}},
  title = {{{title}}},
  journal = {{{journal}}},
  year = {{{year}}}"""

        if paper.doi:
            bibtex += f""",
  doi = {{{paper.doi}}}"""

        if paper.pmid:
            bibtex += f""",
  pmid = {{{paper.pmid}}}"""

        if paper.pmcid:
            bibtex += f""",
  pmcid = {{{paper.pmcid}}}"""

        bibtex += "\n}"

        return bibtex


# 싱글톤 인스턴스
citation_service = CitationService()


def get_citation_service() -> CitationService:
    """CitationService 의존성"""
    return citation_service
