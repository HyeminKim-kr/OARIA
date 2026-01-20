"""
RAG Pipeline - Complete Query Processing

Orchestrates the full RAG workflow:
1. Query embedding (BGE-M3)
2. Hybrid search (Qdrant dense + sparse)
3. Cross-encoder reranking
4. Gate 2 validation
5. Answer generation (Claude)
6. Citation extraction

Author: HK
Created: 2025-12-30
Spec: F-03 Section 6.2
"""

import time
import logging
from typing import Optional
from datetime import date

from .models import (
    RAGQuery,
    RAGResponse,
    RAGError,
    Evidence,
    Gate2Result,
    Gate2Config,
    Gate2FailureReason,
)
from .embedder import BGEM3Embedder
from .retriever import HybridRetriever
from .reranker import CrossEncoderReranker
from .generator import LLMGenerator

logger = logging.getLogger(__name__)


class RAGPipeline:
    """
    Complete RAG pipeline for oncology research questions.

    Design Decisions:
    -----------------
    1. WHY THIS ORDER?
       Query → Embed → Search → Rerank → Gate2 → Generate → Citations

       - Embed once, use for both dense and sparse search
       - Search retrieves candidates (fast, approximate)
       - Rerank filters to best matches (slow, precise)
       - Gate2 validates before expensive LLM call
       - Generate only if we have quality evidence

    2. WHY GATE 2 BEFORE GENERATION?
       - LLM calls are expensive ($$$)
       - Poor retrieval → poor answer
       - Better to refuse than hallucinate
       - Clear feedback to user on why no answer

    3. WHY SHARE EMBEDDER?
       - BGE-M3 is a 2GB model
       - Loading once saves memory and time
       - Same embeddings for indexing and query

    Usage:
        pipeline = RAGPipeline()

        # Simple query
        response = await pipeline.query(RAGQuery(
            query="What are EGFR mutations?",
            top_k=20,
            top_n=5,
        ))

        if response.gate2_passed:
            print(response.answer)
        else:
            print(response.gate2_details["message"])
    """

    def __init__(
        self,
        qdrant_host: str = "localhost",
        qdrant_port: int = 6333,
        anthropic_api_key: Optional[str] = None,
        language: str = "ko",
    ):
        """
        Initialize RAG pipeline with all components.

        Args:
            qdrant_host: Qdrant server host
            qdrant_port: Qdrant server port
            anthropic_api_key: API key for Claude (or use env var)
            language: 'ko' or 'en' for prompts
        """
        logger.info("Initializing RAG pipeline...")

        # Shared embedder (loaded lazily)
        self.embedder = BGEM3Embedder()

        # Components
        self.retriever = HybridRetriever(
            qdrant_host=qdrant_host,
            qdrant_port=qdrant_port,
            embedder=self.embedder,
        )
        self.reranker = CrossEncoderReranker()
        self.generator = LLMGenerator(
            api_key=anthropic_api_key,
            language=language,
        )

        # Gate 2 config
        self.gate2_config = Gate2Config()

        logger.info("RAG pipeline initialized")

    def _check_gate2(
        self,
        query: str,
        documents: list,
        config: Optional[Gate2Config] = None,
    ) -> Gate2Result:
        """
        Run Gate 2 retrieval confidence checks.

        Checks:
        1. Similarity threshold (max score >= 0.7)
        2. Minimum relevant docs (>= 3 with score >= 0.6)
        3. Domain validation (>= 80% oncology-related)

        Args:
            query: User's query
            documents: Reranked documents
            config: Gate 2 configuration

        Returns:
            Gate2Result with pass/fail and details
        """
        config = config or self.gate2_config

        if not documents:
            return Gate2Result(
                passed=False,
                reason=Gate2FailureReason.INSUFFICIENT_DOCS,
                message="검색 결과가 없습니다. 다른 질문을 시도해 주세요.",
                max_similarity=0.0,
                relevant_count=0,
                domain_ratio=0.0,
            )

        # Check 1: Similarity threshold
        max_score = max(doc.rerank_score for doc in documents)
        if max_score < config.similarity_threshold:
            return Gate2Result(
                passed=False,
                reason=Gate2FailureReason.LOW_SIMILARITY,
                message="관련 논문을 충분히 찾지 못했습니다. 질문을 더 구체적으로 해주세요.",
                max_similarity=max_score,
                relevant_count=0,
                domain_ratio=0.0,
                details={
                    "threshold": config.similarity_threshold,
                    "max_score": max_score,
                },
            )

        # Check 2: Minimum relevant docs
        relevant_count = sum(
            1 for doc in documents
            if doc.rerank_score >= config.min_doc_score
        )
        if relevant_count < config.min_relevant_docs:
            return Gate2Result(
                passed=False,
                reason=Gate2FailureReason.INSUFFICIENT_DOCS,
                message="충분한 근거 논문을 찾지 못했습니다.",
                max_similarity=max_score,
                relevant_count=relevant_count,
                domain_ratio=0.0,
                details={
                    "min_required": config.min_relevant_docs,
                    "found": relevant_count,
                    "min_score": config.min_doc_score,
                },
            )

        # Check 3: Domain validation
        oncology_keywords = [
            "cancer", "tumor", "tumour", "oncology", "carcinoma", "malignant",
            "metastasis", "chemotherapy", "immunotherapy", "egfr", "kras",
            "lung cancer", "breast cancer", "nsclc", "sclc", "melanoma",
            "leukemia", "lymphoma", "tki", "checkpoint", "pd-1", "pd-l1",
            "암", "종양", "항암", "전이", "폐암", "유방암", "대장암",
        ]

        oncology_count = 0
        for doc in documents:
            text_lower = doc.text.lower()
            if any(kw in text_lower for kw in oncology_keywords):
                oncology_count += 1

        domain_ratio = oncology_count / len(documents) if documents else 0

        if domain_ratio < config.domain_ratio_threshold:
            return Gate2Result(
                passed=False,
                reason=Gate2FailureReason.DOMAIN_MISMATCH,
                message="검색 결과가 암 연구와 관련성이 낮습니다.",
                max_similarity=max_score,
                relevant_count=relevant_count,
                domain_ratio=domain_ratio,
                details={
                    "threshold": config.domain_ratio_threshold,
                    "actual_ratio": domain_ratio,
                },
            )

        # All checks passed
        return Gate2Result(
            passed=True,
            reason=None,
            message="검색 결과 검증 통과",
            max_similarity=max_score,
            relevant_count=relevant_count,
            domain_ratio=domain_ratio,
            details={
                "similarity_threshold": config.similarity_threshold,
                "min_docs_required": config.min_relevant_docs,
                "domain_threshold": config.domain_ratio_threshold,
            },
        )

    async def query(
        self,
        request: RAGQuery,
        gate2_config: Optional[Gate2Config] = None,
    ) -> RAGResponse:
        """
        Process a RAG query through the full pipeline.

        Args:
            request: RAGQuery with question and parameters
            gate2_config: Optional custom Gate 2 configuration

        Returns:
            RAGResponse with answer, evidence, and metadata
        """
        start_time = time.time()

        logger.info(f"RAG query start: '{request.query[:50]}...'")

        # Step 1: Hybrid search
        retrieval_output = self.retriever.search(
            query=request.query,
            top_k=request.top_k,
            min_year=request.date_from.year if request.date_from else None,
            max_year=request.date_to.year if request.date_to else None,
            min_citations=request.min_citations,
        )

        # Step 2: Reranking
        reranker_output = self.reranker.rerank(
            query=request.query,
            documents=retrieval_output.results,
            top_n=request.top_n,
        )

        # Step 3: Gate 2 validation
        gate2_result = self._check_gate2(
            query=request.query,
            documents=reranker_output.results,
            config=gate2_config,
        )

        if not gate2_result.passed:
            # Return early with failure response
            processing_time = int((time.time() - start_time) * 1000)

            logger.warning(
                f"Gate 2 failed: reason={gate2_result.reason}, "
                f"query='{request.query[:30]}...'"
            )

            return RAGResponse(
                answer="",
                evidence=[],
                retrieval_scores=[r.score for r in retrieval_output.results[:5]],
                avg_relevance=0.0,
                processing_time_ms=processing_time,
                gate2_passed=False,
                gate2_details={
                    "reason": gate2_result.reason.value if gate2_result.reason else None,
                    "message": gate2_result.message,
                    "max_similarity": gate2_result.max_similarity,
                    "relevant_count": gate2_result.relevant_count,
                    "domain_ratio": gate2_result.domain_ratio,
                },
            )

        # Step 4: Generate answer with Claude
        generator_output, evidence = await self.generator.generate_with_evidence(
            query=request.query,
            documents=reranker_output.results,
        )

        # Calculate metrics
        processing_time = int((time.time() - start_time) * 1000)
        avg_relevance = (
            sum(r.rerank_score for r in reranker_output.results) / len(reranker_output.results)
            if reranker_output.results else 0.0
        )

        logger.info(
            f"RAG query complete: time={processing_time}ms, "
            f"evidence={len(evidence)}, citations={len(generator_output.citations_used)}"
        )

        return RAGResponse(
            answer=generator_output.answer,
            evidence=evidence,
            retrieval_scores=[r.score for r in retrieval_output.results[:5]],
            avg_relevance=avg_relevance,
            processing_time_ms=processing_time,
            gate2_passed=True,
            gate2_details={
                "max_similarity": gate2_result.max_similarity,
                "relevant_count": gate2_result.relevant_count,
                "domain_ratio": gate2_result.domain_ratio,
            },
            citations_used=generator_output.citations_used,
            model=generator_output.model,
            input_tokens=generator_output.input_tokens,
            output_tokens=generator_output.output_tokens,
        )

    async def query_simple(
        self,
        query: str,
        top_k: int = 20,
        top_n: int = 5,
    ) -> RAGResponse:
        """
        Simplified query interface.

        Args:
            query: User's question
            top_k: Initial retrieval count
            top_n: Final count after reranking

        Returns:
            RAGResponse
        """
        request = RAGQuery(query=query, top_k=top_k, top_n=top_n)
        return await self.query(request)

    def get_stats(self) -> dict:
        """Get pipeline component statistics."""
        return {
            "embedder": self.embedder.get_stats(),
            "retriever": {
                "collection": self.retriever.COLLECTION_NAME,
            },
            "reranker": {
                "model": self.reranker.model_name,
            },
            "generator": {
                "model": self.generator.model,
                "language": self.generator.language,
            },
            "gate2": {
                "similarity_threshold": self.gate2_config.similarity_threshold,
                "min_relevant_docs": self.gate2_config.min_relevant_docs,
                "domain_ratio_threshold": self.gate2_config.domain_ratio_threshold,
            },
        }


