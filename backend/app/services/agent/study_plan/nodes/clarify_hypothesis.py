"""Node 2: clarify_hypothesis - 가설 명확화 질문 생성 (Loop 0)"""

import json
import logging

from openai import AsyncOpenAI

from app.config import settings

from ..prompts import CLARIFY_HYPOTHESIS_SYSTEM, CLARIFY_HYPOTHESIS_USER
from ..state import StudyPlanState

logger = logging.getLogger(__name__)


async def clarify_hypothesis(state: StudyPlanState) -> dict:
    """
    가설이 불명확할 때 명확화 질문을 생성합니다.

    Args:
        state: 현재 에이전트 상태

    Returns:
        업데이트된 상태 dict:
        - clarification_questions: list[str]
        - clarification_count: int
        - clarification_needed: bool (루프 탈출용)
        - status_detail: str
    """
    hypothesis = state.get("hypothesis")
    confidence = state.get("hypothesis_confidence", 0.0)
    existing_questions = state.get("clarification_questions", [])
    clarification_count = state.get("clarification_count", 0)

    logger.info(f"Generating clarification questions (confidence={confidence})")

    try:
        client = AsyncOpenAI(api_key=settings.openai_api_key)

        # hypothesis를 dict로 변환
        hyp_dict = {}
        if hypothesis:
            hyp_dict = {
                "original_text": hypothesis.original_text,
                "independent_variable": hypothesis.independent_variable,
                "dependent_variable": hypothesis.dependent_variable,
                "population": hypothesis.population,
                "mechanism_pathway": hypothesis.mechanism_pathway,
            }

        user_prompt = CLARIFY_HYPOTHESIS_USER.format(
            hypothesis=json.dumps(hyp_dict, ensure_ascii=False, indent=2),
            confidence=confidence,
            existing_questions=existing_questions,
        )

        response = await client.chat.completions.create(
            model=settings.openai_chat_model,
            messages=[
                {"role": "system", "content": CLARIFY_HYPOTHESIS_SYSTEM},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.5,
            response_format={"type": "json_object"},
        )

        result = json.loads(response.choices[0].message.content)
        questions = result.get("clarification_questions", [])

        logger.info(f"Generated {len(questions)} clarification questions")

        # clarification_count 증가 및 루프 탈출 조건 설정
        # 한 번 clarify를 거치면 더 이상 루프하지 않음 (사용자 입력 없이는 개선 불가)
        return {
            "clarification_questions": questions,
            "clarification_count": clarification_count + 1,
            "clarification_needed": False,  # 루프 탈출: 사용자 입력 없이 계속 루프 방지
            "status_detail": "awaiting_clarification",
        }

    except Exception as e:
        logger.error(f"Error generating clarification questions: {e}")
        return {
            "clarification_questions": ["가설에 대해 더 자세히 설명해주세요."],
            "clarification_count": clarification_count + 1,
            "clarification_needed": False,  # 에러 시에도 루프 탈출
            "error": str(e),
            "status_detail": "clarify_error",
        }
