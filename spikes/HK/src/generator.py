"""
OAR-34: LLM Generator & Prompt Templates Implementation

Generates answers from retrieved context using Claude API.
Enforces citation requirements and safety guidelines.

Author: HK
Created: 2025-12-30
Jira: OAR-34
"""

import os
import time
from dataclasses import dataclass, field
from typing import Optional, Generator, Any


# Lazy import for anthropic
_anthropic = None


def _get_anthropic():
    """Lazy import anthropic client."""
    global _anthropic
    if _anthropic is None:
        try:
            import anthropic
            _anthropic = anthropic
        except ImportError:
            raise ImportError(
                "anthropic required. Install with: pip install anthropic"
            )
    return _anthropic


# ============================================================================
# PROMPT TEMPLATES
# ============================================================================

SYSTEM_PROMPT = """You are OARIA (Oncology AI Research Intelligence Assistant), a specialized assistant for oncology research questions.

## Your Role
You help researchers understand and synthesize information from cancer research papers. You provide evidence-based answers using ONLY the provided paper excerpts.

## Critical Rules

### 1. Citation Requirements
- EVERY factual claim MUST have a citation
- Use format: [1], [2], etc. matching the source numbers
- Never make claims without citation support
- If multiple sources support a claim, cite all: [1][2]

### 2. Honesty About Limitations
- If the provided sources don't contain enough information, say so clearly
- Use phrases like "Based on the provided sources..." or "The available evidence suggests..."
- Never invent or extrapolate beyond what sources state
- If sources conflict, acknowledge the disagreement

### 3. Safety Guidelines
- NEVER provide clinical recommendations or treatment advice
- Always recommend consulting healthcare professionals for medical decisions
- Use academic/research language, not patient-facing advice
- Focus on research findings, mechanisms, and evidence

### 4. Response Format
- Start with a direct answer to the question
- Support with evidence from sources
- Use clear, organized structure
- End with limitations or caveats if applicable

### 5. Language
- Respond in the same language as the user's question
- Use precise scientific terminology
- Explain complex concepts when needed"""


CONTEXT_PROMPT_TEMPLATE = """## Research Context

The following excerpts are from peer-reviewed oncology papers. Use these as your ONLY source of information.

{context}

---

## User Question

{question}

---

## Instructions

Answer the question using ONLY the information from the provided paper excerpts. Follow the citation rules strictly. If the sources don't adequately address the question, clearly state this limitation."""


# ============================================================================
# DATA CLASSES
# ============================================================================

@dataclass
class GeneratorConfig:
    """Configuration for the LLM generator."""
    model: str = "claude-sonnet-4-20250514"
    max_tokens: int = 2048
    temperature: float = 0.3  # Lower for factual accuracy
    top_p: float = 0.9

    # Token budget management
    max_context_tokens: int = 6000  # Reserve for context
    max_question_tokens: int = 500   # Reserve for question


@dataclass
class Citation:
    """A single citation reference."""
    number: int
    paper_id: str
    text_snippet: str
    score: float


@dataclass
class GeneratorOutput:
    """Complete generator output with metadata."""
    answer: str
    citations_used: list[int]
    model: str
    input_tokens: int
    output_tokens: int
    generation_time_ms: float
    context_sources: list[dict]

    def to_dict(self) -> dict:
        return {
            "answer": self.answer,
            "citations_used": self.citations_used,
            "model": self.model,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "generation_time_ms": self.generation_time_ms,
            "context_sources": self.context_sources,
        }


# ============================================================================
# GENERATOR CLASS
# ============================================================================

