"""Study Plan Agent 서비스

StudyPlanService: 싱글톤 서비스로 그래프 실행 관리.
"""

import logging
import time
from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any, AsyncGenerator

from langgraph.graph.state import CompiledStateGraph

from .graph import compile_study_plan_graph, compile_study_plan_graph_no_synthesis
from .nodes.synthesize_plan import synthesize_plan
from .state import (
    ApprovalStatus,
    ExperimentType,
    StudyPlanState,
    create_initial_state,
)

logger = logging.getLogger(__name__)


# ============================================================
# SSE 이벤트 타입
# ============================================================


class StudyPlanEventType(str, Enum):
    """Study Plan Agent SSE 이벤트 타입"""

    STATUS = "status"
    HYPOTHESIS_PARSED = "hypothesis"
    CLARIFICATION_NEEDED = "clarification"
    TESTS_DECOMPOSED = "tests"
    STUDIES_FOUND = "studies"
    SEARCH_EXPANDING = "search_expanding"
    EVIDENCE_PACKED = "evidence"
    METHODOLOGIES_ANALYZED = "methodologies"
    EXPERIMENTS_DESIGNED = "experiments"
    CRITIQUE = "critique"
    REVISION = "revision"
    MEASUREMENTS_IDENTIFIED = "measurements"
    FEASIBILITY_ASSESSED = "feasibility"
    APPROVAL_REQUIRED = "approval_required"
    TOKEN = "token"
    RESULT = "result"
    ERROR = "error"
    DONE = "done"


@dataclass
class StudyPlanEvent:
    """SSE 이벤트 데이터"""

    event_type: StudyPlanEventType
    data: dict[str, Any]


@dataclass
class StudyPlanResult:
    """최종 실행 결과"""

    success: bool
    final_plan: str
    executive_summary: str
    experiment_count: int
    approval_required: bool
    approval_status: str
    references: list[dict]
    evidence_trace: dict
    total_duration_ms: int
    error: str | None = None


# ============================================================
# 노드 → 이벤트 매핑
# ============================================================

NODE_EVENT_MAP = {
    "parse_hypothesis": StudyPlanEventType.HYPOTHESIS_PARSED,
    "clarify_hypothesis": StudyPlanEventType.CLARIFICATION_NEEDED,
    "decompose_tests": StudyPlanEventType.TESTS_DECOMPOSED,
    "search_studies": StudyPlanEventType.STUDIES_FOUND,
    "expand_search": StudyPlanEventType.SEARCH_EXPANDING,
    "build_evidence": StudyPlanEventType.EVIDENCE_PACKED,
    "analyze_methodologies": StudyPlanEventType.METHODOLOGIES_ANALYZED,
    "design_experiments": StudyPlanEventType.EXPERIMENTS_DESIGNED,
    "critique_refine": StudyPlanEventType.CRITIQUE,
    "identify_measurements": StudyPlanEventType.MEASUREMENTS_IDENTIFIED,
    "validate_feasibility": StudyPlanEventType.FEASIBILITY_ASSESSED,
    "approval_gate": StudyPlanEventType.APPROVAL_REQUIRED,
    "synthesize_plan": StudyPlanEventType.RESULT,
}


# ============================================================
# StudyPlanService
# ============================================================


