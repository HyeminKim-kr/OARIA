"""Phase tracker for Study Plan Agent v4.

Tracks the current phase and generates phase-aware prompts for the LLM.
"""

from dataclasses import dataclass, field

from app.services.agent.study_plan.v4.core.phase import (
    PHASE_EXIT_CONDITIONS,
    PHASE_NAMES_KO,
    PHASE_ORDER,
    PHASE_TOOLS,
    Phase,
    get_phase_number,
    get_total_phases,
)
from app.services.agent.study_plan.v4.core.state_view import StateView


@dataclass
class PhaseStatus:
    """Status of a single phase."""

    phase: Phase
    completed: bool
    is_current: bool
    requirement: str


@dataclass
class PhaseProgress:
    """Overall phase progress information."""

    current_phase: Phase
    phase_number: int
    total_phases: int
    completed_phases: list[Phase]
    allowed_tools: list[str]
    exit_condition: str
    progress_detail: str


class PhaseTracker:
    """Tracks agent phase and provides phase-aware context.

    Determines the current phase based on StateView
    and generates prompts to help LLM understand where it is.
    """

    # Research phase: max search attempts per question before moving on
    MAX_SEARCH_ATTEMPTS_PER_QUESTION = 3

    def __init__(self, state: StateView):
        """Initialize with state view.

        Args:
            state: Current state view (read-only)
        """
        self.state = state
        self._tool_calls: dict[str, int] = {}

    def record_tool_call(self, tool_name: str) -> None:
        """Record a tool call for tracking.

        Args:
            tool_name: Name of the tool that was called
        """
        self._tool_calls[tool_name] = self._tool_calls.get(tool_name, 0) + 1

    def get_tool_call_count(self, tool_name: str) -> int:
        """Get number of times a tool has been called.

        Args:
            tool_name: Name of the tool

        Returns:
            Number of calls
        """
        return self._tool_calls.get(tool_name, 0)

    def get_current_phase(self) -> Phase:
        """Determine current phase based on state.

        Returns:
            Current Phase
        """
        # Phase 1: UNDERSTAND - 가설 파싱
        if not self.state.structured_hypothesis:
            return Phase.UNDERSTAND

        # Phase 2: DECOMPOSE - 질문 분해
        if len(self.state.test_questions) < 3:
            return Phase.DECOMPOSE

        # Phase 3: RESEARCH - 문헌 검색
        if not self._has_enough_evidence():
            return Phase.RESEARCH

        # Phase 4: DESIGN - 실험 설계
        if len(self.state.experiments) < 1:
            return Phase.DESIGN

        # Phase 5: VALIDATE - 검증
        if self.state.quality_score < 0.7:
            return Phase.VALIDATE

        # Phase 6: SYNTHESIZE - 최종 합성
        if not (self.state.plan_a and self.state.plan_b):
            return Phase.SYNTHESIZE

        return Phase.COMPLETED

    def _has_enough_evidence(self) -> bool:
        """Check if research phase should be considered complete.

        Evidence is enough if:
        - We have any evidence snippets (simplified), OR
        - We have retrieved papers, OR
        - iteration_count >= 10 (force advancement to prevent infinite loops)

        Returns:
            True if evidence gathering is complete
        """
        # Option 1: We have evidence snippets (any amount)
        if self.state.evidence_snippets and len(self.state.evidence_snippets) >= 1:
            return True

        # Option 2: We have retrieved papers (search succeeded)
        if self.state.retrieved_papers and len(self.state.retrieved_papers) >= 3:
            return True

        # Option 3: Force advancement after certain iterations
        # (prevents infinite RESEARCH loop when search returns no evidence)
        if self.state.iteration_count >= 10:
            return True

        return False

    def get_allowed_tools(self) -> list[str]:
        """Get tools allowed in current phase.

        Returns:
            List of allowed tool names
        """
        phase = self.get_current_phase()
        return PHASE_TOOLS.get(phase, [])

    def is_tool_allowed(self, tool_name: str) -> tuple[bool, str]:
        """Check if a tool is allowed in current phase.

        Args:
            tool_name: Name of the tool to check

        Returns:
            Tuple of (allowed, reason)
        """
        phase = self.get_current_phase()
        allowed_tools = PHASE_TOOLS.get(phase, [])

        # FINISH is always allowed
        if tool_name == "FINISH":
            return True, "FINISH is always allowed"

        if tool_name in allowed_tools:
            return True, f"Tool allowed in {phase.value} phase"
        else:
            return (
                False,
                f"Tool '{tool_name}' not allowed in {phase.value} phase. "
                f"Allowed tools: {', '.join(allowed_tools)}",
            )

    # ============================================================
    # Forced Phase Advancement (Anti-Infinite-Loop)
    # ============================================================

    # Thresholds for forcing phase advancement
    MAX_ITERATIONS_PER_PHASE = 5  # Max iterations stuck in same phase
    MAX_TOOL_FAILURES = 3  # Max failures for same tool before skip

    def should_force_advance(
        self,
        iteration: int,
        failed_actions: dict[str, int],
        action_sequence: list[str],
    ) -> tuple[bool, str]:
        """Check if phase should be forcibly advanced due to being stuck.

        Args:
            iteration: Current iteration count
            failed_actions: Dict of {action: failure_count}
            action_sequence: List of recent action names

        Returns:
            Tuple of (should_advance, reason)
        """
        current_phase = self.get_current_phase()
        allowed_tools = PHASE_TOOLS.get(current_phase, [])

        # Check 1: All allowed tools have failed multiple times
        all_tools_exhausted = all(
            failed_actions.get(tool, 0) >= self.MAX_TOOL_FAILURES
            for tool in allowed_tools
        ) if allowed_tools else False

        if all_tools_exhausted:
            return True, f"All tools in {current_phase.value} phase have failed {self.MAX_TOOL_FAILURES}+ times"

        # Check 2: Same tool called repeatedly (loop detection)
        if len(action_sequence) >= 4:
            recent_4 = action_sequence[-4:]
            if len(set(recent_4)) == 1 and recent_4[0] in allowed_tools:
                # Same tool called 4+ times in a row
                return True, f"Tool '{recent_4[0]}' called 4+ times in a row (loop detected)"

        # Check 3: High iteration count with no progress
        # Phase-specific thresholds
        phase_iteration_limits = {
            Phase.UNDERSTAND: 5,
            Phase.DECOMPOSE: 8,
            Phase.RESEARCH: 15,
            Phase.DESIGN: 20,
            Phase.VALIDATE: 25,
            Phase.SYNTHESIZE: 30,
        }
        limit = phase_iteration_limits.get(current_phase, 30)

        if iteration > limit and current_phase != Phase.COMPLETED:
            return True, f"Iteration {iteration} exceeds limit {limit} for {current_phase.value} phase"

        return False, ""

    def get_next_phase(self) -> Phase:
        """Get the next phase after current.

        Returns:
            Next Phase, or COMPLETED if at end
        """
        current = self.get_current_phase()
        try:
            current_idx = PHASE_ORDER.index(current)
            if current_idx < len(PHASE_ORDER) - 1:
                return PHASE_ORDER[current_idx + 1]
        except ValueError:
            pass
        return Phase.COMPLETED

    def get_fallback_tool_for_advance(self) -> str | None:
        """Get a tool from the next phase to force advancement.

        When current phase is stuck, this returns the first tool
        from the next phase to force progress.

        Returns:
            Tool name or None if no next phase
        """
        next_phase = self.get_next_phase()
        if next_phase == Phase.COMPLETED:
            return "FINISH"

        next_tools = PHASE_TOOLS.get(next_phase, [])
        return next_tools[0] if next_tools else None

    def get_phase_progress(self) -> PhaseProgress:
        """Get comprehensive phase progress information.

        Returns:
            PhaseProgress with all details
        """
        current_phase = self.get_current_phase()

        # Determine completed phases
        completed = []
        for phase in PHASE_ORDER:
            if phase == current_phase:
                break
            if phase != Phase.COMPLETED:
                completed.append(phase)

        return PhaseProgress(
            current_phase=current_phase,
            phase_number=get_phase_number(current_phase),
            total_phases=get_total_phases(),
            completed_phases=completed,
            allowed_tools=self.get_allowed_tools(),
            exit_condition=PHASE_EXIT_CONDITIONS.get(current_phase, ""),
            progress_detail=self._get_progress_detail(current_phase),
        )

    def _get_progress_detail(self, phase: Phase) -> str:
        """Get detailed progress for current phase.

        Args:
            phase: Current phase

        Returns:
            Human-readable progress detail
        """
        if phase == Phase.UNDERSTAND:
            return "가설 파싱 대기 중"

        if phase == Phase.DECOMPOSE:
            count = len(self.state.test_questions)
            return f"질문 {count}/3개 생성됨"

        if phase == Phase.RESEARCH:
            total_q = len(self.state.test_questions)
            evidence_count = len(self.state.evidence_snippets)
            search_count = sum(
                self._tool_calls.get(t, 0)
                for t in ["search_rag", "search_epmc", "search_web"]
            )
            return f"증거 {evidence_count}개 수집, 검색 {search_count}회 시도"

        if phase == Phase.DESIGN:
            exp_count = len(self.state.experiments)
            return f"실험 {exp_count}개 설계됨 (최소 1개 필요)"

        if phase == Phase.VALIDATE:
            score = self.state.quality_score
            return f"품질 점수 {score:.0%} (목표 70%)"

        if phase == Phase.SYNTHESIZE:
            plan_a = "생성됨" if self.state.plan_a else "미생성"
            plan_b = "생성됨" if self.state.plan_b else "미생성"
            return f"Plan A: {plan_a}, Plan B: {plan_b}"

        return "완료"

    def get_phase_prompt(self) -> str:
        """Generate phase context prompt for LLM.

        This is the key prompt that helps LLM understand:
        1. What phase it's in
        2. What it can do
        3. How to proceed

        Returns:
            Formatted prompt string
        """
        progress = self.get_phase_progress()

        # Build phase status table
        status_lines = []
        for phase in PHASE_ORDER:
            if phase == Phase.COMPLETED:
                continue

            if phase in progress.completed_phases:
                status = "✓ Done"
            elif phase == progress.current_phase:
                status = "▶ NOW"
            else:
                status = "⏳"

            phase_name = PHASE_NAMES_KO.get(phase, phase.value)
            requirement = PHASE_EXIT_CONDITIONS.get(phase, "")
            status_lines.append(f"| {phase_name} | {status} | {requirement} |")

        status_table = "\n".join(status_lines)

        # Build allowed tools list
        tools_list = "\n".join(f"- {tool}" for tool in progress.allowed_tools)
        if not tools_list:
            tools_list = "- (없음 - FINISH만 가능)"

        # Format the prompt
        prompt = f"""
## Current Phase: {PHASE_NAMES_KO.get(progress.current_phase, progress.current_phase.value)} ({progress.phase_number}/{progress.total_phases})

| Phase | Status | Requirement |
|-------|--------|-------------|
{status_table}

**In this phase, you can ONLY use:**
{tools_list}

**Exit condition:** {progress.exit_condition}

**Current progress:** {progress.progress_detail}

**IMPORTANT:** 현재 Phase에서 허용된 도구만 사용하세요. 다른 도구를 선택하면 거부됩니다.
"""
        return prompt.strip()

    def get_phase_statuses(self) -> list[PhaseStatus]:
        """Get status of all phases for UI display.

        Returns:
            List of PhaseStatus for each phase
        """
        current_phase = self.get_current_phase()
        progress = self.get_phase_progress()

        statuses = []
        for phase in PHASE_ORDER:
            if phase == Phase.COMPLETED:
                continue

            statuses.append(
                PhaseStatus(
                    phase=phase,
                    completed=phase in progress.completed_phases,
                    is_current=phase == current_phase,
                    requirement=PHASE_EXIT_CONDITIONS.get(phase, ""),
                )
            )

        return statuses
