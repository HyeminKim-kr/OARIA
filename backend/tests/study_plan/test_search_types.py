"""Tests for Study Plan Agent v3 search types.

Run with: pytest tests/study_plan/test_search_types.py -v
"""

import pytest

from app.services.agent.study_plan.shared.search.types import (
    SearchTier,
    SearchObjective,
    ClaimType,
    EvidenceSnippetV3,
    DP1RouterInput,
    DP1RouterOutput,
    DP2RouterInput,
    DP2RouterOutput,
    DP3RouterInput,
    DP3RouterOutput,
    QueryPlan,
)


# ─────────────────────────────────────────────────────────────
# SearchTier Tests
# ─────────────────────────────────────────────────────────────


def test_search_tier_enum():
    """Test SearchTier enum values."""
    assert SearchTier.RAG.value == 1
    assert SearchTier.EPMC.value == 2
    assert SearchTier.WEB.value == 3


def test_search_tier_ordering():
    """Test SearchTier can be compared."""
    assert SearchTier.RAG.value < SearchTier.EPMC.value
    assert SearchTier.EPMC.value < SearchTier.WEB.value


# ─────────────────────────────────────────────────────────────
# SearchObjective Tests
# ─────────────────────────────────────────────────────────────


def test_search_objective_enum():
    """Test SearchObjective enum values."""
    assert SearchObjective.MECHANISM.value == "mechanism"
    assert SearchObjective.PROTOCOL_CONTROLS.value == "protocol_controls"
    assert SearchObjective.EVIDENCE_STRENGTH.value == "evidence_strength"


# ─────────────────────────────────────────────────────────────
# ClaimType Tests
# ─────────────────────────────────────────────────────────────


def test_claim_type_enum():
    """Test ClaimType enum values."""
    assert ClaimType.MECHANISM.value == "mechanism"
    assert ClaimType.PROTOCOL.value == "protocol"
    assert ClaimType.CONTROL.value == "control"
    assert ClaimType.MEASUREMENT.value == "measurement"
    assert ClaimType.RESULT.value == "result"


# ─────────────────────────────────────────────────────────────
# EvidenceSnippetV3 Tests
# ─────────────────────────────────────────────────────────────


def test_evidence_snippet_v3_creation():
    """Test EvidenceSnippetV3 dataclass creation."""
    snippet = EvidenceSnippetV3(
        snippet_id="snip_001",
        text="EGFR T790M mutation causes drug resistance",
        source_tier=SearchTier.EPMC,
        source_tool="europe_pmc",
        claim_type=ClaimType.MECHANISM,
        paper_id="PMC12345",
        title="Test Paper Title",
        relevance_score=0.85,
    )

    assert snippet.snippet_id == "snip_001"
    assert snippet.source_tier == SearchTier.EPMC
    assert snippet.claim_type == ClaimType.MECHANISM
    assert snippet.relevance_score == 0.85


def test_evidence_snippet_v3_to_dict():
    """Test EvidenceSnippetV3 to_dict method."""
    snippet = EvidenceSnippetV3(
        snippet_id="snip_001",
        text="Test text content",
        source_tier=SearchTier.RAG,
        source_tool="weaviate",
        claim_type=ClaimType.PROTOCOL,
        paper_id="paper_123",
        title="Test Title",
        relevance_score=0.9,
    )

    result = snippet.to_dict()

    assert result["snippet_id"] == "snip_001"
    assert result["source_tier"] == 1  # RAG = 1
    assert result["source_tool"] == "weaviate"
    assert result["claim_type"] == "protocol"
    assert result["relevance_score"] == 0.9


def test_evidence_snippet_v3_from_dict():
    """Test EvidenceSnippetV3 from_dict method."""
    data = {
        "snippet_id": "snip_002",
        "text": "Another text content",
        "source_tier": 2,  # EPMC
        "source_tool": "europe_pmc",
        "claim_type": "protocol",
        "paper_id": "PMC67890",
        "title": "Another Paper",
        "relevance_score": 0.75,
    }

    snippet = EvidenceSnippetV3.from_dict(data)

    assert snippet.snippet_id == "snip_002"
    assert snippet.source_tier == SearchTier.EPMC
    assert snippet.claim_type == ClaimType.PROTOCOL


# ─────────────────────────────────────────────────────────────
# QueryPlan Tests
# ─────────────────────────────────────────────────────────────


def test_query_plan_creation():
    """Test QueryPlan dataclass creation."""
    plan = QueryPlan(
        objective=SearchObjective.MECHANISM,
        primary_query="EGFR T790M mutation treatment",
        fallback_queries=["osimertinib resistance", "MET amplification"],
        filters={"year_from": 2020, "open_access_only": True},
    )

    assert plan.primary_query == "EGFR T790M mutation treatment"
    assert len(plan.fallback_queries) == 2
    assert plan.filters["year_from"] == 2020


def test_query_plan_to_dict():
    """Test QueryPlan to_dict method."""
    plan = QueryPlan(
        objective=SearchObjective.PROTOCOL_CONTROLS,
        primary_query="Test query",
        fallback_queries=[],
        filters={},
    )

    result = plan.to_dict()

    assert result["objective"] == "protocol_controls"
    assert result["primary_query"] == "Test query"


# ─────────────────────────────────────────────────────────────
# DP1 Router Types Tests
# ─────────────────────────────────────────────────────────────


