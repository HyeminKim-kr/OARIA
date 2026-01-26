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


# ─────────────────────────────────────────────────────────────
# 템플릿 기반 시스템 프롬프트 (v3.1)
# ─────────────────────────────────────────────────────────────

STUDY_PLAN_TEMPLATE = """
## 0. 한 줄 요약

> **Question**: {연구 질문 한 문장}
> **Decision**: {이 실험으로 판단할 수 있는 것}

---

## 1. 연구 제목 (Title)

{질환/모델} + {조작/처치} + {주요 엔드포인트}를 포함한 명확한 제목

---

## 2. 서론 및 연구 목적 (Introduction & Objectives)

### 배경 (Background)
- 왜 이 연구가 중요한가?

### 연구 질문 (Research Questions)
1. {주요 연구 질문}
2. {보조 연구 질문 - 필요시}

### 가설 (Hypothesis)
> {검증 가능한 형태의 가설}

### 대안 가설 (Alternative Hypotheses)
1. {대안 가설 1}
2. {대안 가설 2 - 필요시}

---

## 3. 변수 정의 (Variables)

| 구분 | 변수명 | 조작/측정 방법 |
|------|--------|---------------|
| **독립변수** | {변수} | {방법} |
| **종속변수 (Primary)** | {변수} | {방법} |
| **종속변수 (Secondary)** | {변수} | {방법} |
| **통제변수** | {passage, 처리시간, 농도 등} | {표준화 방법} |

### 판정 기준 (Operational Definition)
- {핵심 용어}: {구체적인 정의와 판정 기준}

---

## 4. 검증 질문 분해 (Test Questions - NSPE)

| Category | Question | Decision Rule |
|----------|----------|---------------|
| **Necessity** | {X를 막으면 phenotype이 사라지는가?} | {판정 기준} |
| **Sufficiency** | {X를 올리면 phenotype이 생기는가?} | {판정 기준} |
| **Epistasis** | {X가 Y 위/아래인가?} | {판정 기준} |
| **Specificity** | {off-target/다른 세포타입에서 재현?} | {판정 기준} |

---

## 5. 연구 대상 및 샘플링 (Subjects & Sampling)

### 대상
- {세포주/오가노이드/동물/환자/데이터셋}

### 포함/제외 기준
- **포함**: {조건}
- **제외**: {조건}

### 샘플 크기 및 근거
- N = {숫자} (효과크기 가정: {d}, 검정력: 80%, α = 0.05)
- 근거: {선행연구/파일럿 데이터}

### 무작위화/블라인딩
- {적용 여부 및 방법}

---

## 6. 실험 설계 (Study Design)

### 실험군/대조군 (Arms)

| Group | Treatment | N | Purpose |
|-------|-----------|---|---------|
| Experimental | {처치} | {n} | {목적} |
| Vehicle | {DMSO/PBS 등} | {n} | 처치 자체의 영향 통제 |
| Non-targeting | {siRNA-NC/sgRNA-NC} | {n} | 유전자 조작 특이성 확인 |
| Positive control | {알려진 효과 물질} | {n} | Assay 작동 확인 |
| Rescue | {복원 처치} | {n} | 원인-결과 확인 |

### 대조군 체크리스트 ✅
- [ ] Vehicle/Mock control
- [ ] Non-targeting control (유전자 조작 시)
- [ ] Positive control
- [ ] Rescue control (필요 시)

### 반복 (Replicates)
- **기술적 반복**: {n회/well 또는 tube}
- **생물학적 반복**: {n개 독립적 배양 또는 동물}

---

## 7. 방법 및 절차 (Methods & Procedures)

### 단계별 프로토콜
1. {Step 1}
2. {Step 2}
3. {Step 3}

### 사용 장비/소프트웨어
- {장비/소프트웨어 목록}

### 시간표 (주차 단위)
| Week | Activity |
|------|----------|
| 1-2 | {활동} |
| 3-4 | {활동} |

### QC 포인트
- {오염 체크, 정규화, 캘리브레이션 등}

---

## 8. 측정치 및 데이터 수집 (Measurements & Data Capture)

### Primary Endpoints
| Endpoint | Method | Timepoint | Unit |
|----------|--------|-----------|------|
| {변수} | {방법} | {시점} | {단위} |

### Secondary Endpoints
| Endpoint | Method | Timepoint | Unit |
|----------|--------|-----------|------|
| {변수} | {방법} | {시점} | {단위} |

### Biomarkers/기전 Readouts
- {기전 확인용 측정치}

---

## 9. 분석 계획 (Data Analysis Plan)

### 통계 방법
- **Primary**: {t-test/ANOVA/regression 등}
- **다중비교 보정**: {Bonferroni/FDR 등}

### 배치효과 처리
- {normalization, batch correction 방법}

### 시각화
- {dose-response curve, volcano plot, survival curve 등}

---

## 10. 예상 결과 & 해석 프레임 (Expected Results & Interpretation)

### 결과 시나리오

| 결과 | 해석 | 다음 단계 |
|------|------|----------|
| **A**: {예상 결과} | 가설 지지 | {후속 실험} |
| **B**: {예상 결과} | 가설 반박 | {대안 탐색} |
| **C**: {모호한 결과} | 대안 가설 지지 | {추가 실험 제안} |

---

## 11. Feasibility / 리스크 / 대안 (Feasibility, Risks, Alternatives)

### 비용/시간/리소스
| 항목 | 예상치 |
|------|--------|
| 비용 | {금액 범위} |
| 기간 | {주/개월} |
| 인력 | {필요 인원} |

### 실패 모드 및 대응
| Risk | Mitigation |
|------|------------|
| {off-target effect} | {방안} |
| {모델 부적합} | {방안} |
| {독성} | {방안} |

### Plan B (대안)
- {저비용/대체 모델/대체 readout 옵션}

---

## 12. 윤리 및 제한점 (Ethics & Limitations)

### 승인 필요 여부
- [ ] IRB (인간 대상 연구)
- [ ] IACUC (동물 실험)
- [ ] IBC (생물안전)

### 제한점 및 완화 전략
| 제한점 | 완화 전략 |
|--------|----------|
| {제한점 1} | {전략} |
| {제한점 2} | {전략} |

---

## 13. 근거 (Evidence)

### 핵심 설계 포인트별 근거

| 설계 포인트 | 근거 논문 | Key Finding |
|-------------|----------|-------------|
| {포인트} | {논문 제목 (저널, 연도)} | {핵심 발견} |

---

*이 연구 계획서는 AI Study Plan Agent에 의해 자동 생성되었습니다.*
"""

