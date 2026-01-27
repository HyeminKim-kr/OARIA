"""Phase definitions for Study Plan Agent v4.

Defines the phases of the agent's workflow and their allowed tools.
"""

from enum import Enum


class Phase(str, Enum):
    """Agent workflow phases."""

    UNDERSTAND = "understand"  # 가설 파싱
    DECOMPOSE = "decompose"  # 질문 분해
    RESEARCH = "research"  # 문헌 검색
    DESIGN = "design"  # 실험 설계
    VALIDATE = "validate"  # 검증
    SYNTHESIZE = "synthesize"  # 최종 합성
    COMPLETED = "completed"


# Phase별 사용 가능한 도구
PHASE_TOOLS: dict[Phase, list[str]] = {
    Phase.UNDERSTAND: ["parse_hypothesis"],
    Phase.DECOMPOSE: ["decompose_questions"],
    Phase.RESEARCH: ["search_rag", "search_epmc", "search_web"],
    Phase.DESIGN: ["design_experiment", "design_controls", "suggest_measurements"],
    Phase.VALIDATE: ["critique_design", "validate_feasibility"],
    Phase.SYNTHESIZE: ["synthesize_plan", "generate_plan_b"],
    Phase.COMPLETED: [],
}

# Phase 순서 (인덱스로 진행률 계산)
PHASE_ORDER: list[Phase] = [
    Phase.UNDERSTAND,
    Phase.DECOMPOSE,
    Phase.RESEARCH,
    Phase.DESIGN,
    Phase.VALIDATE,
    Phase.SYNTHESIZE,
    Phase.COMPLETED,
]

# Phase별 전환 조건 설명
PHASE_EXIT_CONDITIONS: dict[Phase, str] = {
    Phase.UNDERSTAND: "structured_hypothesis가 생성되면 완료",
    Phase.DECOMPOSE: "test_questions가 3개 이상이면 완료",
    Phase.RESEARCH: "각 질문에 evidence가 있거나 3회 검색 시도하면 완료",
    Phase.DESIGN: "experiments가 1개 이상이면 완료",
    Phase.VALIDATE: "quality_score가 70% 이상이면 완료",
    Phase.SYNTHESIZE: "Plan A와 Plan B가 모두 생성되면 완료",
    Phase.COMPLETED: "모든 작업 완료",
}

# Phase별 한글 이름
PHASE_NAMES_KO: dict[Phase, str] = {
    Phase.UNDERSTAND: "가설 이해",
    Phase.DECOMPOSE: "질문 분해",
    Phase.RESEARCH: "문헌 검색",
    Phase.DESIGN: "실험 설계",
    Phase.VALIDATE: "검증",
    Phase.SYNTHESIZE: "계획 합성",
    Phase.COMPLETED: "완료",
}


def get_phase_number(phase: Phase) -> int:
    """Phase의 순서 번호 반환 (1부터 시작)."""
    try:
        return PHASE_ORDER.index(phase) + 1
    except ValueError:
        return 0


def get_total_phases() -> int:
    """전체 Phase 수 반환 (COMPLETED 제외)."""
    return len(PHASE_ORDER) - 1  # COMPLETED 제외