def test_dp1_router_input_creation():
    """Test DP1RouterInput creation."""
    input_data = DP1RouterInput(
        current_tier=SearchTier.RAG,
        coverage_score=0.65,
        evidence_density=3,
        test_questions=["mechanism", "dosing"],
        answered_questions=["mechanism"],
        epmc_budget_remaining=2,
        web_budget_remaining=1,
    )

    assert input_data.coverage_score == 0.65
    assert input_data.evidence_density == 3
    assert input_data.current_tier == SearchTier.RAG
    assert len(input_data.test_questions) == 2


def test_dp1_router_output_creation():
    """Test DP1RouterOutput creation."""
    output = DP1RouterOutput(
        decision="upgrade_to_epmc",
        reason="Coverage below threshold",
        next_tier=SearchTier.EPMC,
        objective=SearchObjective.MECHANISM,
        query_plan=QueryPlan(
            objective=SearchObjective.MECHANISM,
            primary_query="EGFR mechanism",
            fallback_queries=[],
            filters={},
        ),
    )

    assert output.decision == "upgrade_to_epmc"
    assert output.next_tier == SearchTier.EPMC
    assert output.objective == SearchObjective.MECHANISM


def test_dp1_decisions():
    """Test valid DP1 decision values."""
    valid_decisions = ["proceed", "upgrade_to_epmc", "upgrade_to_web", "skip_web_limit"]

    for decision in valid_decisions:
        output = DP1RouterOutput(
            decision=decision,
            reason="Test reason",
            next_tier=None,
            objective=None,
            query_plan=None,
        )
        assert output.decision == decision


def test_dp1_router_output_to_dict():
    """Test DP1RouterOutput to_dict method."""
    output = DP1RouterOutput(
        decision="proceed",
        reason="Coverage sufficient",
        next_tier=None,
        objective=None,
        query_plan=None,
    )

    result = output.to_dict()

    assert result["decision"] == "proceed"
    assert result["reason"] == "Coverage sufficient"
    assert result["next_tier"] is None


# ─────────────────────────────────────────────────────────────
# DP2 Router Types Tests
# ─────────────────────────────────────────────────────────────


def test_dp2_router_input_creation():
    """Test DP2RouterInput creation."""
    input_data = DP2RouterInput(
        quality_score=0.7,
        missing_controls=["vehicle_control"],
        evidence_gaps=["dosing protocol"],
        feasibility_conflicts=["timeline too short"],
        unclear_elements=["animal model"],
        search_budget_remaining=1,
        loop_count=0,
        previous_gaps_searched=["mechanism"],
    )

    assert input_data.missing_controls == ["vehicle_control"]
    assert input_data.quality_score == 0.7
    assert input_data.search_budget_remaining == 1


def test_dp2_router_output_creation():
    """Test DP2RouterOutput creation."""
    output = DP2RouterOutput(
        decision="search_for_controls",
        reason="Need control group evidence",
        target_gaps=["vehicle_control"],
        user_questions=[],
    )

    assert output.decision == "search_for_controls"
    assert output.target_gaps == ["vehicle_control"]


def test_dp2_decisions():
    """Test valid DP2 decision values."""
    valid_decisions = ["redesign", "search_for_controls", "ask_user", "accept_minor_issues"]

    for decision in valid_decisions:
        output = DP2RouterOutput(
            decision=decision,
            reason="Test reason",
            target_gaps=[],
            user_questions=[],
        )
        assert output.decision == decision


def test_dp2_router_output_to_dict():
    """Test DP2RouterOutput to_dict method."""
    output = DP2RouterOutput(
        decision="ask_user",
        reason="Need clarification",
        target_gaps=[],
        user_questions=["What is the animal model?", "What is the dose?"],
    )

    result = output.to_dict()

    assert result["decision"] == "ask_user"
    assert len(result["user_questions"]) == 2


# ─────────────────────────────────────────────────────────────
# DP3 Router Types Tests
# ─────────────────────────────────────────────────────────────


def test_dp3_router_input_creation():
    """Test DP3RouterInput creation."""
    input_data = DP3RouterInput(
        quality_score=0.85,
        approval_required=False,
        web_limit_exceeded=False,
        evidence_sufficient=True,
        high_cost_experiment=False,
        ethics_required=False,
        explicit_constraints=[],
    )

    assert input_data.quality_score == 0.85
    assert input_data.evidence_sufficient is True
    assert input_data.approval_required is False


def test_dp3_router_output_creation():
    """Test DP3RouterOutput creation."""
    output = DP3RouterOutput(
        decision="single_plan",
        reason="High quality with sufficient evidence",
        plan_config={"emphasis": "optimal_design"},
    )

    assert output.decision == "single_plan"
    assert output.plan_config["emphasis"] == "optimal_design"


def test_dp3_decisions():
    """Test valid DP3 decision values."""
    valid_decisions = ["single_plan", "plan_a_b", "plan_b_only"]

    for decision in valid_decisions:
        output = DP3RouterOutput(
            decision=decision,
            reason="Test reason",
            plan_config={},
        )
        assert output.decision == decision


def test_dp3_router_output_to_dict():
    """Test DP3RouterOutput to_dict method."""
    output = DP3RouterOutput(
        decision="plan_a_b",
        reason="Approval required",
        plan_config={"plan_a_focus": "ideal", "plan_b_focus": "practical"},
    )

    result = output.to_dict()

    assert result["decision"] == "plan_a_b"
    assert result["plan_config"]["plan_a_focus"] == "ideal"
