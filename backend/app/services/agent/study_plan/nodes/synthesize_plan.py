"""Node 13: synthesize_plan - 최종 연구 계획서 합성"""

import json
import logging

from openai import AsyncOpenAI

from app.config import settings

from ..prompts import SYNTHESIZE_PLAN_SYSTEM, SYNTHESIZE_PLAN_USER
from ..state import StudyPlanState

logger = logging.getLogger(__name__)


async def synthesize_plan(state: StudyPlanState) -> dict:
    """
    모든 정보를 종합하여 최종 연구 계획서를 생성합니다.

    Args:
        state: 현재 에이전트 상태

    Returns:
        업데이트된 상태 dict:
        - final_plan: str
        - executive_summary: str
        - references: list[dict]
        - evidence_trace: dict
    """
    hypothesis = state.get("hypothesis")
    test_questions = state.get("test_questions", [])
    experiment_designs = state.get("experiment_designs", [])
    measurements = state.get("measurements", [])
    feasibility = state.get("feasibility")
    evidence_packs = state.get("evidence_packs", [])
    approval_status = state.get("approval_status")

    logger.info("Synthesizing final study plan")

    try:
        client = AsyncOpenAI(api_key=settings.openai_api_key)

        # 데이터 준비
        hyp_dict = {}
        if hypothesis:
            hyp_dict = {
                "original_text": hypothesis.original_text,
                "independent_variable": hypothesis.independent_variable,
                "dependent_variable": hypothesis.dependent_variable,
                "mechanism_pathway": hypothesis.mechanism_pathway,
                "population": hypothesis.population,
            }

        tq_list = [
            {
                "category": q.category.value,
                "question": q.question,
                "decision_rule": q.decision_rule,
                "priority": q.priority,
            }
            for q in test_questions
        ]

        experiments_list = []
        for exp in experiment_designs:
            exp_dict = {
                "experiment_id": exp.experiment_id,
                "experiment_type": exp.experiment_type.value,
                "title": exp.title,
                "objective": exp.objective,
                "test_category": exp.test_category.value,
                "model_system": exp.model_system,
                "treatment_protocol": exp.treatment_protocol,
                "control_groups": [cg.name for cg in exp.control_groups],
                "primary_endpoint": exp.primary_endpoint,
                "secondary_endpoints": exp.secondary_endpoints,
                "estimated_timeline": exp.estimated_timeline,
                "estimated_cost_level": exp.estimated_cost_level.value,
                "evidence_snippet_ids": exp.evidence_snippet_ids,
            }
            experiments_list.append(exp_dict)

        measurements_list = [
            {
                "name": m.name,
                "method": m.method,
                "timing": m.timing,
                "expected_change": m.expected_change,
            }
            for m in measurements
        ]

        feasibility_dict = {}
        if feasibility:
            feasibility_dict = {
                "overall_score": feasibility.overall_score,
                "technical_concerns": feasibility.technical_concerns,
                "resource_concerns": feasibility.resource_concerns,
                "timeline_concerns": feasibility.timeline_concerns,
                "risk_mitigation": feasibility.risk_mitigation,
            }

        packs_list = [
            {
                "paper_id": p.paper_id,
                "title": p.title,
                "journal": p.journal,
                "year": p.year,
                "key_finding": p.key_finding,
            }
            for p in evidence_packs
        ]

        user_prompt = SYNTHESIZE_PLAN_USER.format(
            hypothesis=json.dumps(hyp_dict, ensure_ascii=False, indent=2),
            test_questions=json.dumps(tq_list, ensure_ascii=False, indent=2),
            experiment_designs=json.dumps(experiments_list, ensure_ascii=False, indent=2),
            measurements=json.dumps(measurements_list, ensure_ascii=False, indent=2),
            feasibility=json.dumps(feasibility_dict, ensure_ascii=False, indent=2),
            evidence_packs=json.dumps(packs_list, ensure_ascii=False, indent=2),
            approval_status=approval_status.value if approval_status else "approved",
        )

        response = await client.chat.completions.create(
            model=settings.openai_chat_model,
            messages=[
                {"role": "system", "content": SYNTHESIZE_PLAN_SYSTEM},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.4,
        )

        final_plan = response.choices[0].message.content

        # Executive summary 추출 (첫 섹션)
        executive_summary = ""
        if "## Executive Summary" in final_plan:
            start = final_plan.find("## Executive Summary")
            end = final_plan.find("##", start + 1)
            if end == -1:
                end = len(final_plan)
            executive_summary = final_plan[start:end].replace("## Executive Summary", "").strip()
        elif "## 1." in final_plan:
            # 첫 문단 사용
            lines = final_plan.split("\n")
            for i, line in enumerate(lines):
                if line.startswith("## 1."):
                    executive_summary = "\n".join(lines[1:i]).strip()
                    break

        # References 수집
        references = [
            {
                "paper_id": p.paper_id,
                "title": p.title,
                "journal": p.journal,
                "year": p.year,
            }
            for p in evidence_packs
        ]

        # Evidence trace 구축
        evidence_trace = {}
        for i, exp in enumerate(experiment_designs):
            section_id = f"experiment_{i + 1}"
            evidence_trace[section_id] = exp.evidence_snippet_ids

        logger.info(f"Synthesized plan: {len(final_plan)} chars, {len(references)} refs")

        return {
            "final_plan": final_plan,
            "executive_summary": executive_summary,
            "references": references,
            "evidence_trace": evidence_trace,
            "status_detail": "plan_synthesized",
        }

    except Exception as e:
        logger.error(f"Error synthesizing plan: {e}")
        return {
            "final_plan": "계획서 생성 중 오류가 발생했습니다.",
            "executive_summary": "",
            "references": [],
            "evidence_trace": {},
            "error": str(e),
            "status_detail": "synthesis_error",
        }
