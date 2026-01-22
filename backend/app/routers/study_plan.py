"""Study Plan Agent 라우터

가설 기반 실험 설계 에이전트 엔드포인트.
"""

import json
import logging
import math
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from app.database import get_db
from app.dependencies import CurrentUser
from app.models import StudyPlan
from app.schemas.study_plan import (
    PaginatedStudyPlans,
    StudyPlanFullResponse,
    StudyPlanListItem,
    StudyPlanRequest,
    StudyPlanSaveRequest,
    StudyPlanSummaryResponse,
)
from app.services.agent.study_plan import (
    StudyPlanEventType,
    study_plan_service,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/study-plan", tags=["study-plan"])


# ─────────────────────────────────────────────────────────────
# Generate Study Plan (SSE Streaming)
# ─────────────────────────────────────────────────────────────


@router.post("/generate")
async def generate_study_plan(
    request: StudyPlanRequest,
    current_user: CurrentUser,
):
    """Study Plan 생성 (SSE 스트리밍)

    가설을 입력받아 실험 설계 계획서를 생성합니다.

    **SSE 이벤트 타입:**
    - `status`: 진행 상태
    - `hypothesis`: 가설 파싱 완료
    - `clarification`: 명확화 질문 필요
    - `tests`: 검증 질문 분해 완료
    - `studies`: 관련 연구 검색 완료
    - `search_expanding`: 검색 쿼리 확장 중
    - `evidence`: Evidence Pack 구축 완료
    - `methodologies`: 방법론 분석 완료
    - `experiments`: 실험 설계 완료
    - `critique`: Critic 검증 결과
    - `revision`: 설계 수정 중
    - `measurements`: 측정 항목 식별 완료
    - `feasibility`: 실현가능성 평가 완료
    - `approval_required`: 승인 필요 (선택지 포함)
    - `result`: 최종 결과
    - `done`: 완료
    - `error`: 오류 발생

    **예시 요청:**
    ```json
    {
        "hypothesis": "EGFR T790M 돌연변이 환자에서 osimertinib 내성 기전으로 MET amplification이 관여한다",
        "research_context": "NSCLC targeted therapy",
        "preferred_experiment_types": ["in_vitro", "in_vivo"]
    }
    ```

    Returns:
        SSE 스트림
    """
    logger.info(
        f"Study Plan request from user {current_user.id}: "
        f"{request.hypothesis[:50]}..."
    )

    async def generate_sse():
        """SSE 스트림 생성"""
        try:
            async for event in study_plan_service.execute_stream(
                user_input=request.hypothesis,
                research_context=request.research_context,
                constraints=request.constraints,
                preferred_experiment_types=request.preferred_experiment_types,
                user_id=str(current_user.id),
            ):
                # StudyPlanEvent를 SSE 이벤트로 변환
                yield {
                    "event": event.event_type.value,
                    "data": json.dumps(event.data, ensure_ascii=False),
                }

        except Exception as e:
            logger.error(f"Error in Study Plan generation: {e}")
            yield {
                "event": "error",
                "data": json.dumps(
                    {"error": str(e), "message": "계획 생성 중 오류가 발생했습니다"},
                    ensure_ascii=False,
                ),
            }

    return EventSourceResponse(generate_sse())


# ─────────────────────────────────────────────────────────────
# Generate Study Plan (Sync - for testing)
# ─────────────────────────────────────────────────────────────


@router.post("/generate-sync", response_model=StudyPlanSummaryResponse)
async def generate_study_plan_sync(
    request: StudyPlanRequest,
    current_user: CurrentUser,
):
    """Study Plan 생성 (동기 - 테스트용)

    SSE 대신 전체 결과를 한 번에 반환합니다.
    개발/테스트 용도로 사용하세요.
    """
    logger.info(
        f"Study Plan sync request from user {current_user.id}: "
        f"{request.hypothesis[:50]}..."
    )

    try:
        result = await study_plan_service.execute(
            user_input=request.hypothesis,
            research_context=request.research_context,
            constraints=request.constraints,
            preferred_experiment_types=request.preferred_experiment_types,
            user_id=str(current_user.id),
        )

        return StudyPlanSummaryResponse(
            success=result.success,
            plan_id=None,  # TODO: DB 저장 시 ID 반환
            final_plan=result.final_plan,
            executive_summary=result.executive_summary,
            experiment_count=result.experiment_count,
            approval_required=result.approval_required,
            approval_status=result.approval_status,
            total_duration_ms=result.total_duration_ms,
            error=result.error,
        )

    except Exception as e:
        logger.error(f"Error in Study Plan sync generation: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


# ─────────────────────────────────────────────────────────────
# Generate Study Plan v3 (Sync)
# ─────────────────────────────────────────────────────────────


@router.post("/generate-v3", response_model=StudyPlanSummaryResponse)
async def generate_study_plan_v3(
    request: StudyPlanRequest,
    current_user: CurrentUser,
):
    """Study Plan v3 생성 (3-tier 검색 + Decision Points)

    v3 기능:
    - **3-tier 검색**: RAG → Europe PMC → Tavily Web
    - **Decision Points**: DP1(검색 승격), DP2(Critique 전략), DP3(Plan A/B)
    - **Plan A/B**: 이상적 설계와 현실적 대안 동시 제공

    **예시 요청:**
    ```json
    {
        "hypothesis": "EGFR T790M mutation causes osimertinib resistance via MET amplification",
        "research_context": "NSCLC targeted therapy",
        "constraints": ["budget limited"],
        "preferred_experiment_types": ["in_vitro", "in_vivo"]
    }
    ```

    Returns:
        StudyPlanSummaryResponse: 생성된 연구 계획 (Plan A/B 포함 가능)
    """
    logger.info(
        f"Study Plan v3 request from user {current_user.id}: "
        f"{request.hypothesis[:50]}..."
    )

    try:
        result = await study_plan_service.execute_v3(
            user_input=request.hypothesis,
            research_context=request.research_context,
            constraints=request.constraints,
            preferred_experiment_types=request.preferred_experiment_types,
            user_id=str(current_user.id),
        )

        return StudyPlanSummaryResponse(
            success=result.success,
            plan_id=None,
            final_plan=result.final_plan,
            executive_summary=result.executive_summary,
            experiment_count=result.experiment_count,
            approval_required=result.approval_required,
            approval_status=result.approval_status,
            total_duration_ms=result.total_duration_ms,
            error=result.error,
        )

    except Exception as e:
        logger.error(f"Error in Study Plan v3 generation: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


# ─────────────────────────────────────────────────────────────
# Save Study Plan
# ─────────────────────────────────────────────────────────────


@router.post("/save", response_model=StudyPlanFullResponse)
async def save_study_plan(
    request: StudyPlanSaveRequest,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """Study Plan 저장

    생성된 Study Plan을 데이터베이스에 저장합니다.
    프론트엔드에서 생성 완료 후 호출하세요.
    """
    logger.info(f"Saving Study Plan for user {current_user.id}")

    try:
        study_plan = StudyPlan(
            user_id=current_user.id,
            hypothesis_input=request.hypothesis_input,
            research_context=request.research_context,
            preferred_experiment_types=request.preferred_experiment_types or [],
            hypothesis_structured=request.hypothesis_structured,
            hypothesis_confidence=request.hypothesis_confidence,
            test_questions=request.test_questions or [],
            search_coverage_score=request.search_coverage_score,
            prior_studies_count=request.prior_studies_count,
            evidence_packs=request.evidence_packs or [],
            experiment_designs=request.experiment_designs or [],
            experiment_count=request.experiment_count,
            quality_score=request.quality_score,
            revision_count=request.revision_count,
            measurements=request.measurements or [],
            feasibility_assessment=request.feasibility_assessment,
            approval_required=request.approval_required,
            approval_status=request.approval_status,
            final_plan=request.final_plan,
            executive_summary=request.executive_summary,
            references=request.references or [],
            # v3 전용 필드
            plan_a=request.plan_a,
            plan_b=request.plan_b,
            plan_config=request.plan_config,
            dp1_decisions=request.dp1_decisions or [],
            dp2_decision=request.dp2_decision,
            dp3_decision=request.dp3_decision,
            highest_tier_used=request.highest_tier_used,
            evidence_snippets_v3=request.evidence_snippets_v3 or [],
            search_tier_history=request.search_tier_history or [],
            # 메타
            status=request.status,
            total_duration_ms=request.total_duration_ms,
            error_message=request.error_message,
        )

        db.add(study_plan)
        await db.commit()
        await db.refresh(study_plan)

        logger.info(f"Study Plan saved with ID: {study_plan.id}")
        return study_plan

    except Exception as e:
        await db.rollback()
        logger.error(f"Error saving Study Plan: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Study Plan 저장 실패: {str(e)}",
        )


# ─────────────────────────────────────────────────────────────
# List Study Plans (History)
# ─────────────────────────────────────────────────────────────


@router.get("/history", response_model=PaginatedStudyPlans)
async def list_study_plans(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    page: int = 1,
    size: int = 10,
):
    """Study Plan 히스토리 목록 조회

    현재 사용자의 Study Plan 목록을 페이지네이션하여 반환합니다.

    Args:
        page: 페이지 번호 (1부터 시작)
        size: 페이지당 항목 수 (기본 10, 최대 50)
    """
    # 페이지네이션 제한
    if size > 50:
        size = 50
    if page < 1:
        page = 1

    offset = (page - 1) * size

    # 총 개수 조회
    count_query = select(func.count(StudyPlan.id)).where(
        StudyPlan.user_id == current_user.id
    )
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # 목록 조회 (최신순)
    list_query = (
        select(StudyPlan)
        .where(StudyPlan.user_id == current_user.id)
        .order_by(StudyPlan.created_at.desc())
        .offset(offset)
        .limit(size)
    )
    result = await db.execute(list_query)
    study_plans = result.scalars().all()

    # 응답 생성
    items = [
        StudyPlanListItem(
            id=sp.id,
            hypothesis_input=sp.hypothesis_input,
            experiment_count=sp.experiment_count,
            quality_score=sp.quality_score,
            status=sp.status,
            created_at=sp.created_at,
        )
        for sp in study_plans
    ]

    pages = math.ceil(total / size) if total > 0 else 1

    return PaginatedStudyPlans(
        items=items,
        total=total,
        page=page,
        size=size,
        pages=pages,
    )


# ─────────────────────────────────────────────────────────────
# Get Study Plan Detail
# ─────────────────────────────────────────────────────────────


@router.get("/{plan_id}", response_model=StudyPlanFullResponse)
async def get_study_plan(
    plan_id: uuid.UUID,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """Study Plan 상세 조회

    특정 Study Plan의 전체 내용을 조회합니다.
    """
    query = select(StudyPlan).where(
        StudyPlan.id == plan_id,
        StudyPlan.user_id == current_user.id,
    )
    result = await db.execute(query)
    study_plan = result.scalar_one_or_none()

    if not study_plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Study Plan을 찾을 수 없습니다.",
        )

    return study_plan


# ─────────────────────────────────────────────────────────────
# Delete Study Plan
# ─────────────────────────────────────────────────────────────


@router.delete("/{plan_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_study_plan(
    plan_id: uuid.UUID,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """Study Plan 삭제

    특정 Study Plan을 삭제합니다.
    """
    query = select(StudyPlan).where(
        StudyPlan.id == plan_id,
        StudyPlan.user_id == current_user.id,
    )
    result = await db.execute(query)
    study_plan = result.scalar_one_or_none()

    if not study_plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Study Plan을 찾을 수 없습니다.",
        )

    await db.delete(study_plan)
    await db.commit()

    logger.info(f"Study Plan {plan_id} deleted by user {current_user.id}")
