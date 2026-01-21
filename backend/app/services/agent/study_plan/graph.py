"""Study Plan Agent 그래프 정의

LangGraph 기반 그래프 구조 정의.
3개의 조건부 루프 포함:
- Loop 0: 가설 명확화 (clarify → parse)
- Loop 1: 검색 확장 (expand → search)
- Loop 2: Critic 수정 (critique → design)
"""

import logging

from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph

from .state import ApprovalStatus, StudyPlanState

logger = logging.getLogger(__name__)


# ============================================================
# 조건부 라우팅 함수
# ============================================================


def route_after_parse(state: StudyPlanState) -> str:
    """
    Loop 0: 가설 파싱 후 라우팅

    - clarification_needed=True → clarify (명확화 질문)
    - clarification_needed=False → decompose (검증 질문 분해)
    """
    if state.get("clarification_needed", False):
        logger.info("Routing: parse → clarify (clarification needed)")
        return "clarify"
    logger.info("Routing: parse → decompose (hypothesis clear)")
    return "decompose"


def route_after_search(state: StudyPlanState) -> str:
    """
    Loop 1: 검색 후 커버리지 기반 라우팅

    - coverage < 0.6 AND expand_count < 2 → expand (쿼리 확장)
    - otherwise → build_evidence (Evidence Pack 구축)
    """
    coverage = state.get("search_coverage_score", 1.0)
    expand_count = state.get("search_expand_count", 0)

    if coverage < 0.6 and expand_count < 2:
        logger.info(
            f"Routing: search → expand "
            f"(coverage={coverage:.2f}, expand_count={expand_count})"
        )
        return "expand"

    logger.info(f"Routing: search → build_evidence (coverage={coverage:.2f})")
    return "build_evidence"


def route_after_critique(state: StudyPlanState) -> str:
    """
    Loop 2: Critic 검증 후 품질 기반 라우팅

    - quality >= 0.8 OR revision_count >= 2 → measurements (측정치 도출)
    - otherwise → design (실험 재설계)
    """
    quality = state.get("quality_score", 0.0)
    revision_count = state.get("revision_count", 0)

    if quality >= 0.8 or revision_count >= 2:
        logger.info(
            f"Routing: critique → measurements "
            f"(quality={quality:.2f}, revisions={revision_count})"
        )
        return "measurements"

    logger.info(
        f"Routing: critique → design (revision needed, "
        f"quality={quality:.2f}, revisions={revision_count})"
    )
    return "design"


def route_after_approval(state: StudyPlanState) -> str:
    """
    승인 게이트 후 라우팅

    - approved → synthesize (최종 합성)
    - needs_user → END (사용자 승인 대기)
    - rejected → END (거부됨)
    """
    status = state.get("approval_status", ApprovalStatus.APPROVED)

    if isinstance(status, str):
        status_value = status
    else:
        status_value = status.value

    if status_value == "approved":
        logger.info("Routing: approval → synthesize (approved)")
        return "synthesize"
    elif status_value == "needs_user":
        logger.info("Routing: approval → END (needs user approval)")
        return "end"
    else:
        logger.info(f"Routing: approval → END (status={status_value})")
        return "end"


# ============================================================
# 그래프 빌더
# ============================================================


def build_study_plan_graph() -> StateGraph:
    """
    Study Plan Agent 그래프를 구성합니다.

    Returns:
        StateGraph: 컴파일 전 그래프
    """
    # 순환 import 방지를 위해 여기서 import
    from .nodes import (
        analyze_methodologies,
        approval_gate,
        build_evidence_pack,
        clarify_hypothesis,
        critique_and_refine,
        decompose_to_test_questions,
        design_experiments,
        expand_search,
        identify_measurements,
        parse_hypothesis,
        search_prior_studies,
        synthesize_plan,
        validate_feasibility,
    )

    graph = StateGraph(StudyPlanState)

    # ============================================================
    # 노드 등록 (13개)
    # ============================================================
    graph.add_node("parse_hypothesis", parse_hypothesis)
    graph.add_node("clarify_hypothesis", clarify_hypothesis)
    graph.add_node("decompose_tests", decompose_to_test_questions)
    graph.add_node("search_studies", search_prior_studies)
    graph.add_node("expand_search", expand_search)
    graph.add_node("build_evidence", build_evidence_pack)
    graph.add_node("analyze_methodologies", analyze_methodologies)
    graph.add_node("design_experiments", design_experiments)
    graph.add_node("critique_refine", critique_and_refine)
    graph.add_node("identify_measurements", identify_measurements)
    graph.add_node("validate_feasibility", validate_feasibility)
    graph.add_node("approval_gate", approval_gate)
    graph.add_node("synthesize_plan", synthesize_plan)

    # ============================================================
    # 엔트리 포인트
    # ============================================================
    graph.set_entry_point("parse_hypothesis")

    # ============================================================
    # Loop 0: 가설 명확화 루프
    # ============================================================
    graph.add_conditional_edges(
        "parse_hypothesis",
        route_after_parse,
        {
            "clarify": "clarify_hypothesis",
            "decompose": "decompose_tests",
        },
    )
    # clarify 후 다시 parse로 (사용자 입력 후 재시도)
    graph.add_edge("clarify_hypothesis", "parse_hypothesis")

    # ============================================================
    # 검증 질문 분해 → 검색
    # ============================================================
    graph.add_edge("decompose_tests", "search_studies")

    # ============================================================
    # Loop 1: 검색 커버리지 루프
    # ============================================================
    graph.add_conditional_edges(
        "search_studies",
        route_after_search,
        {
            "expand": "expand_search",
            "build_evidence": "build_evidence",
        },
    )
    # expand 후 다시 search로
    graph.add_edge("expand_search", "search_studies")

    # ============================================================
    # Evidence → 방법론 분석 → 실험 설계
    # ============================================================
    graph.add_edge("build_evidence", "analyze_methodologies")
    graph.add_edge("analyze_methodologies", "design_experiments")

    # ============================================================
    # Loop 2: Critic 수정 루프
    # ============================================================
    graph.add_edge("design_experiments", "critique_refine")
    graph.add_conditional_edges(
        "critique_refine",
        route_after_critique,
        {
            "measurements": "identify_measurements",
            "design": "design_experiments",  # 재설계
        },
    )

    # ============================================================
    # 측정치 → 실현가능성 → 승인 게이트
    # ============================================================
    graph.add_edge("identify_measurements", "validate_feasibility")
    graph.add_edge("validate_feasibility", "approval_gate")

    # ============================================================
    # 승인 게이트 분기
    # ============================================================
    graph.add_conditional_edges(
        "approval_gate",
        route_after_approval,
        {
            "synthesize": "synthesize_plan",
            "end": END,
        },
    )

    # ============================================================
    # 최종 합성 → 종료
    # ============================================================
    graph.add_edge("synthesize_plan", END)

    return graph


