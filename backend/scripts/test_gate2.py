#!/usr/bin/env python3
"""Test script for Gate 2: Retrieval Confidence (OAR-12).

Run from backend directory:
    python scripts/test_gate2.py

Tests:
    1. Gate 2 validation with mock references
    2. Each failure scenario (low similarity, insufficient docs, domain mismatch)
    3. Integration with RAG service (requires Weaviate)
"""

import os
import sys

# Add parent to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()


def test_gate2_unit():
    """Test Gate 2 validation with mock references."""
    from app.services.gates import gate2_service, Gate2Result
    from app.services.gates.gate2_retrieval import Gate2FailReason
    from app.schemas.chat import Reference

    print("\n=== Gate 2 Unit Tests ===\n")

    # Test 1: Should PASS - Good quality results
    print("Test 1: Good quality results (should PASS)")
    good_refs = [
        Reference(
            paper_id="1", chunk_id="1", title="EGFR mutations in lung cancer",
            journal="Nature", year=2024, section="Abstract",
            snippet="EGFR mutations are a major driver of lung cancer...",
            offset_start=0, offset_end=100, distance=0.85
        ),
        Reference(
            paper_id="2", chunk_id="2", title="Targeted therapy for tumor treatment",
            journal="Cell", year=2023, section="Methods",
            snippet="Chemotherapy combined with immunotherapy...",
            offset_start=0, offset_end=100, distance=0.75
        ),
        Reference(
            paper_id="3", chunk_id="3", title="Oncology advances in carcinoma",
            journal="Science", year=2024, section="Results",
            snippet="Melanoma treatment shows significant improvement...",
            offset_start=0, offset_end=100, distance=0.70
        ),
    ]
    result = gate2_service.validate(good_refs)
    status = "PASS" if result.passed else "FAIL"
    print(f"  Result: {status}")
    print(f"  Max similarity: {result.max_similarity:.2f}")
    print(f"  Relevant docs: {result.relevant_count}")
    print(f"  Oncology ratio: {result.oncology_ratio:.0%}")
    assert result.passed, "Expected to pass but failed!"
    print("  [OK]\n")

    # Test 2: Should FAIL - Low similarity
    print("Test 2: Low similarity results (should FAIL)")
    low_sim_refs = [
        Reference(
            paper_id="1", chunk_id="1", title="Cancer research study",
            journal="Nature", year=2024, section="Abstract",
            snippet="Tumor growth patterns...",
            offset_start=0, offset_end=100, distance=0.50  # Below 0.7 threshold
        ),
        Reference(
            paper_id="2", chunk_id="2", title="Oncology findings",
            journal="Cell", year=2023, section="Methods",
            snippet="Cancer treatment methods...",
            offset_start=0, offset_end=100, distance=0.45
        ),
    ]
    result = gate2_service.validate(low_sim_refs)
    status = "PASS" if result.passed else "FAIL"
    print(f"  Result: {status}")
    print(f"  Max similarity: {result.max_similarity:.2f}")
    print(f"  Reason: {result.reason}")
    print(f"  Message: {result.message}")
    assert not result.passed, "Expected to fail but passed!"
    assert result.reason == Gate2FailReason.LOW_SIMILARITY, f"Wrong reason: {result.reason}"
    print("  [OK]\n")

    # Test 3: Should FAIL - Insufficient docs
    print("Test 3: Insufficient relevant docs (should FAIL)")
    few_refs = [
        Reference(
            paper_id="1", chunk_id="1", title="Cancer treatment advances",
            journal="Nature", year=2024, section="Abstract",
            snippet="Tumor immunotherapy shows promise...",
            offset_start=0, offset_end=100, distance=0.85  # High similarity
        ),
        Reference(
            paper_id="2", chunk_id="2", title="Oncology research",
            journal="Cell", year=2023, section="Methods",
            snippet="Chemotherapy resistance in cancer...",
            offset_start=0, offset_end=100, distance=0.55  # Below 0.6
        ),
    ]
    result = gate2_service.validate(few_refs)
    status = "PASS" if result.passed else "FAIL"
    print(f"  Result: {status}")
    print(f"  Relevant docs: {result.relevant_count} (need >= 3)")
    print(f"  Reason: {result.reason}")
    print(f"  Message: {result.message}")
    assert not result.passed, "Expected to fail but passed!"
    assert result.reason == Gate2FailReason.INSUFFICIENT_DOCS, f"Wrong reason: {result.reason}"
    print("  [OK]\n")

    # Test 4: Should FAIL - Domain mismatch
    print("Test 4: Off-domain results (should FAIL)")
    off_domain_refs = [
        Reference(
            paper_id="1", chunk_id="1", title="Machine learning for image recognition",
            journal="Nature", year=2024, section="Abstract",
            snippet="Deep learning algorithms demonstrate remarkable accuracy...",
            offset_start=0, offset_end=100, distance=0.85
        ),
        Reference(
            paper_id="2", chunk_id="2", title="Neural network architectures",
            journal="Cell", year=2023, section="Methods",
            snippet="Transformer models have revolutionized NLP...",
            offset_start=0, offset_end=100, distance=0.80
        ),
        Reference(
            paper_id="3", chunk_id="3", title="Computer vision advances",
            journal="Science", year=2024, section="Results",
            snippet="Convolutional networks for object detection...",
            offset_start=0, offset_end=100, distance=0.75
        ),
        Reference(
            paper_id="4", chunk_id="4", title="Data science methodologies",
            journal="PNAS", year=2024, section="Discussion",
            snippet="Big data analytics in healthcare...",
            offset_start=0, offset_end=100, distance=0.70
        ),
    ]
    result = gate2_service.validate(off_domain_refs)
    status = "PASS" if result.passed else "FAIL"
    print(f"  Result: {status}")
    print(f"  Oncology ratio: {result.oncology_ratio:.0%} (need >= 80%)")
    print(f"  Reason: {result.reason}")
    print(f"  Message: {result.message}")
    assert not result.passed, "Expected to fail but passed!"
    assert result.reason == Gate2FailReason.DOMAIN_MISMATCH, f"Wrong reason: {result.reason}"
    print("  [OK]\n")

    print("All unit tests passed!")


