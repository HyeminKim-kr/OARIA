"""Synthesize plan tool."""

import logging
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from app.services.agent.study_plan.v4.tools.base import (
    BaseTool,
    ToolParameter,
    ensure_dict,
    ensure_list,
    safe_get,
)

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────
# v3 템플릿 기반 상세 출력 구조 (13섹션)
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

SYNTHESIZE_SYSTEM_PROMPT = f"""You are a biomedical research planner creating a comprehensive experiment plan.
Balance between optimal design and practical feasibility.

Output in Korean. Follow this exact template structure:

{STUDY_PLAN_TEMPLATE}

**중요**:
- 모든 섹션을 빠짐없이 작성하세요
- 대조군 체크리스트의 모든 항목을 검토하세요
- 대안 가설을 반드시 1-2개 포함하세요
- Decision Rule은 수치적/객관적 기준으로 작성하세요
- 실현가능성 평가를 현실적으로 작성하세요
- 예상 결과 시나리오에 "모호한 경우"도 포함하세요
"""


class SynthesizePlanTool(BaseTool):
    """Synthesize final research plan.

    Combines all components into a coherent plan document.
    """

    def __init__(self, llm: ChatOpenAI | None = None):
        self._llm = llm

    @property
    def name(self) -> str:
        return "synthesize_plan"

    @property
    def description(self) -> str:
        return (
            "Generate Plan A (이상적 설계): 리소스 제약 없는 완전한 연구 계획서. "
            "13섹션 구조 (NSPE 검증 질문, 대조군 체크리스트, 예상 결과 시나리오 포함). "
            "모든 대조군(Vehicle, Positive, Rescue) 포함, Primary+Secondary endpoints. "
            "실험 설계 완료 후 호출. Plan A 생성 후 반드시 generate_plan_b로 Plan B도 생성할 것."
        )

    @property
    def cost(self) -> float:
        return 0.5

    @property
    def category(self) -> str:
        return "synthesis"

    def _get_parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="experiments",
                type="list",
                description="List of experiment designs",
                required=True,
            ),
            ToolParameter(
                name="evidence",
                type="list",
                description="Supporting evidence snippets",
                required=False,
                default=[],
            ),
            ToolParameter(
                name="metadata",
                type="dict",
                description="Additional metadata (hypothesis, constraints, etc.)",
                required=False,
                default={},
            ),
        ]

    async def run(
        self,
        experiments: list | str | None = None,
        evidence: list | str | None = None,
        metadata: dict | str | None = None,
    ) -> dict[str, Any]:
        """Synthesize the plan.

        Args:
            experiments: Experiment designs
            evidence: Supporting evidence
            metadata: Additional metadata

        Returns:
            Dict with plan and summary
        """
        # 타입 안전 변환
        exp_list = ensure_list(experiments, [])
        ev_list = ensure_list(evidence, [])
        meta = ensure_dict(metadata) if metadata else {}

        # Handle missing experiments
        if not exp_list:
            logger.warning("synthesize_plan called without experiments")
            return {
                "plan": "",
                "summary": "",
                "error": "No experiments provided. Design experiments first using design_experiment tool.",
            }

        logger.info(f"Synthesizing plan from {len(exp_list)} experiments...")

        try:
            if self._llm is None:
                from app.config import get_settings

                settings = get_settings()
                self._llm = ChatOpenAI(
                    model=settings.openai_model,
                    temperature=0.2,
                )

            # Format components
            hypothesis = safe_get(meta, "hypothesis", {})
            if isinstance(hypothesis, str):
                hypothesis = {"raw": hypothesis}

            # experiments formatting with type safety
            exp_lines = []
            for e in exp_list:
                e_dict = ensure_dict(e) if not isinstance(e, dict) else e
                name = safe_get(e_dict, "name", "Experiment")
                objective = safe_get(e_dict, "objective", "")
                exp_lines.append(f"- {name}: {objective}")
            exp_text = "\n".join(exp_lines)

            # evidence formatting with type safety
            ev_lines = []
            for e in ev_list[:10]:  # 더 많은 evidence 포함
                e_dict = ensure_dict(e) if not isinstance(e, dict) else e
                claim = safe_get(e_dict, "claim", str(e))[:200]
                source = safe_get(e_dict, "source", "")
                if source:
                    ev_lines.append(f"- {claim} (출처: {source})")
                else:
                    ev_lines.append(f"- {claim}")
            evidence_text = "\n".join(ev_lines) if ev_lines else "근거 논문 정보 없음"

            # 컨텍스트 구성
            context_parts = [
                "## 가설",
                str(hypothesis.get("original_text", hypothesis.get("raw", str(hypothesis)))),
                "",
                "## 실험 설계",
                exp_text,
                "",
                "## 근거 (Evidence)",
                evidence_text,
            ]

            # constraints 추가
            constraints = safe_get(meta, "constraints", [])
            if constraints:
                context_parts.extend([
                    "",
                    "## 제약 조건",
                    "\n".join(f"- {c}" for c in constraints),
                ])

            context_prompt = "\n".join(context_parts)
            context_prompt += "\n\n위 정보를 바탕으로 상세한 연구 계획을 작성하세요."

            # System/Human 메시지 형식으로 LLM 호출
            messages = [
                SystemMessage(content=SYNTHESIZE_SYSTEM_PROMPT),
                HumanMessage(content=context_prompt),
            ]
            response = await self._llm.ainvoke(messages)

            plan = response.content

            # Generate summary
            summary = self._generate_summary(exp_list, hypothesis)

            return {
                "plan": plan,
                "summary": summary,
            }
        except Exception as e:
            logger.error(f"Error synthesizing plan: {e}")
            return {
                "plan": "",
                "summary": f"Error generating plan: {e}",
                "error": str(e),
            }

    def _generate_summary(
        self,
        experiments: list,
        hypothesis: dict | str,
    ) -> str:
        """Generate executive summary."""
        # 타입 안전 처리
        hyp = ensure_dict(hypothesis) if not isinstance(hypothesis, dict) else hypothesis
        iv = safe_get(hyp, "iv", "the independent variable")
        dv = safe_get(hyp, "dv", "the dependent variable")

        lines = [
            "## Executive Summary",
            "",
            f"This study plan tests the hypothesis that {iv} affects {dv}.",
            "",
            f"**Number of Experiments:** {len(experiments)}",
            "",
            "**Experimental Approaches:**",
        ]

        approaches = set()
        for exp in experiments:
            exp_dict = ensure_dict(exp) if not isinstance(exp, dict) else exp
            if approach := safe_get(exp_dict, "approach"):
                if isinstance(approach, str):
                    approaches.add(approach)

        for approach in approaches:
            lines.append(f"- {approach.replace('_', ' ').title()}")

        return "\n".join(lines)
