"""
LLM Generator for RAG Pipeline

Generates evidence-based answers using Claude API:
- Builds context from retrieved documents
- Uses citation-aware prompts
- Extracts and validates citations

Author: HK
Created: 2025-12-30
Spec: F-03 Section 3.6, 7
"""

import re
import time
import logging
import os
from typing import Optional
from datetime import date

from .models import RerankResult, GeneratorOutput, Evidence

logger = logging.getLogger(__name__)


# =============================================================================
# PROMPT TEMPLATES
# =============================================================================

SYSTEM_PROMPT_KO = """당신은 암 연구 전문 AI 어시스턴트입니다.

역할: 제공된 연구 논문만을 기반으로 암 과학, 치료법, 예후에 관한 질문에 답변합니다.

핵심 원칙:
1. 근거 기반: 모든 주장은 제공된 논문으로 뒷받침되어야 함
2. 인용 필수: [1], [2] 등으로 출처를 인라인 표기
3. 정직한 불확실성: 논문에 없는 내용은 "제공된 논문에서 확인할 수 없습니다"라고 답변
4. 환각 금지: 사실, 통계, 인용을 만들어내지 않음
5. 권유 금지: 임상적 결정이나 치료 권고 제공 안 함

작성 스타일:
- 학술적이지만 이해하기 쉽게
- 복잡한 용어는 간단히 설명 추가
- 논문들이 다르게 말하면 여러 관점 제시
- 가능하면 수치화 (인용과 함께)"""

SYSTEM_PROMPT_EN = """You are an oncology research AI assistant.

Your role is to answer questions about cancer science, treatments, and prognosis
based ONLY on the research papers provided to you.

Core Principles:
1. EVIDENCE-BASED: Every claim must be supported by the provided papers
2. CITATIONS: Use [1], [2], etc. to cite sources inline
3. HONEST UNCERTAINTY: Say "the provided papers don't address this" when applicable
4. NO HALLUCINATION: Never make up facts, statistics, or citations
5. NO ADVICE: Do not give clinical recommendations or treatment advice

Writing Style:
- Academic but accessible
- Use precise terminology with brief explanations for complex terms
- Present multiple perspectives if papers disagree
- Quantify claims when possible (with citations)"""


def build_context(documents: list[RerankResult], include_metadata: bool = True) -> str:
    """
    Build context string from retrieved documents.

    Args:
        documents: Reranked documents
        include_metadata: Include author/journal info

    Returns:
        Formatted context string
    """
    context_parts = []

    for i, doc in enumerate(documents, 1):
        if include_metadata:
            # Format authors (max 3 + et al.)
            authors = doc.authors or []
            if len(authors) > 3:
                author_str = ", ".join(authors[:3]) + " et al."
            else:
                author_str = ", ".join(authors) if authors else "Unknown"

            context_parts.append(f"""
[{i}] {doc.title or 'Untitled'}
저자: {author_str}
저널: {doc.metadata.get('journal', 'Unknown')} ({doc.metadata.get('publication_date', 'Unknown')})
DOI: {doc.doi or 'N/A'}

{doc.text}
---""")
        else:
            context_parts.append(f"""
[{i}] {doc.title or 'Untitled'}

{doc.text}
---""")

    return "\n".join(context_parts)


def build_prompt(
    query: str,
    documents: list[RerankResult],
    language: str = "ko",
    include_metadata: bool = True,
) -> str:
    """
    Build complete prompt for LLM.

    Args:
        query: User's question
        documents: Retrieved and reranked documents
        language: 'ko' for Korean, 'en' for English
        include_metadata: Include author/journal info in context

    Returns:
        Complete prompt string
    """
    system_prompt = SYSTEM_PROMPT_KO if language == "ko" else SYSTEM_PROMPT_EN
    context = build_context(documents, include_metadata)

    prompt = f"""{system_prompt}

참고 논문:
{context}

질문: {query}

위 논문들을 참고하여 인용과 함께 종합적인 답변을 제공해 주세요."""

    return prompt


