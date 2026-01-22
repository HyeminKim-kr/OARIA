"""Node: search_for_controls - DP2 search_for_controls용 추가 검색

DP2 Router가 search_for_controls를 결정했을 때 실행.
프로토콜, 대조군, 근거 보강을 위한 추가 검색.
"""

import logging

from ..state import StudyPlanState
from ..search import (
    SearchTier,
    SearchObjective,
    multi_tier_search,
    budget_manager,
)
from ..routers import DP2CritiqueRouter

logger = logging.getLogger(__name__)


async def search_for_controls(state: StudyPlanState) -> dict:
    """
    DP2 search_for_controls용 추가 검색.

    critique_refine_v3에서 설정한 _dp2_target_gaps를 기반으로
    EPMC/Web 검색을 수행합니다.

    Args:
        state: 현재 에이전트 상태

    Returns:
        업데이트된 상태 dict
    """
    hypothesis = state.get("hypothesis")
    run_id = state.get("run_id", "")
    target_gaps = state.get("_dp2_target_gaps", [])
    previous_gaps = state.get("previous_gaps_searched", [])
    evidence_snippets_v3 = state.get("evidence_snippets_v3", [])

    logger.info(
        f"search_for_controls run_id={run_id} gaps={target_gaps}"
    )

    if not target_gaps:
        logger.warning("search_for_controls: no target gaps")
        return {
            "status_detail": "search_controls_skipped",
        }

    try:
        hypothesis_text = hypothesis.original_text if hypothesis else ""

        # DP2 Router로 쿼리 계획 생성
        dp2_router = DP2CritiqueRouter()
        query_plan = dp2_router.generate_search_query_plan(
            target_gaps=target_gaps,
            hypothesis=hypothesis_text,
        )

        # EPMC 예산 확인 후 검색
        can_use_epmc = await budget_manager.can_use_tier(run_id, SearchTier.EPMC)
        new_snippets = []

        if can_use_epmc:
            epmc_result = await multi_tier_search.search_tier2_epmc(
                query_plan=query_plan,
                hypothesis=hypothesis_text,
                run_id=run_id,
            )
            new_snippets.extend(epmc_result.snippets)
            logger.info(f"search_controls EPMC found {len(epmc_result.snippets)} snippets")
        else:
            # EPMC 예산 없으면 Web 시도
            can_use_web = await budget_manager.can_use_tier(run_id, SearchTier.WEB)
            if can_use_web:
                web_result = await multi_tier_search.search_tier3_web(
                    query=query_plan.primary_query,
                    hypothesis=hypothesis_text,
                    run_id=run_id,
                )
                new_snippets.extend(web_result.snippets)
                logger.info(f"search_controls Web found {len(web_result.snippets)} snippets")
            else:
                logger.warning("search_controls: no search budget remaining")

        # 기존 evidence에 추가
        updated_snippets = evidence_snippets_v3 + [s.to_dict() for s in new_snippets]
        updated_gaps = previous_gaps + target_gaps

        logger.info(
            f"search_controls complete: added {len(new_snippets)} snippets"
        )

        return {
            "evidence_snippets_v3": updated_snippets,
            "previous_gaps_searched": updated_gaps,
            "_dp2_target_gaps": [],  # 처리 완료
            "status_detail": "search_controls_complete",
        }

    except Exception as e:
        logger.error(f"Error in search_for_controls: {e}")
        return {
            "error": str(e),
            "status_detail": "search_controls_error",
        }
