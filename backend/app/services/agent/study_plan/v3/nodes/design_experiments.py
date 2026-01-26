"""Node 8: design_experiments - 실험 설계"""

import json
import logging

from openai import AsyncOpenAI

from app.config import settings

from ..prompts import DESIGN_EXPERIMENTS_SYSTEM, DESIGN_EXPERIMENTS_USER
from ..state import (
    ControlGroup,
    ControlType,
    CostBucket,
    ExperimentDesign,
    ExperimentType,
    StudyPlanState,
    TestCategory,
)

logger = logging.getLogger(__name__)


async def design_experiments(state: StudyPlanState) -> dict:
    """
    검증 질문과 방법론 분석을 기반으로 실험을 설계합니다.

    Args:
        state: 현재 에이전트 상태

    Returns:
        업데이트된 상태 dict:
        - experiment_designs: list[ExperimentDesign]
        - design_rationale: str
    """
    hypothesis = state.get("hypothesis")
    test_questions = state.get("test_questions", [])
    methodology_patterns = state.get("methodology_patterns", [])
    common_biomarkers = state.get("common_biomarkers", [])
    common_techniques = state.get("common_techniques", [])
    evidence_summary = state.get("evidence_summary")
    preferred_types = state.get("preferred_experiment_types", [])
    constraints = state.get("constraints", [])

    logger.info("Designing experiments based on test questions and methodologies")

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
            }

        tq_list = [
            {
                "category": q.category.value,
                "question": q.question,
                "decision_rule": q.decision_rule,
                "suggested_approach": q.suggested_approach,
            }
            for q in test_questions
        ]

        patterns_list = [
            {
                "pattern_name": p.pattern_name,
                "frequency": p.frequency,
                "description": p.description,
            }
            for p in methodology_patterns
        ]

        summary_dict = {}
        if evidence_summary:
            summary_dict = {
                "models": evidence_summary.models,
                "perturbations": evidence_summary.perturbations,
                "readouts": evidence_summary.readouts,
            }

        user_prompt = DESIGN_EXPERIMENTS_USER.format(
            hypothesis=json.dumps(hyp_dict, ensure_ascii=False, indent=2),
            test_questions=json.dumps(tq_list, ensure_ascii=False, indent=2),
            methodology_patterns=json.dumps(patterns_list, ensure_ascii=False, indent=2),
            common_biomarkers=common_biomarkers,
            common_techniques=common_techniques,
            evidence_summary=json.dumps(summary_dict, ensure_ascii=False, indent=2),
            preferred_experiment_types=[t.value if hasattr(t, "value") else str(t) for t in preferred_types],
            constraints=constraints,
        )

        response = await client.chat.completions.create(
            model=settings.openai_chat_model,
            messages=[
                {"role": "system", "content": DESIGN_EXPERIMENTS_SYSTEM},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.4,
            response_format={"type": "json_object"},
        )

        result = json.loads(response.choices[0].message.content)

        # ExperimentDesign 객체 생성
        experiments = []
        for exp in result.get("experiments", []):
            try:
                exp_type = ExperimentType(exp.get("experiment_type", "in_vitro"))
            except ValueError:
                exp_type = ExperimentType.IN_VITRO

            try:
                test_cat = TestCategory(exp.get("test_category", "necessity"))
            except ValueError:
                test_cat = TestCategory.NECESSITY

            try:
                cost_level = CostBucket(exp.get("estimated_cost_level", "medium"))
            except ValueError:
                cost_level = CostBucket.MEDIUM

            # Control groups 파싱
            control_groups = []
            for cg in exp.get("control_groups", []):
                try:
                    ctrl_type = ControlType(cg.get("type", "negative"))
                except ValueError:
                    ctrl_type = ControlType.NEGATIVE

                control_groups.append(
                    ControlGroup(
                        control_type=ctrl_type,
                        name=cg.get("name", ""),
                        description=cg.get("description", ""),
                        n=cg.get("n", 6),
                    )
                )

            design = ExperimentDesign(
                experiment_id=exp.get("experiment_id", ""),
                experiment_type=exp_type,
                title=exp.get("title", ""),
                objective=exp.get("objective", ""),
                hypothesis_tested=exp.get("hypothesis_tested", ""),
                test_category=test_cat,
                experimental_groups=exp.get("experimental_groups", []),
                control_groups=control_groups,
                model_system=exp.get("model_system", ""),
                treatment_protocol=exp.get("treatment_protocol", ""),
                duration=exp.get("duration", ""),
                primary_endpoint=exp.get("primary_endpoint", ""),
                secondary_endpoints=exp.get("secondary_endpoints", []),
                statistical_approach=exp.get("statistical_approach", ""),
                sample_size_justification=exp.get("sample_size_justification", ""),
                estimated_timeline=exp.get("estimated_timeline", ""),
                estimated_cost_level=cost_level,
                technical_difficulty=exp.get("technical_difficulty", ""),
                evidence_snippet_ids=exp.get("evidence_snippet_ids", []),
                based_on_studies=exp.get("based_on_studies", []),
            )
            experiments.append(design)

        design_rationale = result.get("design_rationale", "")

        logger.info(f"Designed {len(experiments)} experiments")

        return {
            "experiment_designs": experiments,
            "design_rationale": design_rationale,
            "status_detail": "experiments_designed",
        }

    except Exception as e:
        logger.error(f"Error designing experiments: {e}")
        return {
            "experiment_designs": [],
            "design_rationale": "",
            "error": str(e),
            "status_detail": "design_error",
        }