class LLMGenerator:
    """
    LLM-based answer generator with citation support.

    Design Decisions:
    -----------------
    1. WHY CLAUDE?
       - Excellent instruction following
       - Good citation handling
       - Korean language support
       - Reasonable API costs

    2. WHY INLINE CITATIONS?
       - [1], [2] format is readable
       - Easy to parse programmatically
       - Standard academic style
       - Maps directly to Evidence objects

    3. WHY EXTRACT CITATIONS?
       - Validate that LLM actually cited sources
       - Build Evidence objects with citation_markers
       - Detect hallucinated citations

    Usage:
        generator = LLMGenerator()

        output = await generator.generate(
            query="What is EGFR?",
            documents=reranked_docs,
        )

        print(output.answer)
        print(output.citations_used)
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "claude-sonnet-4-20250514",
        max_tokens: int = 2048,
        language: str = "ko",
    ):
        """
        Initialize generator.

        Args:
            api_key: Anthropic API key (or set ANTHROPIC_API_KEY env var)
            model: Claude model to use
            max_tokens: Maximum tokens in response
            language: 'ko' or 'en' for prompts
        """
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        self.model = model
        self.max_tokens = max_tokens
        self.language = language

        if not self.api_key:
            logger.warning("No Anthropic API key provided. Set ANTHROPIC_API_KEY.")

        self._client = None

    @property
    def client(self):
        """Lazy load Anthropic client."""
        if self._client is None:
            try:
                import anthropic
                self._client = anthropic.AsyncAnthropic(api_key=self.api_key)
            except ImportError:
                raise ImportError(
                    "anthropic package required. Install with: pip install anthropic"
                )
        return self._client

    def _extract_citations(self, answer: str, max_citation: int) -> list[int]:
        """
        Extract citation numbers from answer text.

        Args:
            answer: Generated answer text
            max_citation: Maximum valid citation number

        Returns:
            List of unique citation numbers used
        """
        # Find all [n] and [n,m,...] patterns
        pattern = r'\[(\d+(?:,\s*\d+)*)\]'
        citations = set()

        for match in re.finditer(pattern, answer):
            numbers = match.group(1).split(',')
            for num in numbers:
                try:
                    n = int(num.strip())
                    if 1 <= n <= max_citation:
                        citations.add(n)
                except ValueError:
                    continue

        return sorted(citations)

    def _build_evidence(
        self,
        documents: list[RerankResult],
        answer: str,
    ) -> list[Evidence]:
        """
        Build Evidence objects from documents and answer.

        Args:
            documents: Source documents
            answer: Generated answer with citations

        Returns:
            List of Evidence objects with citation markers
        """
        evidence = []
        citation_pattern = r'\[(\d+(?:,\s*\d+)*)\]'

        for doc_index, doc in enumerate(documents, 1):
            markers = []

            # Find all citations to this document
            for match in re.finditer(citation_pattern, answer):
                cited_numbers = [int(n.strip()) for n in match.group(1).split(",")]
                if doc_index in cited_numbers:
                    markers.append(f"[{doc_index}]")

            if markers:
                # Parse publication date if string
                pub_date = None
                if doc.metadata.get("publication_date"):
                    try:
                        date_str = doc.metadata["publication_date"]
                        if isinstance(date_str, str):
                            pub_date = date.fromisoformat(date_str[:10])
                        elif isinstance(date_str, date):
                            pub_date = date_str
                    except (ValueError, TypeError):
                        pass

                evidence.append(Evidence(
                    openalex_id=doc.paper_id or doc.id,
                    title=doc.title or "Untitled",
                    cited_chunk=doc.text[:500] + "..." if len(doc.text) > 500 else doc.text,
                    relevance_score=doc.rerank_score,
                    authors=doc.authors or [],
                    journal=doc.metadata.get("journal"),
                    publication_date=pub_date,
                    doi=doc.doi,
                    pmid=doc.pmid,
                    url=f"https://doi.org/{doc.doi}" if doc.doi else None,
                    citation_markers=list(set(markers)),
                ))

        return evidence

    async def generate(
        self,
        query: str,
        documents: list[RerankResult],
        include_metadata: bool = True,
    ) -> GeneratorOutput:
        """
        Generate answer using Claude API.

        Args:
            query: User's question
            documents: Retrieved and reranked documents
            include_metadata: Include author/journal info in context

        Returns:
            GeneratorOutput with answer and citations
        """
        start_time = time.time()

        if not documents:
            return GeneratorOutput(
                answer="제공된 논문 정보가 없어 답변을 생성할 수 없습니다.",
                citations_used=[],
                model=self.model,
                input_tokens=0,
                output_tokens=0,
                generation_time_ms=0,
                context_sources=[],
            )

        # Build prompt
        prompt = build_prompt(
            query=query,
            documents=documents,
            language=self.language,
            include_metadata=include_metadata,
        )

        # Call Claude API
        try:
            response = await self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )

            answer = response.content[0].text
            input_tokens = response.usage.input_tokens
            output_tokens = response.usage.output_tokens

        except Exception as e:
            logger.error(f"Claude API error: {e}")
            return GeneratorOutput(
                answer=f"답변 생성 중 오류가 발생했습니다: {str(e)}",
                citations_used=[],
                model=self.model,
                input_tokens=0,
                output_tokens=0,
                generation_time_ms=(time.time() - start_time) * 1000,
                context_sources=[],
            )

        # Extract citations
        citations_used = self._extract_citations(answer, len(documents))

        # Build context sources for debugging
        context_sources = [
            {
                "index": i + 1,
                "paper_id": doc.paper_id,
                "title": doc.title,
                "score": doc.rerank_score,
            }
            for i, doc in enumerate(documents)
        ]

        generation_time_ms = (time.time() - start_time) * 1000

        logger.info(
            f"Generation completed: query='{query[:50]}...', "
            f"citations={len(citations_used)}, "
            f"tokens={input_tokens}+{output_tokens}, "
            f"time={generation_time_ms:.1f}ms"
        )

        return GeneratorOutput(
            answer=answer,
            citations_used=citations_used,
            model=self.model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            generation_time_ms=generation_time_ms,
            context_sources=context_sources,
        )

    async def generate_with_evidence(
        self,
        query: str,
        documents: list[RerankResult],
    ) -> tuple[GeneratorOutput, list[Evidence]]:
        """
        Generate answer and extract evidence.

        Args:
            query: User's question
            documents: Retrieved and reranked documents

        Returns:
            Tuple of (GeneratorOutput, list[Evidence])
        """
        output = await self.generate(query, documents)
        evidence = self._build_evidence(documents, output.answer)
        return output, evidence


# Convenience function
async def generate_answer(
    query: str,
    documents: list[RerankResult],
    api_key: Optional[str] = None,
) -> GeneratorOutput:
    """Quick function to generate an answer."""
    generator = LLMGenerator(api_key=api_key)
    return await generator.generate(query, documents)


if __name__ == "__main__":
    import asyncio

    print("=== LLM Generator Demo ===\n")

    # Check API key
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("ANTHROPIC_API_KEY not set. Showing structure only.\n")
        print("Structure overview:")
        print("""
