# Study Plan Agent v4 - 진정한 에이전트로의 리팩토링

> **Version**: v4.0
> **Status**: Draft
> **Created**: 2026-01-22
> **Author**: Claude + Human

---

## 1. 현재 상태 분석 (v3)

### 1.1 v3 아키텍처

```
┌─────────────────────────────────────────────────────────────────┐
│                    Study Plan Agent v3                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Input → Parse → Decompose → Search → Evidence → Design        │
│                                  │                    │         │
│                               DP1(승격)            DP2(전략)    │
│                                  │                    │         │
│                              [EPMC/Web]          [Redesign]     │
│                                  │                    │         │
│                                  └──────→ Critique ←──┘         │
│                                              │                  │
│                                           DP3(분기)             │
│                                              │                  │
│                                    ┌────────┴────────┐          │
│                                 Plan A            Plan B        │
│                                    └────────┬────────┘          │
│                                           Output                │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 1.2 v3의 한계

| 문제 | 설명 |
|------|------|
| **고정된 노드 순서** | Parse → Decompose → Search... 순서가 하드코딩됨 |
| **Rule-based DP** | Decision Point가 조건문 기반, LLM 추론 아님 |
| **단방향 흐름** | Critique 실패 시 Design으로만 돌아감, 가설 재검토 불가 |
| **도구 선택 불가** | 어떤 도구를 쓸지 에이전트가 결정하지 않음 |
| **환경 인식 부재** | 외부 상태 변화, 사용자 피드백 미반영 |
| **학습 없음** | 이전 실행 결과를 기억/활용하지 않음 |

### 1.3 "에이전트"의 정의

```
Agent = Perception + Reasoning + Action + Learning
        (인식)      (추론)      (행동)   (학습)

핵심 특성:
1. 목표 지향적 (Goal-oriented)
2. 자율적 의사결정 (Autonomous decision-making)
3. 환경과 상호작용 (Environment interaction)
4. 실패 복구 (Failure recovery)
5. 적응적 행동 (Adaptive behavior)
```

---

## 2. v4 목표

### 2.1 핵심 목표

> **"Workflow에서 Agent로의 전환"**

| 항목 | v3 (Workflow) | v4 (Agent) |
|------|---------------|------------|
| 흐름 제어 | 하드코딩된 그래프 | LLM이 동적 결정 |
| 도구 사용 | 순서대로 실행 | 필요할 때 선택 |
| 실패 처리 | 고정된 fallback | 원인 분석 후 대안 탐색 |
| 종료 조건 | 마지막 노드 도달 | 목표 달성 판단 |
| 상태 인식 | 내부 state만 | 환경 + 히스토리 |

### 2.2 성공 지표

```
1. 자율성 지표
   - 동일 입력에 대해 상황에 따라 다른 경로 선택 가능
   - 실패 시 스스로 대안 탐색 (최소 2회)

2. 품질 지표
   - 대조군 설계 완성도 ≥ 90%
   - 측정 변수-가설 변수 매칭률 ≥ 95%
   - 사용자 만족도 (Plan 채택률) 측정

3. 효율성 지표
   - 불필요한 도구 호출 감소
   - 평균 실행 시간 유지 (v3 대비 ±20%)
