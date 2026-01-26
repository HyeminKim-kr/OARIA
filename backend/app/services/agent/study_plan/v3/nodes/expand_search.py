"""Node 5: expand_search - 검색 쿼리 확장 (Loop 1)"""

import json
import logging

from openai import AsyncOpenAI

from app.config import settings

from ..prompts import EXPAND_SEARCH_SYSTEM, EXPAND_SEARCH_USER
from ..state import StudyPlanState

logger = logging.getLogger(__name__)


async def expand_search(state: StudyPlanState) -> dict:
    """
    검색 커버리지가 부족할 때 쿼리를 확장합니다.

    Args:
        state: 현재 에이전트 상태

    Returns:
        업데이트된 상태 dict:
        - expanded_queries: list[str]
        - search_expand_count: int
    """
    gap_notes = state.get("search_gap_notes", [])
    existing_queries = state.get("search_queries", [])
    test_questions = state.get("test_questions", [])
    hypothesis = state.get("hypothesis")
    search_expand_count = state.get("search_expand_count", 0)

    logger.info(f"Expanding search queries (current expand_count={search_expand_count})")

    try:
        client = AsyncOpenAI(api_key=settings.openai_api_key)

        hyp_dict = {}
        if hypothesis:
            hyp_dict = {
                "original_text": hypothesis.original_text,
                "expanded_keywords": hypothesis.expanded_keywords,
                "gene_aliases": hypothesis.gene_aliases,
                "pathway_names": hypothesis.pathway_names,
            }

        tq_list = [
            {"category": q.category.value, "question": q.question}
            for q in test_questions
        ]

        user_prompt = EXPAND_SEARCH_USER.format(
            search_gap_notes=gap_notes,
            existing_queries=existing_queries,
            test_questions=json.dumps(tq_list, ensure_ascii=False),
            hypothesis=json.dumps(hyp_dict, ensure_ascii=False),
        )

        response = await client.chat.completions.create(
            model=settings.openai_chat_model,
            messages=[
                {"role": "system", "content": EXPAND_SEARCH_SYSTEM},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.5,
            response_format={"type": "json_object"},
        )

        result = json.loads(response.choices[0].message.content)
        new_queries = result.get("expanded_queries", [])

        logger.info(f"Generated {len(new_queries)} expanded queries")

        return {
            "expanded_queries": new_queries,
            "search_expand_count": search_expand_count + 1,
            "status_detail": "search_expanding",
        }

    except Exception as e:
        logger.error(f"Error expanding search: {e}")
        return {
            "expanded_queries": [],
            "search_expand_count": search_expand_count + 1,
            "error": str(e),
            "status_detail": "expand_error",
        }