def test_gate2_integration():
    """Test Gate 2 with real RAG search (requires Weaviate)."""
    from app.services.rag_service import rag_service
    from app.services.gates import gate2_service

    print("\n=== Gate 2 Integration Test ===\n")

    queries = [
        ("EGFR 변이 폐암 치료", "Should PASS - oncology query"),
        ("머신러닝 알고리즘", "Might FAIL - off-domain query"),
    ]

    for query, description in queries:
        print(f"Query: {query}")
        print(f"  ({description})")

        try:
            retrieval_result = rag_service.retrieve(query)
            print(f"  Retrieved {len(retrieval_result.references)} references")

            gate2_result = gate2_service.validate(retrieval_result.references)

            status = "PASSED" if gate2_result.passed else "FAILED"
            print(f"  Gate 2: {status}")
            print(f"    Max similarity: {gate2_result.max_similarity:.2f}")
            print(f"    Relevant docs: {gate2_result.relevant_count}")
            print(f"    Oncology ratio: {gate2_result.oncology_ratio:.0%}")

            if not gate2_result.passed:
                print(f"    Reason: {gate2_result.reason}")
                print(f"    Message: {gate2_result.message}")
        except Exception as e:
            print(f"  Error: {e}")
        print()


def test_gate2_in_agent():
    """Test Gate 2 within full agent execution."""
    from app.services.agent import agent_service

    print("\n=== Gate 2 in Agent Workflow ===\n")

    query = "EGFR 변이 폐암 환자에서 표적치료제의 효과는?"
    print(f"Query: {query}\n")

    print("Executing agent (streaming)...")

    events_seen = []
    for event in agent_service.execute_stream(query):
        events_seen.append(event.event_type)
        if event.event_type == "gate2":
            print(f"\n  Gate 2 Event:")
            print(f"    Task: {event.data.get('task_id')}")
            print(f"    Passed: {event.data.get('passed')}")
            if not event.data.get("passed"):
                print(f"    Reason: {event.data.get('reason')}")
                print(f"    Message: {event.data.get('message')}")
        elif event.event_type == "status":
            print(f"  Status: {event.data.get('message')}")
        elif event.event_type == "complexity":
            print(f"  Complexity: {event.data.get('level')}")
        elif event.event_type == "token":
            pass  # Skip token streaming for cleaner output

    print(f"\nEvents seen: {set(events_seen)}")
    print(f"Gate 2 event emitted: {'gate2' in events_seen}")


def main():
    print("=" * 60)
    print("OARIA Gate 2: Retrieval Confidence Test (OAR-12)")
    print("=" * 60)

    # Unit tests (no external dependencies)
    test_gate2_unit()

    # Integration tests (require Weaviate)
    print("\n" + "=" * 60)
    print("Integration Tests (require Weaviate)")
    print("=" * 60)

    run_integration = input("\nRun integration tests? (y/n): ").lower().strip()
    if run_integration == "y":
        try:
            test_gate2_integration()
        except Exception as e:
            print(f"Integration test failed: {e}")

        run_agent = input("\nRun agent workflow test? (y/n): ").lower().strip()
        if run_agent == "y":
            try:
                test_gate2_in_agent()
            except Exception as e:
                print(f"Agent test failed: {e}")
    else:
        print("\nSkipping integration tests.")
        print("Run manually with: test_gate2_integration() or test_gate2_in_agent()")


if __name__ == "__main__":
    main()