# Convenience function
async def ask(
    query: str,
    top_k: int = 20,
    top_n: int = 5,
) -> RAGResponse:
    """Quick function to ask a question."""
    pipeline = RAGPipeline()
    return await pipeline.query_simple(query, top_k, top_n)


if __name__ == "__main__":
    import asyncio
    import os

    print("=== RAG Pipeline Demo ===\n")

    # Check requirements
    api_key = os.environ.get("ANTHROPIC_API_KEY")

    if not api_key:
        print("ANTHROPIC_API_KEY not set. Showing structure only.\n")
        print("""
RAGPipeline:
  - query(request: RAGQuery) -> RAGResponse
  - query_simple(query, top_k, top_n) -> RAGResponse
  - get_stats() -> dict

Pipeline flow:
  1. Query → BGE-M3 Embedding
  2. Qdrant Hybrid Search (dense + sparse)
  3. Cross-encoder Reranking
  4. Gate 2 Validation
  5. Claude Answer Generation
  6. Citation Extraction

RAGResponse:
  - answer: str (with [1], [2] citations)
  - evidence: list[Evidence]
  - retrieval_scores: list[float]
  - avg_relevance: float
  - processing_time_ms: int
  - gate2_passed: bool
  - gate2_details: dict
        """)
    else:
        async def demo():
            try:
                pipeline = RAGPipeline()

                # Check if Qdrant has data
                from qdrant_client import QdrantClient
                client = QdrantClient(host="localhost", port=6333)

                if not client.collection_exists("oncology_papers"):
                    print("Collection 'oncology_papers' not found.")
                    print("Run 'python scripts/build_index.py' first.")
                    return

                info = client.get_collection("oncology_papers")
                if info.points_count == 0:
                    print("No papers indexed. Run 'python scripts/build_index.py' first.")
                    return

                print(f"Collection has {info.points_count} vectors\n")

                # Demo query
                query = "EGFR 변이 폐암 환자의 치료 옵션은?"
                print(f"Query: {query}\n")

                response = await pipeline.query_simple(query)

                if response.gate2_passed:
                    print(f"Answer:\n{response.answer}\n")
                    print(f"Evidence: {len(response.evidence)} papers cited")
                    print(f"Citations used: {response.citations_used}")
                    print(f"Processing time: {response.processing_time_ms}ms")
                else:
                    print(f"Gate 2 failed: {response.gate2_details['message']}")

            except Exception as e:
                print(f"Error: {e}")
                print("\nMake sure Qdrant is running and papers are indexed.")

        asyncio.run(demo())
