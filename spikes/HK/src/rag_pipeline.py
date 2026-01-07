"""
OAR-36: RAG Pipeline Integration API

Orchestrates all RAG components into a unified pipeline:
- Retriever (OAR-32): Embeds query and searches vector store
- Reranker (OAR-33): Cross-encoder for improved relevance
- Generator (OAR-34): LLM answer generation with citations
- Citation Linker (OAR-35): Validates and links citations

Author: HK
Created: 2025-12-30
Jira: OAR-36
"""

import time
from dataclasses import dataclass, field
from typing import Optional, Generator, Any
import asyncio


# ============================================================================
# DATA CLASSES
# ============================================================================

@dataclass
class RAGQuery:
    """
    Input for RAG pipeline.

    Matches the API spec:
    - query: User's question
    - top_k: Initial retrieval count (default 20)
    - rerank_top_n: Final docs after reranking (default 5)
    """
    query: str
    top_k: int = 20
    rerank_top_n: int = 5

    # Optional filters
    min_score: float = 0.0
    filter_metadata: Optional[dict] = None


@dataclass
class Evidence:
    """Single piece of evidence from a paper."""
    paper_id: str
    title: Optional[str]
    text_snippet: str
    relevance_score: float
    doi: Optional[str] = None
    pmid: Optional[str] = None
    journal: Optional[str] = None
    publication_date: Optional[str] = None
    url: Optional[str] = None
    citation_number: int = 0

    def to_dict(self) -> dict:
        return {
            "paper_id": self.paper_id,
            "title": self.title,
            "text_snippet": self.text_snippet,
            "relevance_score": self.relevance_score,
            "doi": self.doi,
            "pmid": self.pmid,
            "journal": self.journal,
            "publication_date": self.publication_date,
            "url": self.url,
            "citation_number": self.citation_number,
        }


@dataclass
class RAGResponse:
    """
    Complete RAG pipeline response.

    Matches the API spec output:
    - answer: Generated answer with [1], [2] citations
    - evidence: List of cited papers
    - retrieval_scores: Similarity scores from retrieval
    - processing_time_ms: Total pipeline time
    """
    answer: str
    evidence: list[Evidence]
    retrieval_scores: list[float]
    processing_time_ms: float

    # Additional metadata
    citations_used: list[int] = field(default_factory=list)
    citations_valid: bool = True
    invalid_citations: list[int] = field(default_factory=list)
    model: str = ""
    input_tokens: int = 0
    output_tokens: int = 0

    # Stage timings for debugging
    retrieval_time_ms: float = 0.0
    rerank_time_ms: float = 0.0
    generation_time_ms: float = 0.0

    def to_dict(self) -> dict:
        return {
            "answer": self.answer,
            "evidence": [e.to_dict() for e in self.evidence],
            "retrieval_scores": self.retrieval_scores,
            "processing_time_ms": self.processing_time_ms,
            "citations_used": self.citations_used,
            "citations_valid": self.citations_valid,
            "metadata": {
                "model": self.model,
                "input_tokens": self.input_tokens,
                "output_tokens": self.output_tokens,
                "timings": {
                    "retrieval_ms": self.retrieval_time_ms,
                    "rerank_ms": self.rerank_time_ms,
                    "generation_ms": self.generation_time_ms,
                }
            }
        }


@dataclass
class RAGError:
    """Error response for RAG failures."""
    error_type: str
    message: str
    suggestion: Optional[str] = None
    details: Optional[dict] = None

    def to_dict(self) -> dict:
        return {
            "error_type": self.error_type,
            "message": self.message,
            "suggestion": self.suggestion,
            "details": self.details,
        }


# ============================================================================
# RAG PIPELINE CLASS
# ============================================================================

