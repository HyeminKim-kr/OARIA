"""Node 10: identify_measurements - 측정 항목 식별"""

import json
import logging

from openai import AsyncOpenAI

from app.config import settings

from ..prompts import IDENTIFY_MEASUREMENTS_SYSTEM, IDENTIFY_MEASUREMENTS_USER
from ..state import MeasurementItem, StudyPlanState

logger = logging.getLogger(__name__)


async def identify_measurements(state: StudyPlanState) -> dict:
    """
    실험 설계에 필요한 측정 항목을 식별합니다.

    Args:
        state: 현재 에이전트 상태

    Returns:
        업데이트된 상태 dict:
        - measurements: list[MeasurementItem]
        - measurement_priority: list[str]
    """
    experiment_designs = state.get("experiment_designs", [])
    test_questions = state.get("test_questions", [])
    common_biomarkers = state.get("common_biomarkers", [])

    logger.info("Identifying required measurements")

    try:
        client = AsyncOpenAI(api_key=settings.openai_api_key)

        # 데이터 준비
        experiments_list = []
        for exp in experiment_designs:
            exp_dict = {
                "experiment_id": exp.experiment_id,
                "title": exp.title,
                "test_category": exp.test_category.value,
                "primary_endpoint": exp.primary_endpoint,
                "secondary_endpoints": exp.secondary_endpoints,
                "model_system": exp.model_system,
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

        user_prompt = IDENTIFY_MEASUREMENTS_USER.format(
            experiment_designs=json.dumps(experiments_list, ensure_ascii=False, indent=2),
            test_questions=json.dumps(tq_list, ensure_ascii=False, indent=2),
            common_biomarkers=common_biomarkers,
        )

        response = await client.chat.completions.create(
            model=settings.openai_chat_model,
            messages=[
                {"role": "system", "content": IDENTIFY_MEASUREMENTS_SYSTEM},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.3,
            response_format={"type": "json_object"},
        )

        result = json.loads(response.choices[0].message.content)

        # MeasurementItem 객체 생성
        measurements = []
        for m in result.get("measurements", []):
            measurements.append(
                MeasurementItem(
                    category=m.get("category", ""),
                    name=m.get("name", ""),
                    method=m.get("method", ""),
                    rationale=m.get("rationale", ""),
                    timing=m.get("timing", ""),
                    expected_change=m.get("expected_change", ""),
                    reference_range=m.get("reference_range"),
                    evidence_snippet_ids=m.get("evidence_snippet_ids", []),
                    based_on_studies=m.get("based_on_studies", []),
                )
            )

        measurement_priority = result.get("measurement_priority", [])

        logger.info(f"Identified {len(measurements)} measurements")

        return {
            "measurements": measurements,
            "measurement_priority": measurement_priority,
            "status_detail": "measurements_identified",
        }

    except Exception as e:
        logger.error(f"Error identifying measurements: {e}")
        return {
            "measurements": [],
            "measurement_priority": [],
            "error": str(e),
            "status_detail": "measurement_error",
        }
