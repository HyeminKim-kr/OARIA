"""Node 9: critique_and_refine - Critic 검증 및 수정 (Loop 2)"""

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

logger = logging.getLogger(__name__)


async def critique_and_refine(state: StudyPlanState) -> dict:
    """
    실험 설계를 비판적으로 검토하고 수정 제안을 생성합니다.

    Args:
        state: 현재 에이전트 상태

    Returns:
        업데이트된 상태 dict:
        - critique_result: CritiqueResult
        - quality_score: float
        - revision_count: int
        - revision_history: list[RevisionRecord]
    """
    experiment_designs = state.get("experiment_designs", [])
    test_questions = state.get("test_questions", [])
    hypothesis = state.get("hypothesis")
    revision_count = state.get("revision_count", 0)
    revision_history = state.get("revision_history", [])
    previous_quality = state.get("quality_score", 0.0)

    logger.info(f"Critiquing experiments (revision_count={revision_count})")

    try:
        client = AsyncOpenAI(api_key=settings.openai_api_key)

        # 데이터 준비
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

        tq_list = [
            {
                "category": q.category.value,
                "question": q.question,
                "decision_rule": q.decision_rule,
            }
            for q in test_questions
        ]

        hyp_dict = {}
        if hypothesis:
            hyp_dict = {
                "original_text": hypothesis.original_text,
                "independent_variable": hypothesis.independent_variable,
                "dependent_variable": hypothesis.dependent_variable,
            }

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

        # CritiqueReport 생성
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

        # Revision history 업데이트
        if revision_count > 0:
            revision_record = RevisionRecord(
                revision_number=revision_count,
                changes_made=revision_suggestions[:3],  # 최근 변경사항
                reason="Critic 검증 결과에 따른 수정",
                quality_before=previous_quality,
                quality_after=quality_score,
            )
            revision_history = revision_history + [revision_record]

        logger.info(
            f"Critique complete: quality={quality_score:.2f}, passed={passed}, "
            f"suggestions={len(revision_suggestions)}"
        )

        return {
            "critique_result": critique_result,
            "quality_score": quality_score,
            "revision_count": revision_count + 1 if not passed else revision_count,
            "revision_history": revision_history,
            "status_detail": "critique_complete" if passed else "revision_needed",
        }

    except Exception as e:
        logger.error(f"Error in critique: {e}")
        return {
            "critique_result": None,
            "quality_score": 0.5,
            "revision_count": revision_count,
            "revision_history": revision_history,
            "error": str(e),
            "status_detail": "critique_error",
        }
