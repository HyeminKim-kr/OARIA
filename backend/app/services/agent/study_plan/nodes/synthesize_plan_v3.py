"""Node: synthesize_plan_v3 - Plan A/B 합성 + DP3 라우터 통합

v2.1 synthesize_plan을 확장하여:
- DP3 Router 연동
- Plan A/B 동시 생성
- 제약 조건 반영
"""

import json
import logging
from datetime import datetime

from openai import AsyncOpenAI

from app.config import settings

from ..state import ApprovalStatus, StudyPlanState
from ..search.types import DP3RouterInput
from ..routers import DP3SynthesisRouter

logger = logging.getLogger(__name__)


SYNTHESIZE_PLAN_A_SYSTEM = """You are a biomedical research planner creating an **ideal experiment plan**.
Assume all resources are available. Focus on optimal design without constraints.

Output in Korean. Use clear structure with sections:
1. 연구 개요 (Executive Summary)
2. 가설 및 검증 전략
3. 실험 설계 (모든 필요한 대조군 포함)
4. 측정 변수 및 분석 방법
5. 예상 결과 및 해석
6. 참고문헌
"""

SYNTHESIZE_PLAN_B_SYSTEM = """You are a biomedical research planner creating a **practical alternative plan**.
Consider resource constraints, timeline, and feasibility. Focus on essential experiments only.

Output in Korean. Use clear structure with sections:
1. 연구 개요 (Executive Summary) - 제약 조건 명시
2. 핵심 가설 검증 전략
3. 최소 실험 설계 (필수 대조군만)
4. 1차 측정 변수
5. Go/No-Go 기준
6. 참고문헌
"""

SYNTHESIZE_SINGLE_SYSTEM = """You are a biomedical research planner creating a comprehensive experiment plan.
Balance between optimal design and practical feasibility.

Output in Korean. Use clear structure with sections:
1. 연구 개요 (Executive Summary)
2. 가설 및 검증 전략
3. 실험 설계
4. 측정 변수 및 분석 방법
5. 실현가능성 평가
6. 예상 결과 및 해석
7. 참고문헌
"""


async def synthesize_plan_v3(state: StudyPlanState) -> dict:
    """
    Plan A/B 합성 + DP3 라우터 통합 노드.

    1. DP3 Router로 Plan 유형 결정
    2. 결정에 따라 Plan A, Plan B, 또는 단일 Plan 생성
    3. 최종 결과 반환

    Args:
        state: 현재 에이전트 상태

    Returns:
        업데이트된 상태 dict
    """
    run_id = state.get("run_id", "")
    hypothesis = state.get("hypothesis")
    test_questions = state.get("test_questions", [])
    experiment_designs = state.get("experiment_designs", [])
    evidence_packs = state.get("evidence_packs", [])
    measurements = state.get("measurements", [])
    feasibility = state.get("feasibility")
    approval_gate_result = state.get("approval_gate_result")
    quality_score = state.get("quality_score", 0.0)
    web_limit_exceeded = state.get("web_limit_exceeded", False)
    constraints = state.get("constraints", [])

    logger.info(f"synthesize_plan_v3 run_id={run_id}")

    try:
        # 1. DP3 Router 결정
        dp3_router = DP3SynthesisRouter()

        # approval_required 확인
        approval_required = False
        if approval_gate_result:
            approval_required = approval_gate_result.approval_required

        # 고비용/윤리 체크
        high_cost = False
        ethics_required = False
        if feasibility:
            high_cost = feasibility.resource_feasibility < 0.5
            ethics_required = len(feasibility.ethical_considerations) > 0

        # evidence 충분성
        evidence_sufficient = len(evidence_packs) >= 3 or quality_score >= 0.7

        dp3_input = DP3RouterInput(
            quality_score=quality_score,
            approval_required=approval_required,
            web_limit_exceeded=web_limit_exceeded,
            evidence_sufficient=evidence_sufficient,
            high_cost_experiment=high_cost,
            ethics_required=ethics_required,
            explicit_constraints=constraints,
        )

        dp3_decision = dp3_router.route(dp3_input, run_id)
        plan_prompts = dp3_router.get_plan_prompts(
            dp3_decision.decision, dp3_decision.plan_config
        )

        # 2. 컨텍스트 준비
        context = _prepare_synthesis_context(
            hypothesis=hypothesis,
            test_questions=test_questions,
            experiment_designs=experiment_designs,
            evidence_packs=evidence_packs,
            measurements=measurements,
            feasibility=feasibility,
        )

        client = AsyncOpenAI(api_key=settings.openai_api_key)

        # 3. Plan 생성
        plan_a = ""
        plan_b = ""
        final_plan = ""
        executive_summary = ""

        if dp3_decision.decision == "single_plan":
            # 단일 Plan
            final_plan = await _generate_plan(
                client=client,
                system_prompt=SYNTHESIZE_SINGLE_SYSTEM,
                context=context,
                additional_prompt=plan_prompts.get("plan", ""),
            )
            executive_summary = _extract_executive_summary(final_plan)

        elif dp3_decision.decision == "plan_a_b":
            # Plan A + B 동시 생성
            plan_a = await _generate_plan(
                client=client,
                system_prompt=SYNTHESIZE_PLAN_A_SYSTEM,
                context=context,
                additional_prompt=plan_prompts.get("plan_a", ""),
            )
            plan_b = await _generate_plan(
                client=client,
                system_prompt=SYNTHESIZE_PLAN_B_SYSTEM,
                context=context,
                additional_prompt=plan_prompts.get("plan_b", ""),
            )
            # final_plan은 둘 다 포함
            final_plan = f"# Plan A: 이상적 설계\n\n{plan_a}\n\n---\n\n# Plan B: 현실적 대안\n\n{plan_b}"
            executive_summary = _extract_executive_summary(plan_a) + "\n\n[대안] " + _extract_executive_summary(plan_b)

        elif dp3_decision.decision == "plan_b_only":
            # Plan B만
            plan_b = await _generate_plan(
                client=client,
                system_prompt=SYNTHESIZE_PLAN_B_SYSTEM,
                context=context,
                additional_prompt=plan_prompts.get("plan_b", ""),
            )
            final_plan = plan_b
            executive_summary = _extract_executive_summary(plan_b)

        # 4. 참조 목록 생성
        references = _build_references(evidence_packs)

        logger.info(
            f"synthesize_v3 complete: decision={dp3_decision.decision} "
            f"plan_a_len={len(plan_a)} plan_b_len={len(plan_b)}"
        )

        return {
            "final_plan": final_plan,
            "executive_summary": executive_summary,
            "references": references,
            # v3 필드
            "dp3_decision": dp3_decision.decision,
            "plan_a": plan_a,
            "plan_b": plan_b,
            "plan_config": dp3_decision.plan_config,
            # 메타
            "status_detail": f"synthesized_{dp3_decision.decision}",
            "total_duration_ms": _calculate_duration(state),
        }

    except Exception as e:
        logger.error(f"Error in synthesize_plan_v3: {e}")
        return {
            "final_plan": "",
            "executive_summary": "",
            "references": [],
            "dp3_decision": "single_plan",
            "plan_a": "",
            "plan_b": "",
            "error": str(e),
            "status_detail": "synthesis_error",
        }