class LLMGenerator:
    """
    LLM-based answer generator for RAG pipeline.

    Design Decisions:
    -----------------
    1. WHY Claude API?
       - Strong instruction following for citation rules
       - Good at scientific text understanding
       - Streaming support for better UX
       - Consistent output quality

    2. WHY low temperature (0.3)?
       - Higher factual accuracy
       - Less hallucination risk
       - More consistent responses
       - RAG should rely on evidence, not creativity

    3. WHY strict citation format?
       - Enables automated citation linking (OAR-35)
       - User can verify claims
       - Reduces hallucination (forces grounding)
       - Standard academic practice

    4. WHY system/user prompt separation?
       - System prompt sets consistent behavior
       - User prompt contains variable content
       - Better prompt management
       - Easier A/B testing of prompts
    """

    def __init__(
        self,
        config: Optional[GeneratorConfig] = None,
        api_key: Optional[str] = None,
    ):
        """
        Initialize the generator.

        Args:
            config: Generator configuration
            api_key: Anthropic API key (uses ANTHROPIC_API_KEY env var if not provided)
        """
        self.config = config or GeneratorConfig()

        # Get API key
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError(
                "Anthropic API key required. Set ANTHROPIC_API_KEY environment variable "
                "or pass api_key parameter."
            )

        self._client = None

    @property
    def client(self):
        """Lazy load Anthropic client."""
        if self._client is None:
            anthropic = _get_anthropic()
            self._client = anthropic.Anthropic(api_key=self.api_key)
        return self._client

    def _format_context(
        self,
        sources: list[dict],
        max_chars: int = 12000,
    ) -> tuple[str, list[dict]]:
        """
        Format sources into context string.

        Args:
            sources: List of source dicts with text, score, metadata
            max_chars: Maximum context length

        Returns:
            Tuple of (formatted_context, truncated_sources)
        """
        context_parts = []
        included_sources = []
        total_chars = 0

        for i, source in enumerate(sources, 1):
            # Extract fields
            text = source.get("text", "")
            score = source.get("score", source.get("rerank_score", 0))
            paper_id = source.get("paper_id", source.get("metadata", {}).get("paper_id", "unknown"))

            # Format entry
            entry = f"[{i}] Source: {paper_id} (relevance: {score:.2f})\n{text}\n"

            if total_chars + len(entry) > max_chars:
                break

            context_parts.append(entry)
            included_sources.append({
                "number": i,
                "paper_id": paper_id,
                "score": score,
                "text_preview": text[:200] + "..." if len(text) > 200 else text,
            })
            total_chars += len(entry)

        return "\n".join(context_parts), included_sources

    def _build_messages(
        self,
        question: str,
        context: str,
    ) -> list[dict]:
        """Build message list for Claude API."""
        user_content = CONTEXT_PROMPT_TEMPLATE.format(
            context=context,
            question=question,
        )

        return [
            {"role": "user", "content": user_content}
        ]

    def _extract_citations(self, text: str) -> list[int]:
        """Extract citation numbers from generated text."""
        import re
        # Match [1], [2], [1][2], etc.
        pattern = r'\[(\d+)\]'
        matches = re.findall(pattern, text)
        return sorted(set(int(m) for m in matches))

    def generate(
        self,
        question: str,
        sources: list[dict],
        stream: bool = False,
    ) -> GeneratorOutput:
        """
        Generate answer from question and sources.

        Args:
            question: User's question
            sources: Retrieved/reranked sources
            stream: If True, returns generator for streaming

        Returns:
            GeneratorOutput with answer and metadata
        """
        start_time = time.perf_counter()

        # Format context
        context, included_sources = self._format_context(sources)

        # Build messages
        messages = self._build_messages(question, context)

        # Call Claude API
        response = self.client.messages.create(
            model=self.config.model,
            max_tokens=self.config.max_tokens,
            temperature=self.config.temperature,
            top_p=self.config.top_p,
            system=SYSTEM_PROMPT,
            messages=messages,
        )

        generation_time = (time.perf_counter() - start_time) * 1000

        # Extract answer text
        answer = response.content[0].text

        # Extract citations used
        citations_used = self._extract_citations(answer)

        return GeneratorOutput(
            answer=answer,
            citations_used=citations_used,
            model=self.config.model,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            generation_time_ms=generation_time,
            context_sources=included_sources,
        )

    def generate_stream(
        self,
        question: str,
        sources: list[dict],
    ) -> Generator[str, None, GeneratorOutput]:
        """
        Generate answer with streaming.

        Yields text chunks as they're generated.
        Returns full GeneratorOutput at the end.

        Usage:
            gen = generator.generate_stream(question, sources)
            for chunk in gen:
                print(chunk, end="", flush=True)
            output = gen.value  # Full output after iteration
        """
        start_time = time.perf_counter()

        # Format context
        context, included_sources = self._format_context(sources)

        # Build messages
        messages = self._build_messages(question, context)

        # Stream from Claude API
        full_text = []
        input_tokens = 0
        output_tokens = 0

        with self.client.messages.stream(
            model=self.config.model,
            max_tokens=self.config.max_tokens,
            temperature=self.config.temperature,
            system=SYSTEM_PROMPT,
            messages=messages,
        ) as stream:
            for text in stream.text_stream:
                full_text.append(text)
                yield text

            # Get final message for token counts
            final = stream.get_final_message()
            input_tokens = final.usage.input_tokens
            output_tokens = final.usage.output_tokens

        generation_time = (time.perf_counter() - start_time) * 1000
        answer = "".join(full_text)
        citations_used = self._extract_citations(answer)

        # Store output for retrieval after iteration
        output = GeneratorOutput(
            answer=answer,
            citations_used=citations_used,
            model=self.config.model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            generation_time_ms=generation_time,
            context_sources=included_sources,
        )

        return output

    def get_stats(self) -> dict:
        """Get generator statistics."""
        return {
            "model": self.config.model,
            "max_tokens": self.config.max_tokens,
            "temperature": self.config.temperature,
        }


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