```

---

## 3. v4 아키텍처 설계

### 3.1 전체 구조

```
┌─────────────────────────────────────────────────────────────────┐
│                    Study Plan Agent v4                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                    Agent Core (ReAct Loop)               │   │
│  │                                                          │   │
│  │   ┌──────────┐    ┌──────────┐    ┌──────────┐          │   │
│  │   │ Perceive │ → │  Reason  │ → │   Act    │           │   │
│  │   │  (인식)   │    │  (추론)  │    │  (행동)  │           │   │
│  │   └──────────┘    └──────────┘    └────┬─────┘          │   │
│  │        ↑                               │                 │   │
│  │        │         ┌──────────┐          │                 │   │
│  │        └──────── │ Observe  │ ←────────┘                 │   │
│  │                  │  (관찰)   │                            │   │
│  │                  └──────────┘                            │   │
│  └─────────────────────────────────────────────────────────┘   │
│                              │                                  │
│                              ▼                                  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                      Tool Registry                       │   │
│  │                                                          │   │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐        │   │
│  │  │ Search  │ │ Analyze │ │ Design  │ │Validate │        │   │
│  │  │  Tools  │ │  Tools  │ │  Tools  │ │  Tools  │        │   │
│  │  └─────────┘ └─────────┘ └─────────┘ └─────────┘        │   │
│  │                                                          │   │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐        │   │
│  │  │  User   │ │ Memory  │ │ Critique│ │Synthestic│       │   │
│  │  │Interact │ │  Tools  │ │  Tools  │ │  Tools  │        │   │
│  │  └─────────┘ └─────────┘ └─────────┘ └─────────┘        │   │
│  └─────────────────────────────────────────────────────────┘   │
│                              │                                  │
│                              ▼                                  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                    State & Memory                        │   │
│  │                                                          │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐   │   │
│  │  │ Working      │  │ Execution    │  │ Long-term    │   │   │
│  │  │ Memory       │  │ History      │  │ Memory       │   │   │
│  │  │ (현재 상태)   │  │ (실행 이력)  │  │ (과거 학습)  │   │   │
│  │  └──────────────┘  └──────────────┘  └──────────────┘   │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 3.2 ReAct Loop 상세

```python
class AgentLoop:
    """
    ReAct (Reasoning + Acting) 패턴 기반 에이전트 루프

    Thought → Action → Observation → Thought → ...
    """

    async def run(self, goal: str, context: dict) -> AgentResult:
        state = self.initialize_state(goal, context)

        while not self.is_goal_achieved(state):
            # 1. Perceive: 현재 상태 인식
            perception = await self.perceive(state)

            # 2. Reason: 다음 행동 결정 (LLM)
            thought, action = await self.reason(perception, state)

            # 3. Act: 도구 실행
            observation = await self.act(action)

            # 4. Update: 상태 업데이트
            state = self.update_state(state, thought, action, observation)

            # 5. Check: 종료 조건 또는 실패 처리
            if self.is_failure(observation):
                state = await self.handle_failure(state, observation)

            # 6. Guard: 무한 루프 방지
            if state.iteration_count > self.max_iterations:
                break

        return self.finalize(state)
```

### 3.3 도구 체계

#### 3.3.1 도구 분류

```python
TOOL_REGISTRY = {
    # === Search Tools ===
    "search_rag": {
        "description": "내부 RAG 시스템에서 관련 논문 검색",
        "input": {"query": str, "top_k": int},
        "output": {"papers": list, "coverage": float},
        "cost": "low",
    },
    "search_epmc": {
        "description": "Europe PMC에서 외부 논문 검색",
        "input": {"query": str, "filters": dict},
        "output": {"papers": list, "total": int},
        "cost": "medium",
    },
    "search_web": {
        "description": "Tavily 웹 검색으로 최신 정보 수집",
        "input": {"query": str},
        "output": {"results": list},
        "cost": "high",
    },

    # === Analysis Tools ===
    "parse_hypothesis": {
        "description": "가설을 구조화하여 핵심 변수 추출",
        "input": {"hypothesis": str},
        "output": {"iv": str, "dv": str, "mediators": list, "confidence": float},
        "cost": "low",
    },
    "decompose_questions": {
        "description": "가설 검증을 위한 NSPE 질문 생성",
        "input": {"structured_hypothesis": dict},
        "output": {"questions": list},
        "cost": "low",
    },
    "analyze_methodology": {
        "description": "기존 연구에서 방법론 패턴 추출",
        "input": {"papers": list},
        "output": {"patterns": list, "common_assays": list},
        "cost": "medium",
    },

    # === Design Tools ===
    "design_experiment": {
        "description": "개별 실험 설계 생성",
        "input": {"question": dict, "evidence": list, "constraints": list},
        "output": {"experiment": dict},
        "cost": "medium",
    },
    "design_controls": {
        "description": "실험에 필요한 대조군 설계",
        "input": {"experiment": dict},
        "output": {"controls": list},
        "cost": "low",
    },
    "suggest_measurements": {
        "description": "측정 변수 및 assay 제안",
        "input": {"experiment": dict, "hypothesis_vars": list},
        "output": {"measurements": list, "coverage": float},
        "cost": "low",
    },

    # === Validation Tools ===
    "validate_controls": {
        "description": "대조군 설계의 논리적 완성도 검증",
        "input": {"experiment": dict, "controls": list},
        "output": {"valid": bool, "issues": list, "suggestions": list},
        "cost": "low",
    },
    "validate_coverage": {
        "description": "가설 변수가 측정 항목에 포함되는지 검증",
        "input": {"hypothesis": dict, "measurements": list},
        "output": {"coverage": float, "missing": list},
        "cost": "low",
    },
    "critique_design": {
        "description": "전체 설계의 품질 평가",
        "input": {"design": dict},
        "output": {"score": float, "issues": list, "suggestions": list},
        "cost": "medium",
    },

    # === Synthesis Tools ===
    "synthesize_plan": {
        "description": "최종 연구 계획서 생성",
        "input": {"experiments": list, "evidence": list, "metadata": dict},
        "output": {"plan": str, "summary": str},
        "cost": "medium",
    },
    "generate_plan_b": {
        "description": "자원 제약을 고려한 대안 계획 생성",
        "input": {"plan_a": dict, "constraints": list},
        "output": {"plan_b": str, "tradeoffs": list},
        "cost": "medium",
    },

    # === User Interaction Tools ===
    "ask_user": {
        "description": "사용자에게 명확화 질문",
        "input": {"question": str, "options": list},
        "output": {"answer": str},
        "cost": "high",  # 사용자 대기 필요
    },

    # === Memory Tools ===
    "recall_similar": {
        "description": "유사한 과거 실행 결과 조회",
        "input": {"hypothesis": str, "top_k": int},
        "output": {"past_runs": list},
        "cost": "low",
    },
    "store_result": {
        "description": "현재 실행 결과를 장기 메모리에 저장",
        "input": {"run_id": str, "result": dict},
        "output": {"stored": bool},
        "cost": "low",
    },
}
```