def _prepare_synthesis_context(
    hypothesis,
    test_questions: list,
    experiment_designs: list,
    evidence_packs: list,
    measurements: list,
    feasibility,
) -> str:
    """합성용 컨텍스트 준비"""
    sections = []

    # 가설
    if hypothesis:
        sections.append(f"## 가설\n{hypothesis.original_text}")

    # 검증 질문
    if test_questions:
        tq_text = "\n".join(
            f"- [{q.category.value}] {q.question}" for q in test_questions
        )
        sections.append(f"## 검증 질문\n{tq_text}")

    # 실험 설계
    if experiment_designs:
        exp_text = "\n".join(
            f"### {exp.title}\n- 유형: {exp.experiment_type.value}\n- 목적: {exp.objective}"
            for exp in experiment_designs
        )
        sections.append(f"## 실험 설계\n{exp_text}")

    # Evidence
    if evidence_packs:
        ev_text = "\n".join(
            f"- {ep.title} ({ep.journal}, {ep.year}): {ep.key_finding[:200]}"
            for ep in evidence_packs[:10]
        )
        sections.append(f"## 근거 논문\n{ev_text}")

    # 측정치
    if measurements:
        m_text = "\n".join(
            f"- {m.name}: {m.method}" for m in measurements[:10]
        )
        sections.append(f"## 측정 항목\n{m_text}")

    # 실현가능성
    if feasibility:
        sections.append(
            f"## 실현가능성\n"
            f"- 기술적: {feasibility.technical_feasibility:.0%}\n"
            f"- 자원: {feasibility.resource_feasibility:.0%}\n"
            f"- 일정: {feasibility.timeline_feasibility:.0%}"
        )

    return "\n\n".join(sections)


async def _generate_plan(
    client: AsyncOpenAI,
    system_prompt: str,
    context: str,
    additional_prompt: str = "",
) -> str:
    """LLM으로 Plan 생성"""
    user_prompt = f"{context}\n\n{additional_prompt}\n\n위 정보를 바탕으로 상세한 연구 계획을 작성하세요."

    response = await client.chat.completions.create(
        model=settings.openai_chat_model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.4,
        max_tokens=4000,
    )

    return response.choices[0].message.content


def _extract_executive_summary(plan: str) -> str:
    """Plan에서 Executive Summary 추출"""
    lines = plan.split("\n")

    in_summary = False
    summary_lines = []

    for line in lines:
        if "연구 개요" in line or "Executive Summary" in line:
            in_summary = True
            continue
        if in_summary:
            if line.startswith("##") or line.startswith("# "):
                break
            if line.strip():
                summary_lines.append(line.strip())

    return " ".join(summary_lines[:5])  # 첫 5줄


def _build_references(evidence_packs: list) -> list[dict]:
    """참조 목록 생성"""
    refs = []
    for ep in evidence_packs:
        refs.append({
            "paper_id": ep.paper_id,
            "title": ep.title,
            "journal": ep.journal,
            "year": ep.year,
        })
    return refs


def _calculate_duration(state: StudyPlanState) -> int:
    """총 소요 시간 계산"""
    created_at = state.get("created_at")
    if not created_at:
        return 0

    try:
        start = datetime.fromisoformat(created_at)
        now = datetime.now()
        return int((now - start).total_seconds() * 1000)
    except:
        return 0
