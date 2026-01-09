#!/usr/bin/env python3
"""Integration test for F-04 Agent Task Decomposition.

Run with: python scripts/test_agent_integration.py

Requires:
- Weaviate running on localhost:18080
- OpenAI API key configured
- Papers indexed in Weaviate
"""

import os
import sys
import time

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()


def check_prerequisites():
    """Check if all services are available."""
    print("=" * 60)
    print("Checking prerequisites...")
    print("=" * 60)

    errors = []

    # Check OpenAI API key
    api_key = os.getenv("OPENAI_API_KEY", "")
    if not api_key or api_key.startswith("sk-your"):
        errors.append("OPENAI_API_KEY not configured (found placeholder)")
    else:
        print(f"✓ OpenAI API key configured ({api_key[:10]}...)")

    # Check Weaviate connection
    try:
        import weaviate
        client = weaviate.connect_to_local(
            host=os.getenv("WEAVIATE_HOST", "localhost"),
            port=int(os.getenv("WEAVIATE_PORT", "18080")),
        )
        if client.is_ready():
            print("✓ Weaviate is running")

            # Check for papers collection
            collections = client.collections.list_all()
            if "Paper" in collections or "PaperChunk" in collections:
                print("✓ Paper/PaperChunk collection exists")
            else:
                print(f"⚠ Available collections: {list(collections.keys())}")
            client.close()
        else:
            errors.append("Weaviate is not ready")
    except Exception as e:
        errors.append(f"Cannot connect to Weaviate: {e}")

    if errors:
        print("\n❌ Prerequisites not met:")
        for err in errors:
            print(f"  - {err}")
        return False

    print("\n✓ All prerequisites met!")
    return True


def test_simple_query():
    """Test a simple query (should go direct to RAG)."""
    print("\n" + "=" * 60)
    print("Test 1: Simple Query")
    print("=" * 60)

    from app.services.agent import agent_service

    query = "EGFR이란 무엇인가?"
    print(f"Query: {query}")
    print("-" * 40)

    start = time.perf_counter()
    result = agent_service.execute(query)
    duration = time.perf_counter() - start

    print(f"Complexity: {result.complexity}")
    print(f"Subtasks: {len(result.subtasks)}")
    print(f"References: {len(result.references)}")
    print(f"Duration: {duration:.2f}s")
    print(f"\nAnswer preview:\n{result.answer[:500]}...")

    assert result.answer, "Answer should not be empty"
    assert result.complexity.value == "simple", f"Expected simple, got {result.complexity}"
    print("\n✓ Simple query test PASSED")
    return True


def test_complex_query():
    """Test a complex query (should decompose into subtasks)."""
    print("\n" + "=" * 60)
    print("Test 2: Complex Query (Task Decomposition)")
    print("=" * 60)

    from app.services.agent import agent_service

    query = "EGFR 변이와 TP53 변이가 동시에 있는 비소세포폐암 환자에서 1차 치료와 2차 치료의 효과를 비교해주세요"
    print(f"Query: {query}")
    print("-" * 40)

    start = time.perf_counter()
    result = agent_service.execute(query)
    duration = time.perf_counter() - start

    print(f"Complexity: {result.complexity}")
    print(f"Complexity Reasoning: {result.agent_execution.get('complexity_reasoning', '')[:100]}...")
    print(f"Subtasks: {len(result.subtasks)}")

    if result.subtasks:
        print("\nDecomposed tasks:")
        for task in result.subtasks:
            print(f"  - {task.id}: {task.query[:50]}... (tool: {task.tool})")

    print(f"\nReferences: {len(result.references)}")
    print(f"Duration: {duration:.2f}s")
    print(f"\nAnswer preview:\n{result.answer[:500]}...")

    assert result.answer, "Answer should not be empty"
    # Complex query should be classified as medium or complex
    assert result.complexity.value in ["medium", "complex"], f"Expected medium/complex, got {result.complexity}"
    print("\n✓ Complex query test PASSED")
    return True


def test_streaming():
    """Test streaming execution with events."""
    print("\n" + "=" * 60)
    print("Test 3: Streaming Execution")
    print("=" * 60)

    from app.services.agent import agent_service

    query = "면역항암제의 작용 메커니즘을 설명해주세요"
    print(f"Query: {query}")
    print("-" * 40)

    events = []
    start = time.perf_counter()

    # Collect events from streaming
    for event in agent_service.execute_stream(query):
        events.append(event)
        print(f"  Event: {event.event_type} - {str(event.data)[:80]}...")

    duration = time.perf_counter() - start

    print(f"\nTotal events: {len(events)}")
    print(f"Duration: {duration:.2f}s")

    # Check we got expected event types
    event_types = [e.event_type for e in events]
    assert "status" in event_types, "Should have status events"
    assert "complexity" in event_types, "Should have complexity event"

    print("\n✓ Streaming test PASSED")
    return True


def main():
    """Run all integration tests."""
    print("\n" + "=" * 60)
    print("F-04 Agent Integration Test")
    print("=" * 60)

    # Check prerequisites
    if not check_prerequisites():
        print("\n⚠ Skipping tests due to missing prerequisites")
        print("Please configure OPENAI_API_KEY in .env file")
        return 1

    results = []

    # Run tests
    try:
        results.append(("Simple Query", test_simple_query()))
    except Exception as e:
        print(f"\n❌ Simple query test FAILED: {e}")
        import traceback
        traceback.print_exc()
        results.append(("Simple Query", False))

    try:
        results.append(("Complex Query", test_complex_query()))
    except Exception as e:
        print(f"\n❌ Complex query test FAILED: {e}")
        import traceback
        traceback.print_exc()
        results.append(("Complex Query", False))

    try:
        results.append(("Streaming", test_streaming()))
    except Exception as e:
        print(f"\n❌ Streaming test FAILED: {e}")
        import traceback
        traceback.print_exc()
        results.append(("Streaming", False))

    # Summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)

    passed = sum(1 for _, r in results if r)
    total = len(results)

    for name, result in results:
        status = "✓ PASSED" if result else "❌ FAILED"
        print(f"  {name}: {status}")

    print(f"\nTotal: {passed}/{total} passed")

    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
