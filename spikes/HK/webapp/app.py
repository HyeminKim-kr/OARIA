"""
OARIA Web Application

A modern web interface for oncology research paper discovery and AI-assisted Q&A.
Built with FastAPI + Tailwind CSS + Alpine.js.

Author: HK
Created: 2025-01-06
"""

import os
import sys
import logging
import re
from typing import Optional
from datetime import datetime

from fastapi import FastAPI, Request, Query, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.rag.retriever import HybridRetriever
from src.rag.embedder import BGEM3Embedder

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI
app = FastAPI(
    title="OARIA",
    description="Oncology AI Research Intelligence Assistant",
    version="1.0.0",
)

# Templates and static files
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "templates"))
app.mount("/static", StaticFiles(directory=os.path.join(os.path.dirname(__file__), "static")), name="static")

# Global retriever and OpenAI client (lazy loaded)
_retriever: Optional[HybridRetriever] = None
_openai_client = None


def get_retriever() -> HybridRetriever:
    """Get or create retriever instance."""
    global _retriever
    if _retriever is None:
        logger.info("Initializing HybridRetriever...")
        _retriever = HybridRetriever()
        logger.info("HybridRetriever ready")
    return _retriever


def get_openai_client():
    """Get or create OpenAI client."""
    global _openai_client
    if _openai_client is None:
        api_key = os.getenv("OPENAI_API_KEY")
        if api_key:
            try:
                from openai import OpenAI
                _openai_client = OpenAI(api_key=api_key)
                logger.info("OpenAI client initialized")
            except ImportError:
                logger.warning("openai package not installed. Run: pip install openai")
        else:
            logger.warning("OPENAI_API_KEY not set in .env file")
    return _openai_client


# =============================================================================
# LLM PROMPTS
# =============================================================================

SYSTEM_PROMPT = """You are OARIA, an oncology research AI assistant.

Your role is to answer questions about cancer science, treatments, and prognosis
based ONLY on the research papers provided to you.

Core Principles:
1. EVIDENCE-BASED: Every claim must be supported by the provided papers
2. CITATIONS: Use [1], [2], etc. to cite sources inline
3. HONEST UNCERTAINTY: Say "the provided papers don't address this" when applicable
4. NO HALLUCINATION: Never make up facts, statistics, or citations
5. NO MEDICAL ADVICE: Do not give clinical recommendations or treatment advice

Writing Style:
- Clear and accessible, but academically rigorous
- Use precise terminology with brief explanations for complex terms
- Present multiple perspectives if papers disagree
- Quantify claims when possible (with citations)
- Structure your answer with clear sections if the topic is complex

Format your response in markdown with:
- **Bold** for key terms
- Bullet points for lists
- Clear paragraph breaks"""


def build_context(sources: list, context_parts: list) -> str:
    """Build context string for LLM."""
    context = "RESEARCH PAPERS:\n\n"
    for i, (src, text) in enumerate(zip(sources, context_parts), 1):
        context += f"[{i}] {src.get('title', 'Untitled')}\n"
        context += f"    Journal: {src.get('journal', 'Unknown')} | Year: {src.get('year', 'Unknown')}\n"
        context += f"    Content: {text}\n\n"
    return context


async def generate_answer_openai(question: str, context: str, sources: list) -> str:
    """Generate answer using OpenAI API."""
    client = get_openai_client()

    if not client:
        return generate_fallback_answer(question, context, sources)

    model = os.getenv("OPENAI_MODEL", "gpt-4o")

    user_prompt = f"""Based on the following research papers, answer this question:

QUESTION: {question}

{context}

Please provide a comprehensive answer with inline citations [1], [2], etc. referring to the paper numbers above."""

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt}
            ],
            max_tokens=1500,
            temperature=0.3,  # Lower temperature for more factual responses
        )

        answer = response.choices[0].message.content
        logger.info(f"OpenAI response generated: {len(answer)} chars, model={model}")
        return answer

    except Exception as e:
        logger.error(f"OpenAI API error: {e}")
        return generate_fallback_answer(question, context, sources)


def generate_fallback_answer(question: str, context: str, sources: list) -> str:
    """Fallback answer when OpenAI is not available."""
    if not sources:
        return "I couldn't find relevant papers to answer this question. Please try rephrasing or asking about a different oncology topic."

    answer = f"**Found {len(sources)} relevant papers for your question.**\n\n"
    answer += "**Key excerpts from the research:**\n\n"

    # Show first 3 sources with excerpts
    for i, src in enumerate(sources[:3], 1):
        answer += f"[{i}] **{src.get('title', 'Untitled')}**\n"
        answer += f"   _{src.get('journal', 'Unknown')}_ ({src.get('year', 'N/A')})\n\n"

    answer += "\n---\n"
    answer += "_Note: Set your OPENAI_API_KEY in the .env file to enable AI-generated answers with full analysis._"

    return answer


# Pydantic models
class SearchRequest(BaseModel):
    query: str
    top_k: int = 10
    min_year: Optional[int] = None
    max_year: Optional[int] = None
    min_citations: Optional[int] = None
    sources: Optional[list[str]] = None
    journal_tiers: Optional[list[str]] = None


class AskRequest(BaseModel):
    question: str
    top_k: int = 5