#### 3.3.2 도구 선택 프롬프트

```python
TOOL_SELECTION_PROMPT = """
You are an AI agent designing a research study plan.

## Current State
{state_summary}

## Goal
{goal}

## Available Tools
{tool_descriptions}

## Execution History
{recent_actions}

## Instructions
Based on the current state and goal, decide the next action.

Think step by step:
1. What information do I have?
2. What information do I need?
3. What is blocking progress?
4. Which tool would help most?

Respond in this format:
```json
{
    "thought": "My reasoning about what to do next...",
    "action": "tool_name",
    "action_input": {
        "param1": "value1",
        ...
    },
    "confidence": 0.85,
    "alternative": "backup_tool_name if this fails"
}
```

If the goal is achieved, respond:
```json
{
    "thought": "Goal achieved because...",
    "action": "FINISH",
    "action_input": {
        "final_result": "..."
    }
}
```
"""
```

### 3.4 상태 관리

#### 3.4.1 Working Memory (현재 실행)

```python
@dataclass
class WorkingMemory:
    """현재 실행의 작업 메모리"""

    # 목표 및 입력
    goal: str
    original_hypothesis: str
    structured_hypothesis: dict | None = None
    constraints: list[str] = field(default_factory=list)

    # 검증 질문
    test_questions: list[dict] = field(default_factory=list)
    answered_questions: set[str] = field(default_factory=set)

    # 검색 결과
    retrieved_papers: list[dict] = field(default_factory=list)
    evidence_snippets: list[dict] = field(default_factory=list)
    search_coverage: float = 0.0

    # 설계 결과
    experiments: list[dict] = field(default_factory=list)
    controls: dict[str, list] = field(default_factory=dict)
    measurements: list[dict] = field(default_factory=list)

    # 검증 결과
    validation_results: list[dict] = field(default_factory=list)
    quality_score: float = 0.0

    # 최종 출력
    plan_a: str | None = None
    plan_b: str | None = None

    # 메타
    iteration_count: int = 0
    total_cost: float = 0.0

    def get_summary(self) -> str:
        """현재 상태 요약 (LLM 컨텍스트용)"""
        return f"""
Current Progress:
- Hypothesis parsed: {self.structured_hypothesis is not None}
- Test questions: {len(self.test_questions)} generated, {len(self.answered_questions)} addressed
- Papers retrieved: {len(self.retrieved_papers)}
- Evidence snippets: {len(self.evidence_snippets)}
- Search coverage: {self.search_coverage:.1%}
- Experiments designed: {len(self.experiments)}
- Quality score: {self.quality_score:.1%}
- Iterations: {self.iteration_count}
"""
```

