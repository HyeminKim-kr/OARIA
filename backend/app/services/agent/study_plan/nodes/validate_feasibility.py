"""Node 11: validate_feasibility - 실현 가능성 평가"""

import json
import logging

from openai import AsyncOpenAI

from app.config import settings

from ..prompts import VALIDATE_FEASIBILITY_SYSTEM, VALIDATE_FEASIBILITY_USER
from ..state import FeasibilityAssessment, StudyPlanState

logger = logging.getLogger(__name__)


async def validate_feasibility(state: StudyPlanState) -> dict:
    """
    실험 계획의 실현 가능성을 평가합니다.

    Args:
        state: 현재 에이전트 상태

    Returns:
        업데이트된 상태 dict:
        - feasibility: FeasibilityAssessment
    """
    experiment_designs = state.get("experiment_designs", [])
    measurements = state.get("measurements", [])
    constraints = state.get("constraints", [])

    logger.info("Validating feasibility")

    try:
        client = AsyncOpenAI(api_key=settings.openai_api_key)

        # 데이터 준비
        experiments_list = []
        for exp in experiment_designs:
            exp_dict = {
                "experiment_id": exp.experiment_id,
                "experiment_type": exp.experiment_type.value,
                "title": exp.title,
                "model_system": exp.model_system,
                "estimated_timeline": exp.estimated_timeline,
                "estimated_cost_level": exp.estimated_cost_level.value,
                "technical_difficulty": exp.technical_difficulty,
            }
            experiments_list.append(exp_dict)

        measurements_list = [
            {
                "name": m.name,
                "method": m.method,
                "timing": m.timing,
            }
            for m in measurements
        ]

        user_prompt = VALIDATE_FEASIBILITY_USER.format(
            experiment_designs=json.dumps(experiments_list, ensure_ascii=False, indent=2),
            measurements=json.dumps(measurements_list, ensure_ascii=False, indent=2),
            constraints=constraints,
        )

        response = await client.chat.completions.create(
            model=settings.openai_chat_model,
            messages=[
                {"role": "system", "content": VALIDATE_FEASIBILITY_SYSTEM},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.3,
            response_format={"type": "json_object"},
        )

        result = json.loads(response.choices[0].message.content)

        feasibility = FeasibilityAssessment(
            overall_score=result.get("overall_score", 0.5),
            technical_feasibility=result.get("technical_feasibility", 0.5),
            technical_concerns=result.get("technical_concerns", []),
            resource_feasibility=result.get("resource_feasibility", 0.5),
            resource_concerns=result.get("resource_concerns", []),
            timeline_feasibility=result.get("timeline_feasibility", 0.5),
            timeline_concerns=result.get("timeline_concerns", []),
            ethical_considerations=result.get("ethical_considerations", []),
            alternative_approaches=result.get("alternative_approaches", []),
            risk_mitigation=result.get("risk_mitigation", []),
        )

        logger.info(f"Feasibility validated: overall_score={feasibility.overall_score:.2f}")

        return {
            "feasibility": feasibility,
            "status_detail": "feasibility_validated",
        }

    except Exception as e:
        logger.error(f"Error validating feasibility: {e}")
        return {
            "feasibility": FeasibilityAssessment(
                overall_score=0.5,
                technical_feasibility=0.5,
                resource_feasibility=0.5,
                timeline_feasibility=0.5,
            ),
            "error": str(e),
            "status_detail": "feasibility_error",
        }