def compile_study_plan_graph() -> CompiledStateGraph:
    """
    Study Plan Agent 그래프를 컴파일합니다.

    Returns:
        CompiledStateGraph: 실행 가능한 그래프
    """
    graph = build_study_plan_graph()
    # recursion_limit: 최대 노드 실행 횟수 (루프 포함)
    # 13개 노드 + 루프 여유분 = 50 정도면 충분
    return graph.compile()


# ============================================================
# 스트리밍용 그래프 (synthesis 제외)
# ============================================================


def build_study_plan_graph_no_synthesis() -> StateGraph:
    """
    스트리밍용 그래프 (synthesis 노드 제외).
    synthesis는 별도로 스트리밍 처리.

    Returns:
        StateGraph: synthesis 제외 그래프
    """
    from .nodes import (
        analyze_methodologies,
        approval_gate,
        build_evidence_pack,
        clarify_hypothesis,
        critique_and_refine,
        decompose_to_test_questions,
        design_experiments,
        expand_search,
        identify_measurements,
        parse_hypothesis,
        search_prior_studies,
        validate_feasibility,
    )

    graph = StateGraph(StudyPlanState)

    # 노드 등록 (synthesize_plan 제외)
    graph.add_node("parse_hypothesis", parse_hypothesis)
    graph.add_node("clarify_hypothesis", clarify_hypothesis)
    graph.add_node("decompose_tests", decompose_to_test_questions)
    graph.add_node("search_studies", search_prior_studies)
    graph.add_node("expand_search", expand_search)
    graph.add_node("build_evidence", build_evidence_pack)
    graph.add_node("analyze_methodologies", analyze_methodologies)
    graph.add_node("design_experiments", design_experiments)
    graph.add_node("critique_refine", critique_and_refine)
    graph.add_node("identify_measurements", identify_measurements)
    graph.add_node("validate_feasibility", validate_feasibility)
    graph.add_node("approval_gate", approval_gate)

    # 엔트리 포인트
    graph.set_entry_point("parse_hypothesis")

    # Loop 0
    graph.add_conditional_edges(
        "parse_hypothesis",
        route_after_parse,
        {"clarify": "clarify_hypothesis", "decompose": "decompose_tests"},
    )
    graph.add_edge("clarify_hypothesis", "parse_hypothesis")

    # decompose → search
    graph.add_edge("decompose_tests", "search_studies")

    # Loop 1
    graph.add_conditional_edges(
        "search_studies",
        route_after_search,
        {"expand": "expand_search", "build_evidence": "build_evidence"},
    )
    graph.add_edge("expand_search", "search_studies")

    # Evidence → methodologies → design
    graph.add_edge("build_evidence", "analyze_methodologies")
    graph.add_edge("analyze_methodologies", "design_experiments")

    # Loop 2
    graph.add_edge("design_experiments", "critique_refine")
    graph.add_conditional_edges(
        "critique_refine",
        route_after_critique,
        {"measurements": "identify_measurements", "design": "design_experiments"},
    )

    # measurements → feasibility → approval → END
    graph.add_edge("identify_measurements", "validate_feasibility")
    graph.add_edge("validate_feasibility", "approval_gate")
    graph.add_edge("approval_gate", END)  # 항상 END (synthesis는 별도 처리)

    return graph


def compile_study_plan_graph_no_synthesis() -> CompiledStateGraph:
    """스트리밍용 그래프 컴파일"""
    graph = build_study_plan_graph_no_synthesis()
    return graph.compile()
