"""Node: critique_refine_v3 - Critique + DP2 라우터 통합

v2.1 critique_and_refine을 확장하여:
- DP2 Router 연동
- search_for_controls 지원
- ask_user 지원
"""

import json
import logging

from openai import AsyncOpenAI

from app.config import settings

from ..prompts import CRITIQUE_SYSTEM, CRITIQUE_USER
from ..state import (
    CritiqueReport,
    CritiqueResult,
    RevisionRecord,
    StudyPlanState,
)
from ...shared.search import SearchTier, budget_manager
from ...shared.search.types import DP2RouterInput
from ..routers import DP2CritiqueRouter

logger = logging.getLogger(__name__)


async def critique_refine_v3(state: StudyPlanState) -> dict:
    """
    Critique + DP2 라우터 통합 노드.

    1. LLM으로 실험 설계 비판
    2. DP2 Router로 다음 행동 결정
    3. 결정에 따른 상태 업데이트

    Args:
        state: 현재 에이전트 상태

    Returns:
        업데이트된 상태 dict
    """
    experiment_designs = state.get("experiment_designs", [])
    test_questions = state.get("test_questions", [])
    hypothesis = state.get("hypothesis")
    revision_count = state.get("revision_count", 0)
    revision_history = state.get("revision_history", [])
    previous_quality = state.get("quality_score", 0.0)
    run_id = state.get("run_id", "")
    dp2_loop_count = state.get("dp2_loop_count", 0)
    previous_gaps = state.get("previous_gaps_searched", [])

    logger.info(
        f"critique_refine_v3 run_id={run_id} "
        f"revision={revision_count} dp2_loop={dp2_loop_count}"
    )

    try:
        client = AsyncOpenAI(api_key=settings.openai_api_key)

        # 1. LLM Critique 수행
        experiments_list = _prepare_experiments_for_critique(experiment_designs)
        tq_list = _prepare_test_questions(test_questions)
        hyp_dict = _prepare_hypothesis(hypothesis)

        user_prompt = CRITIQUE_USER.format(
            experiment_designs=json.dumps(experiments_list, ensure_ascii=False, indent=2),
            test_questions=json.dumps(tq_list, ensure_ascii=False, indent=2),
            hypothesis=json.dumps(hyp_dict, ensure_ascii=False),
        )

        response = await client.chat.completions.create(
            model=settings.openai_chat_model,
            messages=[
                {"role": "system", "content": CRITIQUE_SYSTEM},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.3,
            response_format={"type": "json_object"},
        )

        result = json.loads(response.choices[0].message.content)

        # 2. CritiqueReport 생성
        report_data = result.get("critique_report", {})
        critique_report = CritiqueReport(
            missing_controls=report_data.get("missing_controls", []),
            ambiguity_issues=report_data.get("ambiguity_issues", []),
            confounders=report_data.get("confounders", []),
            discriminative_power_issues=report_data.get("discriminative_power_issues", []),
            endpoint_alignment_issues=report_data.get("endpoint_alignment_issues", []),
            feasibility_conflicts=report_data.get("feasibility_conflicts", []),
        )

        quality_score = result.get("quality_score", 0.5)
        passed = result.get("passed", quality_score >= 0.8)
        revision_suggestions = result.get("revision_suggestions", [])

        critique_result = CritiqueResult(
            quality_score=quality_score,
            critique_report=critique_report,
            revision_suggestions=revision_suggestions,
            passed=passed,
        )

        # 3. DP2 Router 결정
        dp2_router = DP2CritiqueRouter()

        # evidence_gaps 추출 (ambiguity + endpoint issues)
        evidence_gaps = (
            critique_report.ambiguity_issues +
            critique_report.endpoint_alignment_issues
        )

        # unclear_elements 추출
        unclear_elements = [
            issue for issue in critique_report.discriminative_power_issues
            if "model" in issue.lower() or "assay" in issue.lower()
        ]

        # 남은 예산 확인
        search_budget = await budget_manager.get_remaining(run_id, SearchTier.EPMC)
        web_remaining = await budget_manager.get_remaining(run_id, SearchTier.WEB)
        total_search_budget = search_budget + web_remaining

        dp2_input = DP2RouterInput(
            quality_score=quality_score,
            missing_controls=critique_report.missing_controls,
            evidence_gaps=evidence_gaps,
            feasibility_conflicts=critique_report.feasibility_conflicts,
            unclear_elements=unclear_elements,
            search_budget_remaining=total_search_budget,
            loop_count=dp2_loop_count,
            previous_gaps_searched=previous_gaps,
        )

        dp2_decision = dp2_router.route(dp2_input, run_id)

        # 4. 결정에 따른 상태 업데이트
        new_revision_count = revision_count
        new_dp2_loop_count = dp2_loop_count
        new_previous_gaps = list(previous_gaps)

        if dp2_decision.decision == "redesign":
            new_revision_count = revision_count + 1
            new_dp2_loop_count = dp2_loop_count + 1

        elif dp2_decision.decision == "search_for_controls":
            new_dp2_loop_count = dp2_loop_count + 1
            new_previous_gaps.extend(dp2_decision.target_gaps)

        # Revision history 업데이트
        if revision_count > 0 and dp2_decision.decision in ["redesign", "accept_minor_issues"]:
            revision_record = RevisionRecord(
                revision_number=revision_count,
                changes_made=revision_suggestions[:3],
                reason=f"DP2 결정: {dp2_decision.decision}",
                quality_before=previous_quality,
                quality_after=quality_score,
            )
            revision_history = revision_history + [revision_record]

        logger.info(
            f"critique_v3 complete: quality={quality_score:.2f} "
            f"dp2_decision={dp2_decision.decision}"
        )

        return {
            "critique_result": critique_result,
            "quality_score": quality_score,
            "revision_count": new_revision_count,
            "revision_history": revision_history,
            # v3 필드
            "dp2_decision": dp2_decision.decision,
            "dp2_loop_count": new_dp2_loop_count,
            "previous_gaps_searched": new_previous_gaps,
            # DP2 ask_user 지원
            "clarification_questions": dp2_decision.user_questions if dp2_decision.decision == "ask_user" else [],
            "clarification_needed": dp2_decision.decision == "ask_user",
            # search_for_controls 지원
            "_dp2_target_gaps": dp2_decision.target_gaps,
            "status_detail": f"critique_v3_{dp2_decision.decision}",
        }

    except Exception as e:
        logger.error(f"Error in critique_refine_v3: {e}")
        return {
            "critique_result": None,
            "quality_score": 0.5,
            "revision_count": revision_count,
            "revision_history": revision_history,
            "dp2_decision": "accept_minor_issues",
            "dp2_loop_count": dp2_loop_count,
            "error": str(e),
            "status_detail": "critique_error",
        }


def _prepare_experiments_for_critique(experiment_designs: list) -> list[dict]:
    """실험 설계를 critique용 dict로 변환"""
    experiments_list = []
    for exp in experiment_designs:
        exp_dict = {
            "experiment_id": exp.experiment_id,
            "experiment_type": exp.experiment_type.value,
            "title": exp.title,
            "objective": exp.objective,
            "hypothesis_tested": exp.hypothesis_tested,
            "test_category": exp.test_category.value,
            "experimental_groups": exp.experimental_groups,
            "control_groups": [
                {"type": cg.control_type.value, "name": cg.name, "n": cg.n}
                for cg in exp.control_groups
            ],
            "model_system": exp.model_system,
            "primary_endpoint": exp.primary_endpoint,
            "secondary_endpoints": exp.secondary_endpoints,
            "sample_size_justification": exp.sample_size_justification,
        }
        experiments_list.append(exp_dict)
    return experiments_list


def _prepare_test_questions(test_questions: list) -> list[dict]:
    """test_questions를 dict로 변환"""
    return [
        {
            "category": q.category.value,
            "question": q.question,
            "decision_rule": q.decision_rule,
        }
        for q in test_questions
    ]


def _prepare_hypothesis(hypothesis) -> dict:
    """hypothesis를 dict로 변환"""
    if not hypothesis:
        return {}
    return {
        "original_text": hypothesis.original_text,
        "independent_variable": hypothesis.independent_variable,
        "dependent_variable": hypothesis.dependent_variable,
    }
