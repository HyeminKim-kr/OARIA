"""Complexity Analyzer node (OAR-47)."""

import json
import logging

from openai import OpenAI

from app.config import settings
from ..state import AgentState, ComplexityLevel
from ..prompts import COMPLEXITY_ANALYZER_SYSTEM, COMPLEXITY_ANALYZER_USER

logger = logging.getLogger(__name__)


def analyze_complexity(state: AgentState) -> AgentState:
    """
    Analyze query complexity and classify as simple/medium/complex.

    This node uses GPT-4o-mini to analyze the query and determine
    the appropriate processing path.

    Args:
        state: Current agent state with query

    Returns:
        Updated state with complexity and complexity_reasoning
    """
    query = state["query"]
    logger.info(f"Analyzing complexity for query: {query[:100]}...")

    # Use OpenAI to classify complexity
    client = OpenAI(api_key=settings.openai_api_key)

    try:
        response = client.chat.completions.create(
            model=settings.openai_chat_model,
            messages=[
                {"role": "system", "content": COMPLEXITY_ANALYZER_SYSTEM},
                {"role": "user", "content": COMPLEXITY_ANALYZER_USER.format(query=query)},
            ],
            temperature=0.1,  # Low temperature for consistent classification
            response_format={"type": "json_object"},
        )

        result = json.loads(response.choices[0].message.content)
        complexity_str = result.get("complexity", "simple").lower()
        reasoning = result.get("reasoning", "")

        # Map to enum
        complexity_map = {
            "simple": ComplexityLevel.SIMPLE,
            "medium": ComplexityLevel.MEDIUM,
            "complex": ComplexityLevel.COMPLEX,
        }
        complexity = complexity_map.get(complexity_str, ComplexityLevel.SIMPLE)

        logger.info(f"Query classified as {complexity.value}: {reasoning[:100]}...")

        return {
            "complexity": complexity,
            "complexity_reasoning": reasoning,
        }

    except Exception as e:
        logger.error(f"Error analyzing complexity: {e}")
        # Default to simple on error
        return {
            "complexity": ComplexityLevel.SIMPLE,
            "complexity_reasoning": f"Error during analysis, defaulting to simple: {str(e)}",
        }
