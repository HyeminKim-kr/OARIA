"""Generate Plan B tool."""

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
# Plan B 전용 템플릿 (v3 기반, 간소화된 버전)
# ─────────────────────────────────────────────────────────────

STUDY_PLAN_TEMPLATE_B = """
## 0. 한 줄 요약

> **Question**: {연구 질문 한 문장}
> **Decision**: {이 실험으로 판단할 수 있는 것}
> **Plan B 핵심**: {저비용/간소화 포인트}

---

## 1. 연구 제목 (Title)

{질환/모델} + {조작/처치} + {주요 엔드포인트} - **실용적 접근**

---

## 2. 서론 및 연구 목적 (Introduction & Objectives)

### 배경 (Background)
- 왜 이 연구가 중요한가?

### 연구 질문 (Research Questions)
1. {주요 연구 질문}

### 가설 (Hypothesis)
> {검증 가능한 형태의 가설}

### Go/No-Go 기준 ⭐️
- {명확한 판단 기준 - 이 결과가 나오면 진행/중단}

---

## 3. 변수 정의 (Variables)

| 구분 | 변수명 | 조작/측정 방법 |
|------|--------|---------------|
| **독립변수** | {변수} | {방법} |
| **종속변수 (Primary)** | {변수} | {방법} |
| **통제변수** | {핵심 통제변수만} | {표준화 방법} |

---

## 4. 검증 질문 분해 (Test Questions - 핵심만)

| Category | Question | Decision Rule |
|----------|----------|---------------|
| **Necessity** | {X를 막으면 phenotype이 사라지는가?} | {판정 기준} |
| **Sufficiency** | {X를 올리면 phenotype이 생기는가?} | {판정 기준} |

---

## 5. 연구 대상 및 샘플링 (Subjects & Sampling)

### 대상
- {세포주/오가노이드 - 가장 비용 효율적인 선택}

### 샘플 크기
- N = {최소 필요 숫자} (파일럿 수준)

---

## 6. 실험 설계 (Study Design) - 간소화

### 실험군/대조군 (Arms) - 필수만

| Group | Treatment | N | Purpose |
|-------|-----------|---|---------|
| Experimental | {처치} | {n} | {목적} |
| Vehicle | {DMSO/PBS 등} | {n} | 처치 자체의 영향 통제 |
| Non-targeting | {siRNA-NC/sgRNA-NC} | {n} | 유전자 조작 특이성 확인 |

### 필수 대조군 체크리스트 ✅
- [x] Vehicle/Mock control (필수)
- [x] Non-targeting control (유전자 조작 시)
- [ ] Positive control (선택적)
- [ ] Rescue control (다음 단계로 연기)

### 반복 (Replicates)
- **생물학적 반복**: {n=3 최소}

---

## 7. 방법 및 절차 (Methods & Procedures)

### 단계별 프로토콜 (간소화)
1. {Step 1}
2. {Step 2}

### 시간표 (주차 단위)
| Week | Activity |
|------|----------|
| 1 | {활동} |
| 2 | {활동} |

---

## 8. 측정치 및 데이터 수집 (Primary Endpoint만)

### Primary Endpoints만 집중
| Endpoint | Method | Timepoint | Unit |
|----------|--------|-----------|------|
| {핵심 변수} | {방법} | {시점} | {단위} |

---

## 9. 분석 계획 (Data Analysis Plan)

### 통계 방법
- **Primary**: {간단한 통계 - t-test 등}

---

## 10. 예상 결과 & Go/No-Go 판단

### 결과 시나리오

| 결과 | 해석 | 다음 단계 |
|------|------|----------|
| **Go**: {예상 결과} | 가설 지지 → Plan A로 확장 | {후속 실험} |
| **No-Go**: {예상 결과} | 가설 반박 → 방향 전환 | {대안 탐색} |

---

## 11. 비용/시간 분석 (Plan A 대비)

### Plan A vs Plan B 비교
| 항목 | Plan A | Plan B | 절감률 |
|------|--------|--------|--------|
| 비용 | {금액} | {금액} | {%} |
| 기간 | {주/개월} | {주/개월} | {%} |
| 인력 | {인원} | {인원} | {%} |

### 트레이드오프
- {Plan B에서 포기한 것들}
- {Plan B의 한계점}

---

## 12. Plan A로의 전환 조건

### Go 신호 시 확장 계획
- {Plan B 성공 시 추가할 실험들}
- {Plan A로 확장하는 구체적 단계}

---

*이 연구 계획서(Plan B)는 AI Study Plan Agent에 의해 자동 생성되었습니다.*
"""