class RAGPipeline:
    """
    Unified RAG pipeline integrating all components.

    Design Decisions:
    -----------------
    1. WHY unified pipeline?
       - Single entry point for all RAG operations
       - Consistent error handling across components
       - Easy to monitor and debug end-to-end
       - Can be exposed as API endpoint directly

    2. WHY lazy loading?
       - Components are heavy (embedder ~400MB, reranker ~100MB)
       - Only load what's needed
       - Faster startup for testing

    3. WHY timing breakdown?
       - Helps identify bottlenecks
       - Enables optimization decisions
       - Useful for monitoring in production

    4. WHY evidence extraction from sources?
       - Generator output tells us which citations were used
       - We map back to sources to build evidence list
       - Citation Linker validates and adds URLs

    Pipeline Flow:
    -------------
    Query → Retrieve (top_k) → Rerank (top_n) → Generate → Link Citations → Response

    Example:
        pipeline = RAGPipeline()
        response = pipeline.query(RAGQuery(query="What is EGFR?", top_k=20, rerank_top_n=5))
        print(response.answer)
    """

    def __init__(
        self,
        retriever=None,
        reranker=None,
        generator=None,
        citation_linker=None,
    ):
        """
        Initialize RAG pipeline with optional component injection.

        If components not provided, they are lazily loaded on first use.
        This allows:
        - Testing with mock components
        - Custom configurations
        - Faster startup when not all components needed
        """
        self._retriever = retriever
        self._reranker = reranker
        self._generator = generator
        self._citation_linker = citation_linker

    @property
    def retriever(self):
        """Lazy load retriever."""
        if self._retriever is None:
            from retriever import Retriever
            self._retriever = Retriever()
        return self._retriever

    @property
    def reranker(self):
        """Lazy load reranker."""
        if self._reranker is None:
            from reranker import CrossEncoderReranker
            self._reranker = CrossEncoderReranker()
        return self._reranker

    @property
    def generator(self):
        """Lazy load generator."""
        if self._generator is None:
            from generator import LLMGenerator
            self._generator = LLMGenerator()
        return self._generator

    @property
    def citation_linker(self):
        """Lazy load citation linker."""
        if self._citation_linker is None:
            from citation_linker import CitationLinker
            self._citation_linker = CitationLinker()
        return self._citation_linker

    def query(self, request: RAGQuery) -> RAGResponse:
        """
        Execute RAG pipeline for a query.

        Args:
            request: RAGQuery with query text and parameters

        Returns:
            RAGResponse with answer, evidence, and metadata

        Raises:
            RAGError: If pipeline fails at any stage
        """
        total_start = time.perf_counter()

        # Stage 1: Retrieval
        retrieval_start = time.perf_counter()
        try:
            retrieval_result = self.retriever.retrieve(
                query=request.query,
                top_k=request.top_k,
                min_score=request.min_score,
                filter_dict=request.filter_metadata,
            )
        except Exception as e:
            raise RAGError(
                error_type="retrieval_failed",
                message=f"Failed to retrieve documents: {str(e)}",
                suggestion="Try a different query or check vector store connection",
            )
        retrieval_time = (time.perf_counter() - retrieval_start) * 1000

        # Check if we have any results
        if not retrieval_result.results:
            return RAGResponse(
                answer="제공된 논문에서 관련 정보를 찾지 못했습니다. 질문을 다르게 표현해 보세요.",
                evidence=[],
                retrieval_scores=[],
                processing_time_ms=(time.perf_counter() - total_start) * 1000,
                retrieval_time_ms=retrieval_time,
            )

        # Stage 2: Reranking
        rerank_start = time.perf_counter()
        try:
            rerank_result = self.reranker.rerank_retrieval_result(
                query=request.query,
                retrieval_results=retrieval_result.results,
                top_n=request.rerank_top_n,
            )
        except Exception as e:
            raise RAGError(
                error_type="rerank_failed",
                message=f"Failed to rerank documents: {str(e)}",
                suggestion="Try with fewer documents or check reranker model",
            )
        rerank_time = (time.perf_counter() - rerank_start) * 1000

        # Prepare sources for generator
        sources = []
        for result in rerank_result.results:
            sources.append({
                "paper_id": result.id,
                "text": result.text,
                "score": result.rerank_score,
                "metadata": result.metadata or {},
            })

        # Stage 3: Generation
        generation_start = time.perf_counter()
        try:
            gen_output = self.generator.generate(
                question=request.query,
                sources=sources,
            )
        except Exception as e:
            raise RAGError(
                error_type="generation_failed",
                message=f"Failed to generate answer: {str(e)}",
                suggestion="Check API key and try again",
            )
        generation_time = (time.perf_counter() - generation_start) * 1000

        # Stage 4: Citation linking and validation
        linked_citations = self.citation_linker.link_citations(
            gen_output.answer,
            sources,
        )
        validation = self.citation_linker.validate_citations(
            gen_output.answer,
            sources,
        )

        # Build evidence list from linked citations
        evidence = []
        for linked in linked_citations:
            evidence.append(Evidence(
                paper_id=linked.paper_id,
                title=linked.paper_title,
                text_snippet=linked.text_snippet,
                relevance_score=linked.relevance_score,
                doi=linked.doi,
                pmid=linked.pmid,
                journal=linked.journal,
                publication_date=linked.publication_date,
                url=linked.url,
                citation_number=linked.citation_number,
            ))

        total_time = (time.perf_counter() - total_start) * 1000

        return RAGResponse(
            answer=gen_output.answer,
            evidence=evidence,
            retrieval_scores=[r.score for r in retrieval_result.results[:request.rerank_top_n]],
            processing_time_ms=total_time,
            citations_used=gen_output.citations_used,
            citations_valid=validation.is_valid,
            invalid_citations=validation.invalid_citations,
            model=gen_output.model,
            input_tokens=gen_output.input_tokens,
            output_tokens=gen_output.output_tokens,
            retrieval_time_ms=retrieval_time,
            rerank_time_ms=rerank_time,
            generation_time_ms=generation_time,
        )

    def query_stream(
        self,
        request: RAGQuery,
    ) -> Generator[str, None, RAGResponse]:
        """
        Execute RAG pipeline with streaming response.

        Yields text chunks as they're generated, returns full
        RAGResponse at the end.

        Usage:
            gen = pipeline.query_stream(request)
            for chunk in gen:
                print(chunk, end="", flush=True)
            response = gen.value
        """
        total_start = time.perf_counter()

        # Stage 1 & 2: Retrieval and Reranking (non-streaming)
        retrieval_result = self.retriever.retrieve(
            query=request.query,
            top_k=request.top_k,
        )
        retrieval_time = (time.perf_counter() - total_start) * 1000

        if not retrieval_result.results:
            yield "제공된 논문에서 관련 정보를 찾지 못했습니다."
            return RAGResponse(
                answer="제공된 논문에서 관련 정보를 찾지 못했습니다.",
                evidence=[],
                retrieval_scores=[],
                processing_time_ms=(time.perf_counter() - total_start) * 1000,
            )

        rerank_start = time.perf_counter()
        rerank_result = self.reranker.rerank_retrieval_result(
            query=request.query,
            retrieval_results=retrieval_result.results,
            top_n=request.rerank_top_n,
        )
        rerank_time = (time.perf_counter() - rerank_start) * 1000

        # Prepare sources
        sources = []
        for result in rerank_result.results:
            sources.append({
                "paper_id": result.id,
                "text": result.text,
                "score": result.rerank_score,
                "metadata": result.metadata or {},
            })

        # Stage 3: Streaming generation
        generation_start = time.perf_counter()
        full_answer = []

        for chunk in self.generator.generate_stream(request.query, sources):
            full_answer.append(chunk)
            yield chunk

        generation_time = (time.perf_counter() - generation_start) * 1000
        answer = "".join(full_answer)

        # Stage 4: Citation linking
        linked_citations = self.citation_linker.link_citations(answer, sources)
        validation = self.citation_linker.validate_citations(answer, sources)

        evidence = []
        for linked in linked_citations:
            evidence.append(Evidence(
                paper_id=linked.paper_id,
                title=linked.paper_title,
                text_snippet=linked.text_snippet,
                relevance_score=linked.relevance_score,
                doi=linked.doi,
                url=linked.url,
                citation_number=linked.citation_number,
            ))

        total_time = (time.perf_counter() - total_start) * 1000

        return RAGResponse(
            answer=answer,
            evidence=evidence,
            retrieval_scores=[r.score for r in retrieval_result.results[:request.rerank_top_n]],
            processing_time_ms=total_time,
            citations_used=self.citation_linker.extract_citations(answer),
            citations_valid=validation.is_valid,
            retrieval_time_ms=retrieval_time,
            rerank_time_ms=rerank_time,
            generation_time_ms=generation_time,
        )

    def get_formatted_response(
        self,
        response: RAGResponse,
        include_references: bool = True,
    ) -> str:
        """
        Format RAGResponse as display-ready text.

        Args:
            response: RAG pipeline response
            include_references: Whether to append reference list

        Returns:
            Formatted string with answer and optional references
        """
        output = response.answer

        if include_references and response.evidence:
            refs = self.citation_linker.format_citations_as_footnotes(
                [self._evidence_to_linked(e) for e in response.evidence]
            )
            output += refs

        return output

    def _evidence_to_linked(self, evidence: Evidence):
        """Convert Evidence to LinkedCitation for formatting."""
        from citation_linker import LinkedCitation
        return LinkedCitation(
            citation_number=evidence.citation_number,
            paper_id=evidence.paper_id,
            paper_title=evidence.title,
            doi=evidence.doi,
            pmid=evidence.pmid,
            journal=evidence.journal,
            publication_date=evidence.publication_date,
            text_snippet=evidence.text_snippet,
            relevance_score=evidence.relevance_score,
            url=evidence.url,
        )


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

