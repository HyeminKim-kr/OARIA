"""Node 3: decompose_to_test_questions - 검증 질문 분해 (NSPE)"""

import json
import logging

from openai import AsyncOpenAI

from app.config import settings

from ..prompts import DECOMPOSE_TEST_QUESTIONS_SYSTEM, DECOMPOSE_TEST_QUESTIONS_USER
from ..state import StudyPlanState, TestCategory, TestQuestion

logger = logging.getLogger(__name__)


async def decompose_to_test_questions(state: StudyPlanState) -> dict:
    """
    가설을 Necessity/Sufficiency/Epistasis/Specificity 검증 질문으로 분해합니다.

    Args:
        state: 현재 에이전트 상태

    Returns:
        업데이트된 상태 dict:
        - test_questions: list[TestQuestion]
    """
    hypothesis = state.get("hypothesis")
    research_context = state.get("research_context") or "없음"
    preferred_types = state.get("preferred_experiment_types", [])

    logger.info("Decomposing hypothesis into test questions (NSPE)")

    try:
        client = AsyncOpenAI(api_key=settings.openai_api_key)

        # hypothesis를 dict로 변환
        hyp_dict = {}
        if hypothesis:
            hyp_dict = {
                "original_text": hypothesis.original_text,
                "independent_variable": hypothesis.independent_variable,
                "dependent_variable": hypothesis.dependent_variable,
                "mediating_variables": hypothesis.mediating_variables,
                "population": hypothesis.population,
                "mechanism_pathway": hypothesis.mechanism_pathway,
                "keywords": hypothesis.keywords,
            }

        user_prompt = DECOMPOSE_TEST_QUESTIONS_USER.format(
            hypothesis=json.dumps(hyp_dict, ensure_ascii=False, indent=2),
            research_context=research_context,
            preferred_experiment_types=[t.value if hasattr(t, "value") else str(t) for t in preferred_types],
        )

        response = await client.chat.completions.create(
            model=settings.openai_chat_model,
            messages=[
                {"role": "system", "content": DECOMPOSE_TEST_QUESTIONS_SYSTEM},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.4,
            response_format={"type": "json_object"},
        )

        result = json.loads(response.choices[0].message.content)
        raw_questions = result.get("test_questions", [])

        # TestQuestion 객체로 변환
        test_questions = []
        for q in raw_questions:
            try:
                category = TestCategory(q.get("category", "necessity"))
            except ValueError:
                category = TestCategory.NECESSITY

            test_questions.append(
                TestQuestion(
                    category=category,
                    question=q.get("question", ""),
                    rationale=q.get("rationale", ""),
                    decision_rule=q.get("decision_rule", ""),
                    suggested_approach=q.get("suggested_approach", ""),
                    priority=q.get("priority", 1),
                )
            )

        logger.info(f"Generated {len(test_questions)} test questions")

        return {
            "test_questions": test_questions,
            "status_detail": "tests_decomposed",
        }

    except Exception as e:
        logger.error(f"Error decomposing test questions: {e}")
        return {
            "test_questions": [],
            "error": str(e),
            "status_detail": "decompose_error",
        }
