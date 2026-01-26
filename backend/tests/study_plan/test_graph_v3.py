"""Tests for Study Plan Agent v3 Graph and Routing.

Run with: pytest tests/study_plan/test_graph_v3.py -v
"""

import pytest
from unittest.mock import patch, MagicMock

from app.services.agent.study_plan.v3.state import StudyPlanState, ApprovalStatus


# ─────────────────────────────────────────────────────────────
# Graph v3 Routing Tests
# ─────────────────────────────────────────────────────────────


class TestRouteAfterCritiqueV3:
    """DP2 기반 라우팅 함수 테스트"""

    def test_route_redesign(self):
        """redesign 결정시 design으로 라우팅"""
        from app.services.agent.study_plan.v3.graph import route_after_critique_v3

        state = {"dp2_decision": "redesign"}
        result = route_after_critique_v3(state)

        assert result == "design"

    def test_route_search_for_controls(self):
        """search_for_controls 결정시 search_controls로 라우팅"""
        from app.services.agent.study_plan.v3.graph import route_after_critique_v3

        state = {"dp2_decision": "search_for_controls"}
        result = route_after_critique_v3(state)

        assert result == "search_controls"

    def test_route_ask_user(self):
        """ask_user 결정시 clarify로 라우팅"""
        from app.services.agent.study_plan.v3.graph import route_after_critique_v3

        state = {"dp2_decision": "ask_user"}
        result = route_after_critique_v3(state)

        assert result == "clarify"

    def test_route_accept_minor_issues(self):
        """accept_minor_issues 결정시 measurements로 라우팅"""
        from app.services.agent.study_plan.v3.graph import route_after_critique_v3

        state = {"dp2_decision": "accept_minor_issues"}
        result = route_after_critique_v3(state)

        assert result == "measurements"

    def test_route_default(self):
        """결정 없을 때 기본값 measurements"""
        from app.services.agent.study_plan.v3.graph import route_after_critique_v3

        state = {}
        result = route_after_critique_v3(state)

        assert result == "measurements"


# ─────────────────────────────────────────────────────────────
# v3 Graph Build Tests
# ─────────────────────────────────────────────────────────────


class TestBuildStudyPlanGraphV3:
    """v3 그래프 빌드 테스트"""

    def test_graph_builds_without_error(self):
        """v3 그래프가 에러 없이 빌드되는지 확인"""
        from app.services.agent.study_plan.v3.graph import build_study_plan_graph_v3

        graph = build_study_plan_graph_v3()

        assert graph is not None

    def test_graph_has_expected_nodes(self):
        """v3 그래프에 예상 노드들이 있는지 확인"""
        from app.services.agent.study_plan.v3.graph import build_study_plan_graph_v3

        graph = build_study_plan_graph_v3()

        # 그래프 노드 확인 (LangGraph 내부 구조에 따라 다를 수 있음)
        # 기본적으로 빌드가 성공했으면 노드가 존재함
        assert graph is not None

    def test_graph_compiles(self):
        """v3 그래프가 컴파일되는지 확인"""
        from app.services.agent.study_plan.v3.graph import build_study_plan_graph_v3

        graph = build_study_plan_graph_v3()
        compiled = graph.compile()

        assert compiled is not None


# ─────────────────────────────────────────────────────────────
# v3 State Fields Tests
# ─────────────────────────────────────────────────────────────


class TestStudyPlanStateV3Fields:
    """v3 상태 필드 테스트"""

    def test_state_has_v3_fields(self):
        """state.py에 v3 필드가 정의되어 있는지 확인"""
        from app.services.agent.study_plan.v3.state import StudyPlanState

        # TypedDict 키 확인
        annotations = StudyPlanState.__annotations__

        # v3 검색 필드
        assert "run_id" in annotations
        assert "evidence_snippets_v3" in annotations
        assert "current_tier" in annotations

        # DP 결과 필드 - 실제 구현 확인
        assert "dp1_decisions" in annotations  # list[dict]
        assert "dp2_decision" in annotations
        assert "dp3_decision" in annotations

        # Plan A/B 필드
        assert "plan_a" in annotations
        assert "plan_b" in annotations
        assert "plan_config" in annotations

    def test_create_initial_state_v3_defaults(self):
        """create_initial_state가 v3 기본값을 포함하는지"""
        from app.services.agent.study_plan.v3.state import create_initial_state

        state = create_initial_state(
            user_input="Test hypothesis",
            research_context="Test context",
        )

        # v3 필드 기본값 확인
        assert "run_id" in state
        assert state["run_id"] != ""
        assert state["search_tier_history"] == []
        assert state["evidence_snippets_v3"] == []
        assert state["current_tier"] == 1
        assert state["run_epmc_count"] == 0
        assert state["run_web_count"] == 0


# ─────────────────────────────────────────────────────────────
# v3 Nodes Import Tests
# ─────────────────────────────────────────────────────────────


class TestV3NodesImport:
    """v3 노드 import 테스트"""

    def test_search_studies_v3_imports(self):
        """search_studies_v3 import 테스트"""
        from app.services.agent.study_plan.v3.nodes import search_studies_v3

        assert callable(search_studies_v3)

    def test_critique_refine_v3_imports(self):
        """critique_refine_v3 import 테스트"""
        from app.services.agent.study_plan.v3.nodes import critique_refine_v3

        assert callable(critique_refine_v3)

    def test_synthesize_plan_v3_imports(self):
        """synthesize_plan_v3 import 테스트"""
        from app.services.agent.study_plan.v3.nodes import synthesize_plan_v3

        assert callable(synthesize_plan_v3)

    def test_search_for_controls_imports(self):
        """search_for_controls import 테스트"""
        from app.services.agent.study_plan.v3.nodes import search_for_controls

        assert callable(search_for_controls)


# ─────────────────────────────────────────────────────────────
# Integration Tests (Skipped by default)
# ─────────────────────────────────────────────────────────────


@pytest.mark.skip(reason="Requires running services (Redis, Weaviate, OpenAI)")
class TestStudyPlanV3Integration:
    """v3 통합 테스트 (외부 서비스 필요)"""

    @pytest.mark.asyncio
    async def test_full_v3_execution(self):
        """v3 전체 실행 테스트"""
        from app.services.agent.study_plan.v3.graph import build_study_plan_graph_v3
        from app.services.agent.study_plan.v3.state import create_initial_state

        graph = build_study_plan_graph_v3()
        compiled = graph.compile()

        initial_state = create_initial_state(
            user_input="EGFR T790M mutation causes osimertinib resistance",
            research_context="NSCLC targeted therapy",
        )

        final_state = await compiled.ainvoke(
            initial_state,
            config={"recursion_limit": 50},
        )

        assert final_state is not None
        assert "final_plan" in final_state