def ask(
    query: str,
    top_k: int = 20,
    rerank_top_n: int = 5,
) -> RAGResponse:
    """
    Simple function to ask a question via RAG.

    Args:
        query: User's question
        top_k: Number of documents to retrieve
        rerank_top_n: Number of documents after reranking

    Returns:
        RAGResponse with answer and evidence
    """
    pipeline = RAGPipeline()
    return pipeline.query(RAGQuery(
        query=query,
        top_k=top_k,
        rerank_top_n=rerank_top_n,
    ))


def ask_simple(query: str) -> str:
    """
    Simplest interface - just returns the answer string.

    Args:
        query: User's question

    Returns:
        Generated answer string
    """
    response = ask(query)
    return response.answer


# ============================================================================
# API-READY HANDLER
# ============================================================================

class RAGAPIHandler:
    """
    API-ready handler for RAG pipeline.

    Design for integration with FastAPI/Flask:
    - Singleton pipeline instance
    - Timeout handling
    - Error response formatting
    - Request validation
    """

    def __init__(self, timeout_seconds: float = 30.0):
        """Initialize API handler with timeout."""
        self.pipeline = RAGPipeline()
        self.timeout = timeout_seconds

    async def handle_ask(
        self,
        query: str,
        top_k: int = 20,
        rerank_top_n: int = 5,
    ) -> dict:
        """
        Handle /api/v1/ask endpoint.

        Args:
            query: User question
            top_k: Retrieval count
            rerank_top_n: Final doc count

        Returns:
            Dict with answer, evidence, scores, timing
        """
        try:
            # Run in thread pool to avoid blocking
            import asyncio
            loop = asyncio.get_event_loop()

            request = RAGQuery(
                query=query,
                top_k=top_k,
                rerank_top_n=rerank_top_n,
            )

            # Execute with timeout
            response = await asyncio.wait_for(
                loop.run_in_executor(None, self.pipeline.query, request),
                timeout=self.timeout,
            )

            return {
                "success": True,
                "data": response.to_dict(),
            }

        except asyncio.TimeoutError:
            return {
                "success": False,
                "error": {
                    "type": "timeout",
                    "message": f"Query exceeded {self.timeout}s timeout",
                    "suggestion": "Try a simpler query or reduce top_k",
                }
            }
        except Exception as e:
            return {
                "success": False,
                "error": {
                    "type": "internal_error",
                    "message": str(e),
                    "suggestion": "Please try again or contact support",
                }
            }