def generate_answer(
    question: str,
    sources: list[dict],
    model: str = "claude-sonnet-4-20250514",
) -> str:
    """
    Simple function to generate an answer.

    Args:
        question: User's question
        sources: List of source dicts
        model: Claude model to use

    Returns:
        Generated answer string
    """
    config = GeneratorConfig(model=model)
    generator = LLMGenerator(config=config)
    output = generator.generate(question, sources)
    return output.answer


if __name__ == "__main__":
    print("=== LLM Generator Demo ===\n")

    # Check for API key
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("⚠️  ANTHROPIC_API_KEY not set. Showing prompt structure only.\n")

        # Demo the prompt structure
        sources = [
            {
                "text": "EGFR mutations are found in 15% of NSCLC patients...",
                "paper_id": "W001",
                "score": 0.92,
            },
            {
                "text": "Erlotinib shows 70% response rate in EGFR+ patients...",
                "paper_id": "W002",
                "score": 0.88,
            },
        ]

        question = "What is the efficacy of EGFR inhibitors?"

        # Show formatted prompt
        generator = None
        context_parts = []
        for i, s in enumerate(sources, 1):
            context_parts.append(f"[{i}] Source: {s['paper_id']} (relevance: {s['score']:.2f})\n{s['text']}")
        context = "\n\n".join(context_parts)

        print("=== SYSTEM PROMPT ===")
        print(SYSTEM_PROMPT[:500] + "...\n")

        print("=== USER PROMPT ===")
        print(CONTEXT_PROMPT_TEMPLATE.format(context=context, question=question))

    else:
        # Full demo with API
        generator = LLMGenerator()

        sources = [
            {
                "text": "EGFR mutations, particularly exon 19 deletions and L858R point mutations, are found in approximately 15% of non-small cell lung cancer (NSCLC) patients in Western populations and up to 50% in Asian populations. These mutations predict sensitivity to EGFR tyrosine kinase inhibitors (TKIs).",
                "paper_id": "W001",
                "score": 0.92,
            },
            {
                "text": "First-generation EGFR TKIs such as erlotinib and gefitinib have shown response rates of 60-70% in EGFR-mutant NSCLC, with median progression-free survival of 9-13 months. However, acquired resistance typically develops through T790M mutation.",
                "paper_id": "W002",
                "score": 0.88,
            },
            {
                "text": "Osimertinib, a third-generation EGFR TKI, is effective against both sensitizing mutations and T790M resistance mutation. In the FLAURA trial, osimertinib showed superior overall survival compared to first-generation TKIs.",
                "paper_id": "W003",
                "score": 0.85,
            },
        ]

        question = "What is the efficacy of EGFR inhibitors in lung cancer?"

        print(f"Question: {question}\n")
        print("Generating answer...")

        output = generator.generate(question, sources)

        print(f"\n=== Answer ({output.generation_time_ms:.0f}ms) ===\n")
        print(output.answer)

        print(f"\n=== Metadata ===")
        print(f"Model: {output.model}")
        print(f"Tokens: {output.input_tokens} in, {output.output_tokens} out")
        print(f"Citations used: {output.citations_used}")
