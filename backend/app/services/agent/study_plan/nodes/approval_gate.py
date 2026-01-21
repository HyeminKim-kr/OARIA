"""Node 12: approval_gate - 승인 게이트"""

import json
import logging
from datetime import datetime

from openai import AsyncOpenAI

from app.config import settings

from ..prompts import APPROVAL_GATE_SYSTEM, APPROVAL_GATE_USER
from ..state import (
    ApprovalChoice,
    ApprovalGateResult,
    ApprovalItem,
    ApprovalStatus,
    CostBucket,
    EthicsBucket,
    ExperimentType,
    StudyPlanState,
)

logger = logging.getLogger(__name__)


async def approval_gate(state: StudyPlanState) -> dict:
    """
    승인이 필요한 항목을 평가하고 선택지를 제공합니다.

    Args:
        state: 현재 에이전트 상태

    Returns:
        업데이트된 상태 dict:
        - approval_gate_result: ApprovalGateResult
        - approval_status: ApprovalStatus
        - approval_log: list[dict]
    """
    experiment_designs = state.get("experiment_designs", [])
    feasibility = state.get("feasibility")
    measurements = state.get("measurements", [])
    approval_log = state.get("approval_log", [])

    logger.info("Evaluating approval requirements")

    try:
        # 1. 규칙 기반 승인 항목 수집
        approval_items = []

        for exp in experiment_designs:
            # In vivo 실험 → IACUC 필요
            if exp.experiment_type == ExperimentType.IN_VIVO:
                approval_items.append(
                    ApprovalItem(
                        item_type="in_vivo",
                        reason="IACUC 승인 필요 (동물 실험)",
                        cost_bucket=exp.estimated_cost_level,
                        ethics_bucket=EthicsBucket.IACUC,
                    )
                )

            # 임상 실험 → IRB 필요
            if exp.experiment_type == ExperimentType.CLINICAL:
                approval_items.append(
                    ApprovalItem(
                        item_type="clinical",
                        reason="IRB 승인 필요 (임상 데이터)",
                        cost_bucket=exp.estimated_cost_level,
                        ethics_bucket=EthicsBucket.IRB_FULL,
                    )
                )

            # 고비용 실험
            if exp.estimated_cost_level in [CostBucket.HIGH, CostBucket.VERY_HIGH]:
                approval_items.append(
                    ApprovalItem(
                        item_type="high_cost",
                        reason=f"예상 비용 수준: {exp.estimated_cost_level.value}",
                        cost_bucket=exp.estimated_cost_level,
                        ethics_bucket=EthicsBucket.NONE,
                    )
                )

        # 오믹스 분석 (측정 항목에서 확인)
        omics_methods = ["RNA-seq", "proteomics", "metabolomics", "ChIP-seq"]
        for m in measurements:
            if any(om.lower() in m.method.lower() for om in omics_methods):
                approval_items.append(
                    ApprovalItem(
                        item_type="omics",
                        reason=f"{m.method} 분석 비용/전문성 필요",
                        cost_bucket=CostBucket.HIGH,
                        ethics_bucket=EthicsBucket.NONE,
                    )
                )
                break  # 중복 방지

        # 2. 선택지 생성
        choices = []
        if approval_items:
            # 총 비용 추정
            has_in_vivo = any(i.item_type == "in_vivo" for i in approval_items)
            has_omics = any(i.item_type == "omics" for i in approval_items)
            has_high_cost = any(i.item_type == "high_cost" for i in approval_items)

            # 전체 승인
            choices.append(
                ApprovalChoice(
                    choice_id="approve_all",
                    label="전체 승인하고 진행",
                    description="모든 실험 포함",
                    estimated_cost="$50K-100K" if has_in_vivo else "$20K-50K",
                    estimated_timeline="6개월" if has_in_vivo else "3개월",
                )
            )

            # In vitro만
            if has_in_vivo:
                choices.append(
                    ApprovalChoice(
                        choice_id="in_vitro_only",
                        label="In vitro만으로 1차 검증",
                        description="동물실험 제외, 세포주 실험만",
                        estimated_cost="$15K-25K",
                        estimated_timeline="2개월",
                    )
                )

            # 오믹스 제외
            if has_omics:
                choices.append(
                    ApprovalChoice(
                        choice_id="no_omics",
                        label="오믹스 분석 제외",
                        description="RNA-seq 등 제외한 저비용 플랜",
                        estimated_cost="$20K-40K",
                        estimated_timeline="3개월",
                    )
                )

            # 범위 축소
            choices.append(
                ApprovalChoice(
                    choice_id="reduce_scope",
                    label="최소 범위로 축소",
                    description="핵심 실험만 진행",
                    estimated_cost="$10K-20K",
                    estimated_timeline="6주",
                )
            )

        # 3. 승인 상태 결정
        approval_required = len(approval_items) > 0
        status = ApprovalStatus.NEEDS_USER if approval_required else ApprovalStatus.APPROVED

        # 4. 결과 생성
        gate_result = ApprovalGateResult(
            approval_required=approval_required,
            approval_items=approval_items,
            choices=choices,
            approval_status=status,
            user_decision=None,
        )

        # 5. 로그 기록
        new_log = {
            "timestamp": datetime.now().isoformat(),
            "items_count": len(approval_items),
            "status": status.value,
            "items": [
                {
                    "type": i.item_type,
                    "reason": i.reason,
                    "cost": i.cost_bucket.value,
                    "ethics": i.ethics_bucket.value,
                }
                for i in approval_items
            ],
        }
        approval_log = approval_log + [new_log]

        logger.info(
            f"Approval gate: required={approval_required}, "
            f"items={len(approval_items)}, choices={len(choices)}"
        )

        return {
            "approval_gate_result": gate_result,
            "approval_status": status,
            "approval_log": approval_log,
            "status_detail": "approval_required" if approval_required else "approved",
        }

    except Exception as e:
        logger.error(f"Error in approval gate: {e}")
        return {
            "approval_gate_result": ApprovalGateResult(
                approval_required=False,
                approval_status=ApprovalStatus.APPROVED,
            ),
            "approval_status": ApprovalStatus.APPROVED,
            "approval_log": approval_log,
            "error": str(e),
            "status_detail": "approval_error",
        }