# ============================================================================
# DEMO
# ============================================================================

if __name__ == "__main__":
    print("=== RAG Pipeline Demo ===\n")
    print("This demo shows the pipeline structure without actual execution.")
    print("(Requires vector store with indexed data and API keys)\n")

    # Show pipeline structure
    print("Pipeline Components:")
    print("  1. Retriever (OAR-32) - Embeds query, searches vector store")
    print("  2. Reranker (OAR-33) - Cross-encoder for better relevance")
    print("  3. Generator (OAR-34) - Claude API for answer generation")
    print("  4. Citation Linker (OAR-35) - Links and validates citations")
    print()

    # Show data classes
    print("Data Classes:")
    print(f"  RAGQuery: query, top_k={20}, rerank_top_n={5}")
    print(f"  RAGResponse: answer, evidence[], retrieval_scores, processing_time_ms")
    print()

    # Show API spec
    print("API Spec (OAR-36):")
    print("  POST /api/v1/ask")
    print("  Input: { query, top_k, rerank_top_n }")
    print("  Output: { answer, evidence[], retrieval_scores, processing_time_ms }")
    print()

    # Example usage
    print("Example Usage:")
    print("""
    # Basic usage
    from rag_pipeline import RAGPipeline, RAGQuery

    pipeline = RAGPipeline()
    response = pipeline.query(RAGQuery(
        query="What is EGFR inhibitor efficacy in lung cancer?",
        top_k=20,
        rerank_top_n=5
    ))

    print(response.answer)
    print(f"Evidence: {len(response.evidence)} papers")
    print(f"Time: {response.processing_time_ms:.0f}ms")

    # Or simpler
    from rag_pipeline import ask_simple
    answer = ask_simple("What is EGFR?")
    """)

    print("\n=== Pipeline Flow ===")
    print("""
    Query: "What is EGFR inhibitor efficacy?"
           ↓
    ┌──────────────────────────────────────────────┐
    │ Stage 1: RETRIEVAL (~50ms)                   │
    │ - Embed query with PubMedBERT                │
    │ - Search vector store for top_k=20 docs      │
    │ - Return docs with similarity scores         │
    └──────────────────────────────────────────────┘
           ↓
    ┌──────────────────────────────────────────────┐
    │ Stage 2: RERANKING (~200ms)                  │
    │ - Cross-encoder scores each (query, doc)     │
    │ - Keep top_n=5 highest scoring docs          │
    │ - More accurate than retrieval scores        │
    └──────────────────────────────────────────────┘
           ↓
    ┌──────────────────────────────────────────────┐
    │ Stage 3: GENERATION (~2000ms)                │
    │ - Build prompt with sources                  │
    │ - Call Claude API with citations prompt      │
    │ - Get answer with [1], [2] citations         │
    └──────────────────────────────────────────────┘
           ↓
    ┌──────────────────────────────────────────────┐
    │ Stage 4: CITATION LINKING (<1ms)             │
    │ - Extract [1], [2] from answer               │
    │ - Map to paper metadata (title, DOI, etc)    │
    │ - Validate all citations exist               │
    │ - Generate clickable URLs                    │
    └──────────────────────────────────────────────┘
           ↓
    Response: answer + evidence + metadata
    """)