#### 3.4.2 Execution History (실행 이력)

```python
@dataclass
class ExecutionStep:
    """단일 실행 단계 기록"""
    step_number: int
    timestamp: datetime
    thought: str
    action: str
    action_input: dict
    observation: dict
    success: bool
    error: str | None = None
    duration_ms: int = 0


class ExecutionHistory:
    """현재 실행의 전체 이력"""

    def __init__(self):
        self.steps: list[ExecutionStep] = []
        self.failed_actions: dict[str, int] = {}  # action -> failure count

    def add_step(self, step: ExecutionStep):
        self.steps.append(step)
        if not step.success:
            self.failed_actions[step.action] = self.failed_actions.get(step.action, 0) + 1

    def get_recent(self, n: int = 5) -> list[ExecutionStep]:
        return self.steps[-n:]

    def should_avoid(self, action: str) -> bool:
        """같은 액션이 2회 이상 실패했으면 피해야 함"""
        return self.failed_actions.get(action, 0) >= 2

    def get_context_for_llm(self, n: int = 5) -> str:
        """최근 n개 단계를 LLM 컨텍스트 형태로"""
        recent = self.get_recent(n)
        lines = []
        for step in recent:
            status = "✓" if step.success else "✗"
            lines.append(f"[{status}] {step.action}: {step.thought[:100]}...")
        return "\n".join(lines)
```

#### 3.4.3 Long-term Memory (장기 기억)

```python
class LongTermMemory:
    """
    과거 실행 결과를 저장하고 유사 케이스 검색
    Redis 또는 Vector DB 기반
    """

    async def store_run(self, run_id: str, hypothesis: str, result: dict):
        """실행 결과 저장"""
        embedding = await self.embed(hypothesis)
        await self.vector_store.upsert({
            "id": run_id,
            "vector": embedding,
            "metadata": {
                "hypothesis": hypothesis,
                "quality_score": result.get("quality_score"),
                "experiment_count": result.get("experiment_count"),
                "timestamp": datetime.utcnow().isoformat(),
            }
        })

    async def recall_similar(self, hypothesis: str, top_k: int = 3) -> list[dict]:
        """유사한 과거 실행 검색"""
        embedding = await self.embed(hypothesis)
        results = await self.vector_store.search(embedding, top_k=top_k)
        return [
            {
                "run_id": r["id"],
                "hypothesis": r["metadata"]["hypothesis"],
                "quality_score": r["metadata"]["quality_score"],
                "similarity": r["score"],
            }
            for r in results
        ]

    async def get_common_failures(self, hypothesis_type: str) -> list[str]:
        """특정 유형 가설에서 자주 발생하는 실패 패턴"""
        # 예: "resistance mechanism" 가설에서 대조군 누락이 빈번
        ...
```

---

## 4. 핵심 컴포넌트 상세 설계

### 4.1 Reasoner (추론기)

```python
class Reasoner:
    """
    현재 상태를 분석하고 다음 행동을 결정하는 LLM 기반 추론기
    """

    def __init__(self, llm: ChatOpenAI, tools: ToolRegistry):
        self.llm = llm
        self.tools = tools
        self.prompt = ChatPromptTemplate.from_template(TOOL_SELECTION_PROMPT)

    async def reason(
        self,
        state: WorkingMemory,
        history: ExecutionHistory,
        goal: str,
    ) -> tuple[str, Action]:
        """
        Returns:
            thought: 추론 과정 설명
            action: 수행할 액션
        """
        # 컨텍스트 구성
        context = {
            "state_summary": state.get_summary(),
            "goal": goal,
            "tool_descriptions": self.tools.get_descriptions(),
            "recent_actions": history.get_context_for_llm(),
        }

        # LLM 호출
        messages = self.prompt.format_messages(**context)
        response = await self.llm.ainvoke(messages)

        # 파싱
        parsed = self._parse_response(response.content)

        # 실패 기록 있는 액션 회피
        if history.should_avoid(parsed["action"]):
            parsed = await self._get_alternative(parsed, state, history)

        action = Action(
            name=parsed["action"],
            input=parsed["action_input"],
            confidence=parsed.get("confidence", 0.5),
        )

        return parsed["thought"], action

    async def _get_alternative(
        self,
        original: dict,
        state: WorkingMemory,
        history: ExecutionHistory,
    ) -> dict:
        """실패한 액션의 대안 찾기"""
        if original.get("alternative"):
            return {**original, "action": original["alternative"]}

        # LLM에게 대안 요청
        ...
```