LLMGenerator:
  - generate(query, documents) -> GeneratorOutput
  - generate_with_evidence(query, documents) -> (GeneratorOutput, list[Evidence])

GeneratorOutput:
  - answer: str (with [1], [2] citations)
  - citations_used: list[int]
  - model: str
  - input_tokens: int
  - output_tokens: int
  - generation_time_ms: float
  - context_sources: list[dict]

Evidence:
  - openalex_id: str
  - title: str
  - cited_chunk: str
  - relevance_score: float
  - citation_markers: list[str]
        """)
    else:
        # Demo with mock documents
        async def demo():
            generator = LLMGenerator()

            mock_docs = [
                RerankResult(
                    id="W123_chunk_0",
                    text="EGFR mutations are found in 15% of NSCLC patients. These mutations predict response to TKIs.",
                    original_score=0.85,
                    rerank_score=0.92,
                    rank=1,
                    metadata={"journal": "Nature Medicine", "publication_date": "2024-01-15"},
                    paper_id="W123",
                    title="EGFR in Lung Cancer",
                    authors=["Kim J", "Lee S"],
                ),
                RerankResult(
                    id="W456_chunk_0",
                    text="Osimertinib shows superior efficacy in EGFR-mutant NSCLC with T790M resistance.",
                    original_score=0.80,
                    rerank_score=0.88,
                    rank=2,
                    metadata={"journal": "NEJM", "publication_date": "2023-06-20"},
                    paper_id="W456",
                    title="Osimertinib Efficacy Study",
                    authors=["Park H"],
                ),
            ]

            output = await generator.generate(
                query="EGFR 변이 폐암 환자의 치료 옵션은?",
                documents=mock_docs,
            )

            print(f"Query: EGFR 변이 폐암 환자의 치료 옵션은?\n")
            print(f"Answer:\n{output.answer}\n")
            print(f"Citations used: {output.citations_used}")
            print(f"Tokens: {output.input_tokens} in, {output.output_tokens} out")
            print(f"Time: {output.generation_time_ms:.1f}ms")

        asyncio.run(demo())
