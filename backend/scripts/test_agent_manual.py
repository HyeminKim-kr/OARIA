#!/usr/bin/env python3
"""Manual test script for Agent service.

Run from backend directory:
    python scripts/test_agent_manual.py

Requires:
    - Python 3.11+
    - OpenAI API key in environment
    - Weaviate running (for RAG search)
"""

import os
import sys

# Add parent to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()


def test_complexity_analysis():
    """Test complexity analyzer with different queries."""
    from app.services.agent.nodes.complexity_analyzer import analyze_complexity

    queries = [
        ("EGFR이란 무엇인가?", "simple"),
        ("EGFR 변이 폐암의 표적치료제는?", "medium"),
        ("EGFR+TP53 이중 변이 환자의 1차 치료 vs 2차 치료 효과 비교", "complex"),
    ]

    print("\n=== Complexity Analysis Test ===\n")

    for query, expected in queries:
        state = {"query": query}
        result = analyze_complexity(state)

        status = "✓" if result["complexity"].value == expected else "✗"
        print(f"{status} Query: {query[:50]}...")
        print(f"  Expected: {expected}")
        print(f"  Got: {result['complexity'].value}")
        print(f"  Reasoning: {result['complexity_reasoning'][:100]}...")
        print()


def test_task_decomposition():
    """Test task decomposer with a complex query."""
    from app.services.agent.nodes.task_decomposer import decompose_tasks
    from app.services.agent.state import ComplexityLevel

    print("\n=== Task Decomposition Test ===\n")

    state = {
        "query": "EGFR+TP53 이중 변이 환자의 1차 치료 vs 2차 치료 효과 비교",
        "complexity": ComplexityLevel.COMPLEX,
        "complexity_reasoning": "Multiple conditions and comparison required",
    }

    result = decompose_tasks(state)

    print(f"Decomposed into {len(result['subtasks'])} tasks:")
    for task in result["subtasks"]:
        deps = f" (depends on: {task.depends_on})" if task.depends_on else ""
        print(f"  - [{task.id}] {task.query} ({task.tool.value}){deps}")

    print(f"\nExecution plan: {result['execution_plan']}")


def test_full_agent():
    """Test full agent execution."""
    from app.services.agent import agent_service

    print("\n=== Full Agent Test ===\n")

    query = "EGFR 변이 폐암 환자에서 면역항암제의 효과는?"
    print(f"Query: {query}\n")

    print("Executing agent...")
    result = agent_service.execute(query)

    print(f"\nComplexity: {result.complexity.value}")
    print(f"Subtasks: {len(result.subtasks)}")
    print(f"References: {len(result.references)}")
    print(f"Duration: {result.total_duration_ms}ms")
    print(f"\nAnswer preview: {result.answer[:500]}...")


def main():
    print("=" * 60)
    print("OARIA Agent Service Manual Test")
    print("=" * 60)

    # Check OpenAI API key
    if not os.getenv("OPENAI_API_KEY"):
        print("\n⚠️  Warning: OPENAI_API_KEY not set")
        print("   Set it with: export OPENAI_API_KEY=sk-...")
        return

    try:
        test_complexity_analysis()
    except Exception as e:
        print(f"✗ Complexity test failed: {e}")

    try:
        test_task_decomposition()
    except Exception as e:
        print(f"✗ Decomposition test failed: {e}")

    # Full agent test requires Weaviate
    print("\n⚠️  Skipping full agent test (requires Weaviate)")
    print("   Run manually with: test_full_agent()")


if __name__ == "__main__":
    main()