### 4.2 Executor (실행기)

```python
class Executor:
    """도구 실행 및 결과 관찰"""

    def __init__(self, tools: ToolRegistry):
        self.tools = tools

    async def execute(self, action: Action) -> Observation:
        """
        액션 실행 및 결과 반환
        """
        if action.name == "FINISH":
            return Observation(
                success=True,
                result=action.input.get("final_result"),
                is_terminal=True,
            )

        tool = self.tools.get(action.name)
        if not tool:
            return Observation(
                success=False,
                error=f"Unknown tool: {action.name}",
            )

        try:
            start_time = time.time()
            result = await tool.run(**action.input)
            duration = int((time.time() - start_time) * 1000)

            return Observation(
                success=True,
                result=result,
                duration_ms=duration,
                cost=tool.cost,
            )
        except Exception as e:
            return Observation(
                success=False,
                error=str(e),
            )
```

### 4.3 Failure Handler (실패 처리기)

```python
class FailureHandler:
    """
    실패 원인 분석 및 복구 전략 결정
    """

    FAILURE_STRATEGIES = {
        "search_no_results": [
            "broaden_query",      # 검색어 확장
            "try_different_tier", # 다른 검색 소스
            "ask_user",           # 사용자에게 키워드 요청
        ],
        "low_coverage": [
            "expand_search",      # 추가 검색
            "relax_constraints",  # 제약 완화
            "decompose_further",  # 질문 세분화
        ],
        "validation_failed": [
            "redesign",           # 재설계
            "add_controls",       # 대조군 추가
            "revise_hypothesis",  # 가설 재검토
        ],
        "quality_low": [
            "iterate_critique",   # 반복 검증
            "seek_more_evidence", # 추가 근거 수집
            "simplify_design",    # 설계 단순화
        ],
    }

    async def handle(
        self,
        failure_type: str,
        state: WorkingMemory,
        history: ExecutionHistory,
    ) -> RecoveryPlan:
        """
        실패 유형에 따른 복구 계획 수립
        """
        strategies = self.FAILURE_STRATEGIES.get(failure_type, ["ask_user"])

        # 이미 시도한 전략 제외
        tried = {s.action for s in history.steps if not s.success}
        available = [s for s in strategies if s not in tried]

        if not available:
            # 모든 전략 실패 → 사용자 개입 요청
            return RecoveryPlan(
                strategy="ask_user",
                message="자동 복구 실패. 사용자 입력이 필요합니다.",
                options=self._generate_user_options(failure_type),
            )

        # LLM에게 최적 전략 선택 요청
        strategy = await self._select_strategy(available, state, failure_type)

        return RecoveryPlan(
            strategy=strategy,
            next_actions=self._plan_recovery_actions(strategy, state),
        )
```

### 4.4 Goal Checker (목표 달성 검사기)

```python
class GoalChecker:
    """
    목표 달성 여부 판단
    """

    # 최소 요구사항
    MINIMUM_REQUIREMENTS = {
        "hypothesis_parsed": True,
        "test_questions_count": 3,
        "experiments_count": 1,
        "quality_score": 0.7,
        "controls_complete": True,
        "measurements_coverage": 0.8,
    }

    def is_goal_achieved(self, state: WorkingMemory) -> tuple[bool, dict]:
        """
        Returns:
            achieved: 목표 달성 여부
            details: 각 요구사항별 충족 상태
        """
        details = {
            "hypothesis_parsed": state.structured_hypothesis is not None,
            "test_questions_count": len(state.test_questions) >= 3,
            "experiments_count": len(state.experiments) >= 1,
            "quality_score": state.quality_score >= 0.7,
            "controls_complete": self._check_controls(state),
            "measurements_coverage": self._check_measurement_coverage(state),
        }

        achieved = all(details.values())
        return achieved, details

    def _check_controls(self, state: WorkingMemory) -> bool:
        """각 실험에 필수 대조군이 있는지 확인"""
        for exp in state.experiments:
            controls = state.controls.get(exp["id"], [])
            has_vehicle = any(c["type"] == "vehicle" for c in controls)
            has_positive = any(c["type"] == "positive" for c in controls)
            if not (has_vehicle and has_positive):
                return False
        return True

    def _check_measurement_coverage(self, state: WorkingMemory) -> bool:
        """가설 변수가 측정 항목에 포함되는지"""
        if not state.structured_hypothesis:
            return False

        required_vars = {
            state.structured_hypothesis.get("iv"),
            state.structured_hypothesis.get("dv"),
        }
        required_vars.update(state.structured_hypothesis.get("mediators", []))
        required_vars.discard(None)

        measured = {m.get("target") for m in state.measurements}

        coverage = len(required_vars & measured) / len(required_vars) if required_vars else 0
        return coverage >= 0.8
```