class PaperResult(BaseModel):
    id: str
    title: str
    abstract: str
    authors: list[str]
    journal: Optional[str]
    journal_tier: Optional[str]
    publication_year: Optional[int]
    cited_by_count: Optional[int]
    doi: Optional[str]
    pmid: Optional[str]
    source: Optional[str]
    score: float


# Routes
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Home page with search."""
    return templates.TemplateResponse("index.html", {
        "request": request,
        "title": "OARIA - Oncology Research Assistant",
    })


@app.get("/explore", response_class=HTMLResponse)
async def explore(request: Request):
    """Explore papers page."""
    retriever = get_retriever()

    # Get recent/popular papers
    results = retriever.search(
        "cancer oncology treatment therapy",
        top_k=20,
        min_year=2020,
    )

    # Deduplicate by paper_id
    seen_papers = set()
    papers = []
    for r in results.results:
        if r.paper_id and r.paper_id not in seen_papers:
            seen_papers.add(r.paper_id)
            papers.append({
                "id": r.paper_id,
                "title": clean_html(r.title or "Untitled"),
                "text": r.text[:300] + "..." if len(r.text) > 300 else r.text,
                "journal": r.journal,
                "journal_tier": r.journal_tier,
                "year": r.publication_year,
                "citations": r.cited_by_count or 0,
                "source": r.source,
                "doi": r.doi,
                "score": r.score,
            })

    return templates.TemplateResponse("explore.html", {
        "request": request,
        "title": "Explore Papers - OARIA",
        "papers": papers[:15],
    })


@app.get("/assistant", response_class=HTMLResponse)
async def assistant(request: Request):
    """AI Assistant chat page."""
    return templates.TemplateResponse("assistant.html", {
        "request": request,
        "title": "AI Assistant - OARIA",
    })


@app.get("/api/search")
async def api_search(
    q: str = Query(..., description="Search query"),
    top_k: int = Query(10, ge=1, le=50),
    min_year: Optional[int] = Query(None),
    max_year: Optional[int] = Query(None),
    min_citations: Optional[int] = Query(None),
    source: Optional[str] = Query(None),
    tier: Optional[str] = Query(None),
):
    """Search papers API endpoint."""
    try:
        retriever = get_retriever()

        # Parse filters
        sources = [source] if source else None
        tiers = [tier] if tier else None

        results = retriever.search(
            query=q,
            top_k=top_k,
            min_year=min_year,
            max_year=max_year,
            min_citations=min_citations,
            sources=sources,
            journal_tiers=tiers,
        )

        # Deduplicate and format
        seen_papers = set()
        papers = []
        for r in results.results:
            if r.paper_id and r.paper_id not in seen_papers:
                seen_papers.add(r.paper_id)
                papers.append({
                    "id": r.paper_id,
                    "title": clean_html(r.title or "Untitled"),
                    "text": r.text[:400] + "..." if len(r.text) > 400 else r.text,
                    "journal": r.journal,
                    "journal_tier": r.journal_tier,
                    "year": r.publication_year,
                    "citations": r.cited_by_count or 0,
                    "source": r.source,
                    "doi": r.doi,
                    "pmid": r.pmid,
                    "score": round(r.score, 4),
                })

        return {
            "query": q,
            "total": len(papers),
            "retrieval_time_ms": round(results.retrieval_time_ms, 1),
            "papers": papers,
        }

    except Exception as e:
        logger.error(f"Search error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/ask")
async def api_ask(request: AskRequest):
    """AI Assistant endpoint - retrieves relevant papers and generates answer."""
    try:
        retriever = get_retriever()

        results = retriever.search(
            query=request.question,
            top_k=request.top_k,
        )

        # Build context from retrieved chunks
        context_parts = []
        sources = []
        seen_papers = set()

        for i, r in enumerate(results.results, 1):
            if r.paper_id not in seen_papers:
                seen_papers.add(r.paper_id)
                context_parts.append(r.text)
                sources.append({
                    "id": len(sources) + 1,
                    "paper_id": r.paper_id,
                    "title": clean_html(r.title or "Untitled"),
                    "journal": r.journal,
                    "year": r.publication_year,
                    "doi": r.doi,
                })

        # Build context string
        context = build_context(sources, context_parts)

        # Generate answer using OpenAI
        answer = await generate_answer_openai(request.question, context, sources)

        return {
            "question": request.question,
            "sources": sources,
            "answer": answer,
            "retrieval_time_ms": round(results.retrieval_time_ms, 1),
        }

    except Exception as e:
        logger.error(f"Ask error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/stats")
async def api_stats():
    """Get collection statistics."""
    try:
        retriever = get_retriever()
        info = retriever.qdrant.get_collection(retriever.COLLECTION_NAME)

        # Check if OpenAI is configured
        openai_status = "configured" if os.getenv("OPENAI_API_KEY") else "not configured"

        return {
            "collection": retriever.COLLECTION_NAME,
            "total_chunks": info.points_count,
            "status": info.status.value,
            "openai": openai_status,
        }
    except Exception as e:
        return {"error": str(e)}


def clean_html(text: str) -> str:
    """Remove HTML tags from text."""
    return re.sub(r'<[^>]+>', '', text)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
