"""Node 1: parse_hypothesis - 가설 파싱 및 구조화"""

import json
import logging

from openai import AsyncOpenAI

from app.config import settings

from ..prompts import PARSE_HYPOTHESIS_SYSTEM, PARSE_HYPOTHESIS_USER
from ..state import HypothesisStructure, StudyPlanState

logger = logging.getLogger(__name__)


async def parse_hypothesis(state: StudyPlanState) -> dict:
    """
    가설을 구조화하고 동의어를 확장합니다.

    Args:
        state: 현재 에이전트 상태 (user_input 필요)

    Returns:
        업데이트된 상태 dict:
        - hypothesis: HypothesisStructure
        - hypothesis_confidence: float
        - clarification_needed: bool
        - clarification_questions: list[str]
    """
    user_input = state.get("user_input", "")
    research_context = state.get("research_context") or "없음"
    constraints = state.get("constraints", [])
    clarification_count = state.get("clarification_count", 0)

    logger.info(f"Parsing hypothesis: {user_input[:100]}...")

    try:
        client = AsyncOpenAI(api_key=settings.openai_api_key)

        user_prompt = PARSE_HYPOTHESIS_USER.format(
            user_input=user_input,
            research_context=research_context,
            constraints=", ".join(constraints) if constraints else "없음",
        )

        response = await client.chat.completions.create(
            model=settings.openai_chat_model,
            messages=[
                {"role": "system", "content": PARSE_HYPOTHESIS_SYSTEM},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.3,
            response_format={"type": "json_object"},
        )

        result = json.loads(response.choices[0].message.content)

        # HypothesisStructure 생성
        hyp_data = result.get("hypothesis", {})
        hypothesis = HypothesisStructure(
            original_text=hyp_data.get("original_text", user_input),
            independent_variable=hyp_data.get("independent_variable", ""),
            dependent_variable=hyp_data.get("dependent_variable", ""),
            mediating_variables=hyp_data.get("mediating_variables", []),
            moderating_variables=hyp_data.get("moderating_variables", []),
            population=hyp_data.get("population", ""),
            mechanism_pathway=hyp_data.get("mechanism_pathway", ""),
            keywords=hyp_data.get("keywords", []),
            expanded_keywords=hyp_data.get("expanded_keywords", []),
            gene_aliases=hyp_data.get("gene_aliases", []),
            pathway_names=hyp_data.get("pathway_names", []),
            assay_keywords=hyp_data.get("assay_keywords", []),
        )

        confidence = result.get("confidence", 0.5)
        # 이미 clarification을 거쳤으면 더 이상 요청하지 않음 (무한 루프 방지)
        if clarification_count > 0:
            clarification_needed = False
            clarification_questions = []
        else:
            clarification_needed = result.get("clarification_needed", confidence < 0.7)
            clarification_questions = result.get("clarification_questions", [])

        logger.info(
            f"Hypothesis parsed: confidence={confidence}, "
            f"clarification_needed={clarification_needed}"
        )

        return {
            "hypothesis": hypothesis,
            "hypothesis_confidence": confidence,
            "clarification_needed": clarification_needed,
            "clarification_questions": clarification_questions,
            "status_detail": "hypothesis_parsed",
        }

    except Exception as e:
        logger.error(f"Error parsing hypothesis: {e}")
        # 에러 시에도 무한 루프 방지
        needs_clarify = clarification_count == 0
        return {
            "hypothesis": HypothesisStructure(
                original_text=user_input,
                independent_variable="",
                dependent_variable="",
            ),
            "hypothesis_confidence": 0.0,
            "clarification_needed": needs_clarify,
            "clarification_questions": ["가설을 더 구체적으로 설명해주세요."] if needs_clarify else [],
            "error": str(e),
            "status_detail": "parse_error",
        }