---

## 5. 구현 계획

### 5.1 Phase 1: 핵심 루프 구조 (1주)

```
목표: ReAct 기반 에이전트 루프 구현

작업 항목:
├── [ ] agent/core/loop.py - AgentLoop 클래스
├── [ ] agent/core/state.py - WorkingMemory, ExecutionHistory
├── [ ] agent/core/reasoner.py - Reasoner 클래스
├── [ ] agent/core/executor.py - Executor 클래스
├── [ ] agent/core/goal_checker.py - GoalChecker 클래스
└── [ ] tests/agent/test_loop.py - 루프 테스트

검증:
- 간단한 가설로 전체 루프 동작 확인
- 3회 이상 iteration 후 종료
```

### 5.2 Phase 2: 도구 시스템 (1주)

```
목표: 도구 레지스트리 및 동적 선택 구현

작업 항목:
├── [ ] agent/tools/registry.py - ToolRegistry
├── [ ] agent/tools/base.py - BaseTool 추상 클래스
├── [ ] agent/tools/search/ - 검색 도구들
│   ├── [ ] rag_tool.py
│   ├── [ ] epmc_tool.py
│   └── [ ] web_tool.py
├── [ ] agent/tools/analysis/ - 분석 도구들
│   ├── [ ] parse_hypothesis_tool.py
│   ├── [ ] decompose_tool.py
│   └── [ ] methodology_tool.py
├── [ ] agent/tools/design/ - 설계 도구들
│   ├── [ ] experiment_tool.py
│   ├── [ ] controls_tool.py
│   └── [ ] measurements_tool.py
├── [ ] agent/tools/validation/ - 검증 도구들
│   ├── [ ] validate_controls_tool.py
│   ├── [ ] validate_coverage_tool.py
│   └── [ ] critique_tool.py
└── [ ] tests/agent/test_tools.py

검증:
- 각 도구 단독 실행 테스트
- LLM이 적절한 도구 선택하는지 확인
```

### 5.3 Phase 3: 실패 처리 및 복구 (1주)

```
목표: 강건한 실패 처리 시스템 구현

작업 항목:
├── [ ] agent/core/failure_handler.py - FailureHandler
├── [ ] agent/core/recovery.py - RecoveryPlan, 복구 전략
├── [ ] agent/prompts/recovery_prompts.py - 복구 관련 프롬프트
└── [ ] tests/agent/test_failure_recovery.py

검증:
- 의도적 실패 시나리오에서 복구 동작 확인
- 최대 3회 복구 시도 후 사용자 개입 요청
```

### 5.4 Phase 4: 메모리 시스템 (1주)

```
목표: 장기 메모리 및 학습 기반 구현

작업 항목:
├── [ ] agent/memory/long_term.py - LongTermMemory
├── [ ] agent/memory/embeddings.py - 임베딩 처리
├── [ ] agent/memory/patterns.py - 패턴 학습
└── [ ] tests/agent/test_memory.py

검증:
- 유사 가설 검색 동작 확인
- 과거 실패 패턴 회피 동작 확인
```

### 5.5 Phase 5: 통합 및 마이그레이션 (1주)

```
목표: v3 → v4 마이그레이션 및 API 통합

작업 항목:
├── [ ] agent/v4/service.py - v4 서비스 통합
├── [ ] agent/v4/graph.py - 호환성 레이어 (v3 그래프 유지)
├── [ ] routers/study_plan.py - /generate-v4 엔드포인트
├── [ ] 마이그레이션 스크립트
└── [ ] E2E 테스트

검증:
- v3와 동일 입력에 대해 품질 비교
- 성능 벤치마크 (응답 시간, 토큰 사용량)
```

