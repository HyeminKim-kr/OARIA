"""Node 4: search_prior_studies - 유사 연구 RAG 검색"""

import asyncio
import json
import logging
from typing import Any

from openai import AsyncOpenAI

from app.config import settings

from ..prompts import GENERATE_SEARCH_QUERIES_SYSTEM, GENERATE_SEARCH_QUERIES_USER
from ...shared.rag import study_search_service
from ..state import StudyPlanState

logger = logging.getLogger(__name__)


async def search_prior_studies(state: StudyPlanState) -> dict:
    """
    유사 연구를 RAG로 검색하고 커버리지를 평가합니다.

    Args:
        state: 현재 에이전트 상태

    Returns:
        업데이트된 상태 dict:
        - search_queries: list[str]
        - prior_studies: list[dict]
        - search_coverage_score: float
        - search_gap_notes: list[str]
    """
    hypothesis = state.get("hypothesis")
    test_questions = state.get("test_questions", [])
    expanded_queries = state.get("expanded_queries", [])
    search_expand_count = state.get("search_expand_count", 0)

    logger.info(f"Searching prior studies (expand_count={search_expand_count})")

    try:
        # 1. 검색 쿼리 생성 (첫 검색 시에만)
        if not expanded_queries:
            queries = await _generate_search_queries(hypothesis, test_questions)
        else:
            # 기존 쿼리 + 확장 쿼리
            base_queries = state.get("search_queries", [])
            queries = list(set(base_queries + expanded_queries))

        # 2. RAG 검색 수행 (커버리지 점수도 함께 반환)
        prior_studies, rag_coverage = await _execute_rag_search(queries)

        # 3. 커버리지 평가 (RAG 점수와 휴리스틱 점수 결합)
        heuristic_coverage, gap_notes = _assess_coverage(prior_studies, test_questions)
        # RAG 서비스 점수와 휴리스틱 점수의 가중 평균
        coverage_score = rag_coverage * 0.6 + heuristic_coverage * 0.4

        logger.info(
            f"Found {len(prior_studies)} studies, "
            f"coverage={coverage_score:.2f}, gaps={len(gap_notes)}"
        )

        return {
            "search_queries": queries,
            "prior_studies": prior_studies,
            "search_coverage_score": coverage_score,
            "search_gap_notes": gap_notes,
            "search_expand_count": search_expand_count,
            "status_detail": "studies_searched",
        }

    except Exception as e:
        logger.error(f"Error searching studies: {e}")
        return {
            "search_queries": [],
            "prior_studies": [],
            "search_coverage_score": 0.0,
            "search_gap_notes": ["검색 중 오류 발생"],
            "error": str(e),
            "status_detail": "search_error",
        }


async def _generate_search_queries(hypothesis: Any, test_questions: list) -> list[str]:
    """LLM을 사용하여 검색 쿼리 생성"""
    try:
        client = AsyncOpenAI(api_key=settings.openai_api_key)

        hyp_dict = {}
        if hypothesis:
            hyp_dict = {
                "original_text": hypothesis.original_text,
                "keywords": hypothesis.keywords,
                "expanded_keywords": hypothesis.expanded_keywords,
                "gene_aliases": hypothesis.gene_aliases,
            }

        tq_list = [
            {"category": q.category.value, "question": q.question}
            for q in test_questions
        ]

        user_prompt = GENERATE_SEARCH_QUERIES_USER.format(
            hypothesis=json.dumps(hyp_dict, ensure_ascii=False),
            test_questions=json.dumps(tq_list, ensure_ascii=False),
            expanded_keywords=hyp_dict.get("expanded_keywords", []),
        )

        response = await client.chat.completions.create(
            model=settings.openai_chat_model,
            messages=[
                {"role": "system", "content": GENERATE_SEARCH_QUERIES_SYSTEM},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.4,
            response_format={"type": "json_object"},
        )

        result = json.loads(response.choices[0].message.content)
        return result.get("queries", [])

    except Exception as e:
        logger.error(f"Error generating queries: {e}")
        # Fallback: 키워드 기반 쿼리
        if hypothesis:
            return hypothesis.keywords[:5]
        return []


async def _execute_rag_search(queries: list[str]) -> tuple[list[dict], float]:
    """Study Plan 전용 RAG 서비스를 사용하여 검색 수행

    여러 쿼리로 검색하고 결과를 통합합니다.

    Returns:
        tuple[list[dict], float]: (prior_studies, coverage_score)
    """
    try:
        logger.info(f"Executing RAG search with {len(queries)} queries")

        # Study Plan 전용 검색 서비스 사용
        result = await study_search_service.search_studies(queries=queries)

        # SearchResult를 prior_studies 형식으로 변환
        prior_studies = result.to_prior_studies()

        logger.info(
            f"RAG search found {len(prior_studies)} papers, "
            f"{result.total_snippets} snippets, "
            f"coverage={result.coverage_score:.2f}"
        )

        return prior_studies, result.coverage_score

    except Exception as e:
        logger.error(f"Error in RAG search: {e}")
        return [], 0.0


def _assess_coverage(
    prior_studies: list[dict],
    test_questions: list,
) -> tuple[float, list[str]]:
    """검색 결과의 커버리지 평가"""
    if not test_questions:
        return 1.0, []

    # 간단한 휴리스틱: 논문 수 기반
    # 실제 구현에서는 각 test_question과의 관련성 평가 필요
    study_count = len(prior_studies)

    if study_count >= 15:
        coverage = 0.9
    elif study_count >= 10:
        coverage = 0.75
    elif study_count >= 5:
        coverage = 0.6
    elif study_count >= 3:
        coverage = 0.4
    else:
        coverage = 0.2

    gaps = []
    if coverage < 0.6:
        # 어떤 test_question에 대한 연구가 부족한지 확인
        for tq in test_questions:
            # TODO: 실제 관련성 평가 로직
            gaps.append(f"'{tq.category.value}' 검증 관련 연구 부족 가능")

    return coverage, gaps