SYNTHESIZE_PLAN_A_SYSTEM = f"""You are a biomedical research planner creating an **ideal experiment plan**.
Assume all resources are available. Focus on optimal design without constraints.

Output in Korean. Follow this exact template structure:

{STUDY_PLAN_TEMPLATE}

**중요**:
- 모든 섹션을 빠짐없이 작성하세요
- 대조군 체크리스트의 모든 항목을 검토하세요
- 대안 가설을 반드시 1-2개 포함하세요
- Decision Rule은 수치적/객관적 기준으로 작성하세요
- 예상 결과 시나리오에 "모호한 경우"도 포함하세요
"""

SYNTHESIZE_PLAN_B_SYSTEM = f"""You are a biomedical research planner creating a **practical alternative plan**.
Consider resource constraints, timeline, and feasibility. Focus on essential experiments only.

Output in Korean. Follow this exact template structure (simplified where marked):

{STUDY_PLAN_TEMPLATE}

**Plan B 특화 지침**:
- 섹션 6에서 필수 대조군만 포함 (Vehicle + Non-targeting)
- 섹션 8에서 Primary endpoint만 집중
- 섹션 11에서 "저비용 대안"을 구체적으로 명시
- Go/No-Go 기준을 명확히 설정
"""

SYNTHESIZE_SINGLE_SYSTEM = f"""You are a biomedical research planner creating a comprehensive experiment plan.
Balance between optimal design and practical feasibility.

Output in Korean. Follow this exact template structure:

{STUDY_PLAN_TEMPLATE}

**중요**:
- 모든 섹션을 빠짐없이 작성하세요
- 대조군 체크리스트의 모든 항목을 검토하세요
- 대안 가설을 반드시 1-2개 포함하세요
- Decision Rule은 수치적/객관적 기준으로 작성하세요
- 실현가능성 평가를 현실적으로 작성하세요
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