PLAN_B_SYSTEM_PROMPT = f"""You are a biomedical research planner creating a **practical alternative plan (Plan B)**.
Consider resource constraints, timeline, and feasibility. Focus on essential experiments only.

Output in Korean. Follow this exact template structure:

{STUDY_PLAN_TEMPLATE_B}

**Plan B 특화 지침**:
- 섹션 6에서 필수 대조군만 포함 (Vehicle + Non-targeting)
- 섹션 8에서 Primary endpoint만 집중
- 섹션 11에서 Plan A 대비 비용/시간 절감을 구체적으로 명시
- Go/No-Go 기준을 명확히 설정 (수치적 기준)
- Rescue control, Positive control 등은 "Plan A로 확장 시" 항목으로

**측정치 단위 (필수)** - v3 개선사항:
- Primary Endpoint의 Unit 컬럼에 구체적 단위 명시
  - 예: μM, ng/mL, %, fold change
- IC50 → μM 또는 nM
- 세포 생존율 → % 생존율

**비용 비교표 구체화** - v3 개선사항:
- Plan A vs Plan B 비교표에 실제 예상 금액 명시
  - 비용: 원 단위 (예: 500만원 vs 200만원) 또는 USD
  - 기간: 주/개월 단위 구체화
  - 인력: 명 단위로 명시
- 절감률을 % 단위로 정확히 계산

**Go/No-Go 기준 구체화**:
- 수치적 판정 기준 명시
  - 예: "IC50 > 10μM이면 내성 확인, Plan A로 확장"
  - 예: "생존율 50% 미만이면 효과 확인"
"""


class GeneratePlanBTool(BaseTool):
    """Generate alternative Plan B.

    Creates a resource-conscious alternative to Plan A.
    """

    def __init__(self, llm: ChatOpenAI | None = None):
        self._llm = llm

    @property
    def name(self) -> str:
        return "generate_plan_b"

    @property
    def description(self) -> str:
        return (
            "Generate Plan B (현실적 대안): 저비용, 빠른 검증용 간소화 계획. "
            "필수 대조군만(Vehicle, Non-targeting), Primary endpoint만 집중. "
            "최소 샘플(n=3), Go/No-Go 기준 명시, Plan A 확장 조건 포함. "
            "Plan A 생성 후 반드시 호출하여 단계적 접근법 제공. "
            "Plan B 성공 시 Plan A로 확장 가능."
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
                name="plan_a",
                type="dict",
                description="Original plan (Plan A) to create alternative for",
                required=True,
            ),
            ToolParameter(
                name="constraints",
                type="list",
                description="Constraints to address in Plan B",
                required=False,
                default=[],
            ),
        ]

    async def run(
        self,
        plan_a: dict | str,
        constraints: list | str | None = None,
    ) -> dict[str, Any]:
        """Generate Plan B.

        Args:
            plan_a: Original plan
            constraints: Resource constraints

        Returns:
            Dict with plan_b and tradeoffs
        """
        # 타입 안전 변환
        pa = ensure_dict(plan_a)
        cons = ensure_list(constraints, ["Limited budget", "Time constraints"])

        logger.info("Generating Plan B...")

        try:
            if self._llm is None:
                from app.config import get_settings

                settings = get_settings()
                self._llm = ChatOpenAI(
                    model=settings.openai_model,
                    temperature=0.2,
                )

            plan_a_text = safe_get(pa, "plan", str(pa))
            constraints_text = "\n".join([
                f"- {c}" if isinstance(c, str) else f"- {str(c)}"
                for c in cons
            ])

            # 컨텍스트 구성
            context_parts = [
                "## Plan A (원본 계획)",
                plan_a_text[:3000] if len(plan_a_text) > 3000 else plan_a_text,
                "",
                "## 제약 조건",
                constraints_text,
                "",
                "위 Plan A를 기반으로 제약 조건을 고려한 Plan B를 작성하세요.",
                "Plan B는 핵심 실험에 집중하고, 비용과 시간을 절감하는 방향으로 설계하세요.",
            ]
            context_prompt = "\n".join(context_parts)

            # System/Human 메시지 형식으로 LLM 호출
            messages = [
                SystemMessage(content=PLAN_B_SYSTEM_PROMPT),
                HumanMessage(content=context_prompt),
            ]
            response = await self._llm.ainvoke(messages)

            return {
                "plan_b": response.content,
                "tradeoffs": [
                    "실험 범위 축소 (핵심 실험만)",
                    "대조군 간소화 (Vehicle + Non-targeting만)",
                    "Secondary endpoint 제외",
                    "샘플 크기 최소화",
                ],
            }
        except Exception as e:
            logger.error(f"Error generating Plan B: {e}")
            return {
                "plan_b": "",
                "tradeoffs": [],
                "error": str(e),
            }