---

## 6. 파일 구조

```
backend/app/services/agent/study_plan/
├── v4/                              # v4 전용 디렉토리
│   ├── __init__.py
│   ├── agent.py                     # 메인 에이전트 클래스
│   ├── core/
│   │   ├── __init__.py
│   │   ├── loop.py                  # AgentLoop
│   │   ├── state.py                 # WorkingMemory, ExecutionHistory
│   │   ├── reasoner.py              # Reasoner
│   │   ├── executor.py              # Executor
│   │   ├── goal_checker.py          # GoalChecker
│   │   └── failure_handler.py       # FailureHandler
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── registry.py              # ToolRegistry
│   │   ├── base.py                  # BaseTool
│   │   ├── search/
│   │   │   ├── __init__.py
│   │   │   ├── rag_tool.py
│   │   │   ├── epmc_tool.py
│   │   │   └── web_tool.py
│   │   ├── analysis/
│   │   │   ├── __init__.py
│   │   │   ├── parse_hypothesis_tool.py
│   │   │   ├── decompose_tool.py
│   │   │   └── methodology_tool.py
│   │   ├── design/
│   │   │   ├── __init__.py
│   │   │   ├── experiment_tool.py
│   │   │   ├── controls_tool.py
│   │   │   └── measurements_tool.py
│   │   └── validation/
│   │       ├── __init__.py
│   │       ├── validate_controls_tool.py
│   │       ├── validate_coverage_tool.py
│   │       └── critique_tool.py
│   ├── memory/
│   │   ├── __init__.py
│   │   ├── working.py               # WorkingMemory 상세
│   │   ├── history.py               # ExecutionHistory
│   │   └── long_term.py             # LongTermMemory
│   ├── prompts/
│   │   ├── __init__.py
│   │   ├── reasoning.py             # 추론 프롬프트
│   │   ├── tool_selection.py        # 도구 선택 프롬프트
│   │   └── recovery.py              # 복구 프롬프트
│   └── service.py                   # v4 서비스 인터페이스
├── nodes/                           # v3 노드 (호환성 유지)
├── routers/                         # v3 라우터 (호환성 유지)
├── search/                          # v3 검색 (재사용)
├── rag/                             # v3 RAG (재사용)
├── state.py                         # v3 상태 (호환성 유지)
├── graph.py                         # v3 그래프 (호환성 유지)
└── service.py                       # v3/v4 통합 서비스
```

---

## 7. 위험 요소 및 대응

| 위험 | 가능성 | 영향 | 대응 |
|------|--------|------|------|
| LLM 도구 선택 오류 | 높음 | 중 | 도구 설명 최적화, fallback 전략 |
| 무한 루프 | 중 | 높음 | max_iterations, 중복 탐지 |
| 토큰 비용 증가 | 높음 | 중 | 컨텍스트 압축, 캐싱 |
| 응답 지연 | 중 | 중 | 스트리밍, 비동기 처리 |
| v3 호환성 문제 | 낮음 | 높음 | 호환성 레이어 유지 |

---

## 8. 성공 기준

### 8.1 기능적 기준

```
□ LLM이 80% 이상의 경우 적절한 도구 선택
□ 실패 시 자동 복구 성공률 ≥ 60%
□ 대조군 설계 완성도 ≥ 90%
□ 동일 입력에서 상황에 따라 다른 경로 선택 가능
```

### 8.2 비기능적 기준

```
□ 평균 응답 시간 ≤ v3 × 1.5
□ 토큰 사용량 ≤ v3 × 2.0
□ 메모리 사용량 ≤ 1GB
□ v3 API 하위 호환성 유지
```

---

## 9. 참고 자료

- [ReAct: Synergizing Reasoning and Acting in Language Models](https://arxiv.org/abs/2210.03629)
- [LangChain Agents Documentation](https://python.langchain.com/docs/modules/agents/)
- [AutoGPT Architecture](https://github.com/Significant-Gravitas/AutoGPT)
- [Anthropic Tool Use Best Practices](https://docs.anthropic.com/claude/docs/tool-use)

---

## 10. 변경 이력

| 날짜 | 버전 | 내용 |
|------|------|------|
| 2026-01-22 | 0.1 | 초안 작성 |
