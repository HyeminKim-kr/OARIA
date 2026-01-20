#!/usr/bin/env python3
"""Live test script for Agent service (no auth required).

Run from backend directory:
    python scripts/test_agent_live.py
"""

import os
import sys

# Add parent to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()


def main():
    print("=" * 60)
    print("OARIA Agent Service - Live Test")
    print("=" * 60)

    # Check OpenAI API key
    if not os.getenv("OPENAI_API_KEY"):
        print("\n⚠️  Warning: OPENAI_API_KEY not set")
        return

    from app.services.agent import agent_service

    # Test query
    query = "EGFR이란 무엇인가?"
    print(f"\n📝 Query: {query}\n")
    print("🔄 Executing agent...\n")

    try:
        result = agent_service.execute(query)

        print(f"✓ Complexity: {result.complexity.value}")
        print(f"✓ Subtasks: {len(result.subtasks)}")

        if result.subtasks:
            print("\n📋 Subtasks:")
            for task in result.subtasks:
                status_icon = "✓" if task.status == "completed" else "○"
                print(f"  {status_icon} [{task.id}] {task.query} ({task.tool})")

        print(f"\n📚 References: {len(result.references)}")
        if result.references:
            for i, ref in enumerate(result.references[:3], 1):
                print(f"  {i}. {ref.title[:60]}...")

        print(f"\n⏱️  Duration: {result.total_duration_ms}ms")

        print("\n" + "=" * 60)
        print("📄 Answer:")
        print("=" * 60)
        print(result.answer[:1500] if len(result.answer) > 1500 else result.answer)
        if len(result.answer) > 1500:
            print("\n... (truncated)")

    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
