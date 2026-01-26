"""Node 7: analyze_methodologies - 방법론 분석"""

import json
import logging

from openai import AsyncOpenAI

from app.config import settings

from ..prompts import ANALYZE_METHODOLOGIES_SYSTEM, ANALYZE_METHODOLOGIES_USER
from ..state import MethodologyPattern, StudyPlanState

logger = logging.getLogger(__name__)


async def analyze_methodologies(state: StudyPlanState) -> dict:
    """
    Evidence Pack에서 방법론 패턴을 분석합니다.

    Args:
        state: 현재 에이전트 상태

    Returns:
        업데이트된 상태 dict:
        - methodology_patterns: list[MethodologyPattern]
        - common_biomarkers: list[str]
        - common_techniques: list[str]
        - methodology_gaps: list[str]
    """
    evidence_packs = state.get("evidence_packs", [])
    evidence_summary = state.get("evidence_summary")
    hypothesis = state.get("hypothesis")

    logger.info(f"Analyzing methodologies from {len(evidence_packs)} evidence packs")

    try:
        client = AsyncOpenAI(api_key=settings.openai_api_key)

        # Evidence packs 요약
        packs_summary = [
            {
                "paper_id": p.paper_id,
                "title": p.title,
                "model_used": p.model_used,
                "perturbation_used": p.perturbation_used,
                "readout_used": p.readout_used,
                "key_finding": p.key_finding,
            }
            for p in evidence_packs[:15]
        ]

        # Evidence summary dict 변환
        summary_dict = {}
        if evidence_summary:
            summary_dict = {
                "models": evidence_summary.models,
                "perturbations": evidence_summary.perturbations,
                "readouts": evidence_summary.readouts,
                "results": evidence_summary.results,
            }

        hyp_dict = {}
        if hypothesis:
            hyp_dict = {
                "original_text": hypothesis.original_text,
                "independent_variable": hypothesis.independent_variable,
                "dependent_variable": hypothesis.dependent_variable,
            }

        user_prompt = ANALYZE_METHODOLOGIES_USER.format(
            evidence_packs=json.dumps(packs_summary, ensure_ascii=False, indent=2),
            evidence_summary=json.dumps(summary_dict, ensure_ascii=False, indent=2),
            hypothesis=json.dumps(hyp_dict, ensure_ascii=False),
        )

        response = await client.chat.completions.create(
            model=settings.openai_chat_model,
            messages=[
                {"role": "system", "content": ANALYZE_METHODOLOGIES_SYSTEM},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.3,
            response_format={"type": "json_object"},
        )

        result = json.loads(response.choices[0].message.content)

        # MethodologyPattern 객체 생성
        patterns = []
        for p in result.get("methodology_patterns", []):
            patterns.append(
                MethodologyPattern(
                    pattern_name=p.get("pattern_name", ""),
                    frequency=p.get("frequency", 1),
                    papers=p.get("papers", []),
                    description=p.get("description", ""),
                )
            )

        common_biomarkers = result.get("common_biomarkers", [])
        common_techniques = result.get("common_techniques", [])
        methodology_gaps = result.get("methodology_gaps", [])

        logger.info(
            f"Found {len(patterns)} patterns, "
            f"{len(common_biomarkers)} biomarkers, "
            f"{len(common_techniques)} techniques"
        )

        return {
            "methodology_patterns": patterns,
            "common_biomarkers": common_biomarkers,
            "common_techniques": common_techniques,
            "methodology_gaps": methodology_gaps,
            "status_detail": "methodologies_analyzed",
        }

    except Exception as e:
        logger.error(f"Error analyzing methodologies: {e}")
        return {
            "methodology_patterns": [],
            "common_biomarkers": [],
            "common_techniques": [],
            "methodology_gaps": [],
            "error": str(e),
            "status_detail": "methodology_error",
        }