class StudyPlanService:
    """
    Study Plan Agent 서비스 (싱글톤)

    그래프 컴파일 및 실행을 관리합니다.
    """

    _instance = None
    _graph: CompiledStateGraph | None = None
    _graph_no_synthesis: CompiledStateGraph | None = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @property
    def graph(self) -> CompiledStateGraph:
        """Lazy initialization of the main graph"""
        if self._graph is None:
            logger.info("Compiling Study Plan graph (full)")
            self._graph = compile_study_plan_graph()
        return self._graph

    @property
    def graph_no_synthesis(self) -> CompiledStateGraph:
        """Lazy initialization of the streaming graph"""
        if self._graph_no_synthesis is None:
            logger.info("Compiling Study Plan graph (no synthesis)")
            self._graph_no_synthesis = compile_study_plan_graph_no_synthesis()
        return self._graph_no_synthesis

    async def execute(
        self,
        user_input: str,
        research_context: str | None = None,
        constraints: list[str] | None = None,
        preferred_experiment_types: list[str] | None = None,
        conversation_id: str | None = None,
        user_id: str | None = None,
    ) -> StudyPlanResult:
        """
        동기 실행 (전체 결과 반환)

        Args:
            user_input: 가설/기전 설명
            research_context: 연구 맥락
            constraints: 제약조건
            preferred_experiment_types: 선호 실험 유형
            conversation_id: 대화 ID
            user_id: 사용자 ID

        Returns:
            StudyPlanResult: 최종 결과
        """
        start_time = time.time()

        # 실험 유형 변환
        exp_types = []
        if preferred_experiment_types:
            for t in preferred_experiment_types:
                try:
                    exp_types.append(ExperimentType(t))
                except ValueError:
                    pass

        # 초기 상태 생성
        initial_state = create_initial_state(
            user_input=user_input,
            research_context=research_context,
            constraints=constraints,
            preferred_experiment_types=exp_types,
            conversation_id=conversation_id,
            user_id=user_id,
        )

        logger.info(f"Executing Study Plan Agent for: {user_input[:50]}...")

        try:
            # 그래프 실행 (recursion_limit: 최대 50회 노드 실행)
            final_state = await self.graph.ainvoke(
                initial_state,
                config={"recursion_limit": 50},
            )

            duration_ms = int((time.time() - start_time) * 1000)

            # 결과 추출
            approval_gate_result = final_state.get("approval_gate_result")
            approval_required = (
                approval_gate_result.approval_required
                if approval_gate_result
                else False
            )

            approval_status = final_state.get("approval_status", ApprovalStatus.APPROVED)
            if isinstance(approval_status, ApprovalStatus):
                approval_status = approval_status.value

            experiment_designs = final_state.get("experiment_designs", [])

            result = StudyPlanResult(
                success=True,
                final_plan=final_state.get("final_plan", ""),
                executive_summary=final_state.get("executive_summary", ""),
                experiment_count=len(experiment_designs),
                approval_required=approval_required,
                approval_status=approval_status,
                references=final_state.get("references", []),
                evidence_trace=final_state.get("evidence_trace", {}),
                total_duration_ms=duration_ms,
            )

            logger.info(
                f"Study Plan completed: {len(experiment_designs)} experiments, "
                f"{duration_ms}ms"
            )

            return result

        except Exception as e:
            logger.error(f"Error executing Study Plan: {e}")
            duration_ms = int((time.time() - start_time) * 1000)
            return StudyPlanResult(
                success=False,
                final_plan="",
                executive_summary="",
                experiment_count=0,
                approval_required=False,
                approval_status="error",
                references=[],
                evidence_trace={},
                total_duration_ms=duration_ms,
                error=str(e),
            )

    async def execute_stream(
        self,
        user_input: str,
        research_context: str | None = None,
        constraints: list[str] | None = None,
        preferred_experiment_types: list[str] | None = None,
        conversation_id: str | None = None,
        user_id: str | None = None,
    ) -> AsyncGenerator[StudyPlanEvent, None]:
        """
        스트리밍 실행 (이벤트 yield)

        Args:
            user_input: 가설/기전 설명
            research_context: 연구 맥락
            constraints: 제약조건
            preferred_experiment_types: 선호 실험 유형
            conversation_id: 대화 ID
            user_id: 사용자 ID

        Yields:
            StudyPlanEvent: SSE 이벤트
        """
        start_time = time.time()

        # 실험 유형 변환
        exp_types = []
        if preferred_experiment_types:
            for t in preferred_experiment_types:
                try:
                    exp_types.append(ExperimentType(t))
                except ValueError:
                    pass

        # 초기 상태 생성
        initial_state = create_initial_state(
            user_input=user_input,
            research_context=research_context,
            constraints=constraints,
            preferred_experiment_types=exp_types,
            conversation_id=conversation_id,
            user_id=user_id,
        )

        logger.info(f"Streaming Study Plan Agent for: {user_input[:50]}...")

        # 시작 이벤트
        yield StudyPlanEvent(
            event_type=StudyPlanEventType.STATUS,
            data={"status": "started", "message": "연구 계획 생성을 시작합니다"},
        )

        try:
            # 스트리밍 그래프 실행 (synthesis 제외)
            final_state = initial_state
            async for state_update in self.graph_no_synthesis.astream(
                initial_state,
                config={"recursion_limit": 50},
            ):
                for node_name, node_state in state_update.items():
                    # 상태 병합
                    final_state = {**final_state, **node_state}

                    # 노드별 이벤트 생성
                    event = self._create_node_event(node_name, node_state)
                    if event:
                        yield event

            # 승인이 필요한 경우 별도 이벤트
            approval_gate_result = final_state.get("approval_gate_result")
            if approval_gate_result and approval_gate_result.approval_required:
                yield StudyPlanEvent(
                    event_type=StudyPlanEventType.APPROVAL_REQUIRED,
                    data={
                        "approval_required": True,
                        "items": [
                            {
                                "type": i.item_type,
                                "reason": i.reason,
                                "cost_bucket": i.cost_bucket.value,
                                "ethics_bucket": i.ethics_bucket.value,
                            }
                            for i in approval_gate_result.approval_items
                        ],
                        "choices": [
                            {
                                "choice_id": c.choice_id,
                                "label": c.label,
                                "description": c.description,
                                "estimated_cost": c.estimated_cost,
                                "estimated_timeline": c.estimated_timeline,
                            }
                            for c in approval_gate_result.choices
                        ],
                    },
                )

            # Synthesis 실행 (승인된 경우만)
            approval_status = final_state.get("approval_status", ApprovalStatus.APPROVED)
            if isinstance(approval_status, ApprovalStatus):
                status_value = approval_status.value
            else:
                status_value = approval_status

            if status_value == "approved":
                yield StudyPlanEvent(
                    event_type=StudyPlanEventType.STATUS,
                    data={"status": "synthesizing", "message": "최종 계획서를 작성합니다"},
                )

                # synthesize_plan 직접 호출
                synthesis_result = await synthesize_plan(final_state)
                final_state = {**final_state, **synthesis_result}

                yield StudyPlanEvent(
                    event_type=StudyPlanEventType.RESULT,
                    data={
                        "final_plan": synthesis_result.get("final_plan", ""),
                        "executive_summary": synthesis_result.get("executive_summary", ""),
                    },
                )

            # 완료 이벤트
            duration_ms = int((time.time() - start_time) * 1000)
            experiment_designs = final_state.get("experiment_designs", [])

            yield StudyPlanEvent(
                event_type=StudyPlanEventType.DONE,
                data={
                    "success": True,
                    "experiment_count": len(experiment_designs),
                    "total_duration_ms": duration_ms,
                },
            )

            logger.info(f"Study Plan streaming completed: {duration_ms}ms")

        except Exception as e:
            logger.error(f"Error in Study Plan streaming: {e}")
            yield StudyPlanEvent(
                event_type=StudyPlanEventType.ERROR,
                data={"error": str(e), "message": "계획 생성 중 오류가 발생했습니다"},
            )

    def _create_node_event(
        self, node_name: str, node_state: dict
    ) -> StudyPlanEvent | None:
        """노드 완료 시 이벤트 생성"""
        event_type = NODE_EVENT_MAP.get(node_name)
        if not event_type:
            return None

        # 노드별 데이터 추출
        data = {"node": node_name}

        if node_name == "parse_hypothesis":
            hypothesis = node_state.get("hypothesis")
            if hypothesis:
                data["hypothesis"] = {
                    "independent_variable": hypothesis.independent_variable,
                    "dependent_variable": hypothesis.dependent_variable,
                    "population": hypothesis.population,
                }
            data["confidence"] = node_state.get("hypothesis_confidence", 0)

        elif node_name == "clarify_hypothesis":
            data["questions"] = node_state.get("clarification_questions", [])

        elif node_name == "decompose_tests":
            test_questions = node_state.get("test_questions", [])
            data["test_questions"] = [
                {
                    "category": q.category.value,
                    "question": q.question,
                    "decision_rule": q.decision_rule,
                }
                for q in test_questions
            ]

        elif node_name == "search_studies":
            data["study_count"] = len(node_state.get("prior_studies", []))
            data["coverage"] = node_state.get("search_coverage_score", 0)
            data["gaps"] = node_state.get("search_gap_notes", [])

        elif node_name == "expand_search":
            data["expanded_queries"] = node_state.get("expanded_queries", [])
            data["expand_count"] = node_state.get("search_expand_count", 0)

        elif node_name == "build_evidence":
            data["snippet_count"] = len(node_state.get("evidence_snippets", []))
            data["pack_count"] = len(node_state.get("evidence_packs", []))

        elif node_name == "design_experiments":
            experiments = node_state.get("experiment_designs", [])
            data["experiments"] = [
                {
                    "id": e.experiment_id,
                    "type": e.experiment_type.value,
                    "title": e.title,
                    "test_category": e.test_category.value,
                }
                for e in experiments
            ]

        elif node_name == "critique_refine":
            critique_result = node_state.get("critique_result")
            if critique_result:
                data["quality_score"] = critique_result.quality_score
                data["passed"] = critique_result.passed
                data["suggestions"] = critique_result.revision_suggestions[:3]
            data["revision_count"] = node_state.get("revision_count", 0)

        elif node_name == "identify_measurements":
            data["measurement_count"] = len(node_state.get("measurements", []))
            data["priority"] = node_state.get("measurement_priority", [])[:5]

        elif node_name == "validate_feasibility":
            feasibility = node_state.get("feasibility")
            if feasibility:
                data["overall_score"] = feasibility.overall_score
                data["concerns"] = (
                    feasibility.technical_concerns[:2]
                    + feasibility.resource_concerns[:2]
                )

        elif node_name == "approval_gate":
            gate_result = node_state.get("approval_gate_result")
            if gate_result:
                data["approval_required"] = gate_result.approval_required
                data["item_count"] = len(gate_result.approval_items)

        return StudyPlanEvent(event_type=event_type, data=data)


# ============================================================
# 싱글톤 인스턴스
# ============================================================

study_plan_service = StudyPlanService()


def get_study_plan_service() -> StudyPlanService:
    """의존성 주입용 함수"""
    return study_plan_service
