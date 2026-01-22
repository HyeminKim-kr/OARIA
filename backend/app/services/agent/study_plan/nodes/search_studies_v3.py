"""Node: search_studies_v3 - 3-tier 검색 + DP1 라우터 통합

v2.1 search_prior_studies를 확장하여:
- 3-tier 검색 (RAG → EPMC → Web)
- DP1 Router 연동
- Budget/Cache 관리
"""

import json
import logging
from typing import Any

from langchain_openai import ChatOpenAI
from openai import AsyncOpenAI

from app.config import settings

from ..prompts import GENERATE_SEARCH_QUERIES_SYSTEM, GENERATE_SEARCH_QUERIES_USER
from ..state import StudyPlanState
from ..search import (
    SearchTier,
    SearchObjective,
    DP1RouterInput,
    multi_tier_search,
    budget_manager,
)
from ..routers import DP1SearchRouter

logger = logging.getLogger(__name__)


async def search_studies_v3(state: StudyPlanState) -> dict:
    """
    3-tier 검색 + DP1 라우터 통합 노드.

    1. RAG 검색 수행
    2. DP1 Router로 승격 여부 결정
    3. 필요시 EPMC/Web 검색
    4. 결과 통합

    Args:
        state: 현재 에이전트 상태

    Returns:
        업데이트된 상태 dict
    """
    hypothesis = state.get("hypothesis")
    test_questions = state.get("test_questions", [])
    expanded_queries = state.get("expanded_queries", [])
    search_expand_count = state.get("search_expand_count", 0)
    run_id = state.get("run_id", "")

    logger.info(f"search_studies_v3 run_id={run_id} expand_count={search_expand_count}")

    try:
        # 0. Budget 초기화
        await budget_manager.init_run(run_id)

        # 1. 검색 쿼리 생성 (첫 검색 시에만)
        if not expanded_queries:
            queries = await _generate_search_queries(hypothesis, test_questions)
        else:
            base_queries = state.get("search_queries", [])
            queries = list(set(base_queries + expanded_queries))

        # 2. Tier 1: RAG 검색
        hypothesis_text = hypothesis.original_text if hypothesis else ""
        rag_result = await multi_tier_search.search_tier1_rag(
            queries=queries,
            hypothesis=hypothesis_text,
            run_id=run_id,
        )

        # 3. DP1 Router 결정
        llm = ChatOpenAI(
            model=settings.openai_chat_model,
            api_key=settings.openai_api_key,
            temperature=0.2,
        )
        dp1_router = DP1SearchRouter(llm)

        # 응답된 질문 계산 (간단한 휴리스틱)
        answered_questions = _estimate_answered_questions(
            rag_result.snippets, test_questions
        )

        dp1_input = DP1RouterInput(
            current_tier=SearchTier.RAG,
            coverage_score=rag_result.coverage_score,
            evidence_density=rag_result.evidence_density,
            test_questions=[q.question for q in test_questions],
            answered_questions=answered_questions,
            web_budget_remaining=await budget_manager.get_remaining(run_id, SearchTier.WEB),
            epmc_budget_remaining=await budget_manager.get_remaining(run_id, SearchTier.EPMC),
        )

        dp1_decision = await dp1_router.route(dp1_input, hypothesis_text, run_id)
        dp1_decisions = [dp1_decision.to_dict()]

        # 4. 승격 검색 수행
        all_snippets = list(rag_result.snippets)
        tier_history = [SearchTier.RAG.value]
        current_tier = SearchTier.RAG
        epmc_count = 0
        web_count = 0
        web_limit_exceeded = False

        if dp1_decision.decision == "upgrade_to_epmc" and dp1_decision.query_plan:
            epmc_result = await multi_tier_search.search_tier2_epmc(
                query_plan=dp1_decision.query_plan,
                hypothesis=hypothesis_text,
                run_id=run_id,
            )
            all_snippets.extend(epmc_result.snippets)
            tier_history.append(SearchTier.EPMC.value)
            current_tier = SearchTier.EPMC
            epmc_count = 1

            # EPMC 후 다시 DP1 평가
            dp1_input_2 = DP1RouterInput(
                current_tier=SearchTier.EPMC,
                coverage_score=epmc_result.coverage_score,
                evidence_density=len(all_snippets),
                test_questions=[q.question for q in test_questions],
                answered_questions=_estimate_answered_questions(all_snippets, test_questions),
                web_budget_remaining=await budget_manager.get_remaining(run_id, SearchTier.WEB),
                epmc_budget_remaining=await budget_manager.get_remaining(run_id, SearchTier.EPMC),
            )
            dp1_decision_2 = await dp1_router.route(dp1_input_2, hypothesis_text, run_id)
            dp1_decisions.append(dp1_decision_2.to_dict())

            if dp1_decision_2.decision == "upgrade_to_web" and dp1_decision_2.query_plan:
                web_result = await multi_tier_search.search_tier3_web(
                    query=dp1_decision_2.query_plan.primary_query,
                    hypothesis=hypothesis_text,
                    run_id=run_id,
                )
                all_snippets.extend(web_result.snippets)
                tier_history.append(SearchTier.WEB.value)
                current_tier = SearchTier.WEB
                web_count = 1
            elif dp1_decision_2.decision == "skip_web_limit":
                web_limit_exceeded = True

        elif dp1_decision.decision == "skip_web_limit":
            web_limit_exceeded = True

        # 5. prior_studies 형식으로 변환 (v2 호환)
        prior_studies = _convert_to_prior_studies(all_snippets)

        # 6. 최종 coverage 계산
        final_coverage = multi_tier_search._calculate_coverage(all_snippets)

        logger.info(
            f"search_v3 complete: tier={current_tier.name} "
            f"snippets={len(all_snippets)} coverage={final_coverage:.2f} "
            f"web_exceeded={web_limit_exceeded}"
        )

        return {
            "search_queries": queries,
            "prior_studies": prior_studies,
            "search_coverage_score": final_coverage,
            "search_gap_notes": [],
            "search_expand_count": search_expand_count,
            # v3 필드
            "search_tier_history": tier_history,
            "evidence_snippets_v3": [s.to_dict() for s in all_snippets],
            "current_tier": current_tier.value,
            "run_epmc_count": epmc_count,
            "run_web_count": web_count,
            "dp1_decisions": dp1_decisions,
            "web_limit_exceeded": web_limit_exceeded,
            "status_detail": "studies_searched_v3",
        }

    except Exception as e:
        logger.error(f"Error in search_studies_v3: {e}")
        return {
            "search_queries": [],
            "prior_studies": [],
            "search_coverage_score": 0.0,
            "search_gap_notes": ["검색 중 오류 발생"],
            "search_tier_history": [],
            "evidence_snippets_v3": [],
            "current_tier": 1,
            "dp1_decisions": [],
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
        if hypothesis:
            return hypothesis.keywords[:5]
        return []


def _estimate_answered_questions(snippets: list, test_questions: list) -> list[str]:
    """스니펫 기반으로 응답된 질문 추정 (간단한 휴리스틱)"""
    answered = []
    snippet_texts = " ".join(s.text.lower() if hasattr(s, 'text') else s.get('text', '').lower() for s in snippets)

    for tq in test_questions:
        # 키워드 매칭으로 간단히 판단
        keywords = tq.question.lower().split()[:5]
        matches = sum(1 for kw in keywords if kw in snippet_texts)
        if matches >= 2:
            answered.append(tq.question)

    return answered


def _convert_to_prior_studies(snippets: list) -> list[dict]:
    """EvidenceSnippetV3를 prior_studies 형식으로 변환"""
    # paper_id별로 그룹화
    paper_map = {}

    for s in snippets:
        if hasattr(s, 'paper_id'):
            paper_id = s.paper_id
            snippet_dict = s.to_dict()
        else:
            paper_id = s.get('paper_id')
            snippet_dict = s

        if not paper_id:
            paper_id = snippet_dict.get('url', f"web_{snippet_dict.get('snippet_id', '')}")

        if paper_id not in paper_map:
            paper_map[paper_id] = {
                "paper_id": paper_id,
                "title": snippet_dict.get('title', ''),
                "journal": snippet_dict.get('journal', ''),
                "year": snippet_dict.get('year', 0),
                "relevance_score": snippet_dict.get('relevance_score', 0.5),
                "abstract": snippet_dict.get('text', '')[:500],
                "section": snippet_dict.get('section', ''),
                "all_snippets": [],
            }

        paper_map[paper_id]["all_snippets"].append({
            "snippet_id": snippet_dict.get('snippet_id', ''),
            "section": snippet_dict.get('section', ''),
            "text": snippet_dict.get('text', ''),
            "relevance_score": snippet_dict.get('relevance_score', 0.5),
        })

    return list(paper_map.values())
