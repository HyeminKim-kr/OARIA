"""Reason node for LangGraph agent.

This node wraps the existing Reasoner component to decide
the next action based on current state.
"""

import logging
import re
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from app.services.agent.study_plan.v4.langgraph.state import StudyPlanState
from app.services.agent.study_plan.v4.core.state import WorkingMemory, ExecutionHistory
from app.services.agent.study_plan.v4.core.phase_tracker import PhaseTracker

if TYPE_CHECKING:
    from app.services.agent.study_plan.v4.core.reasoner import Reasoner

logger = logging.getLogger(__name__)


def parse_extended_thinking(thought: str, action: str = "", state_summary: dict | None = None) -> dict:
    """Parse extended thinking from LLM response.

    Extracts structured thinking from <thinking> blocks.
    Falls back to action-based descriptions if no thinking block found.

    Args:
        thought: Raw thought string from LLM
        action: The action being taken (for fallback generation)
        state_summary: Current state summary (for context)

    Returns:
        Dict with title, bullets, and raw thought
    """
    result = {
        "title": None,
        "bullets": [],
        "raw": thought,
    }

    # Try to extract <thinking> block
    thinking_match = re.search(r'<thinking>(.*?)</thinking>', thought, re.DOTALL | re.IGNORECASE)

    if thinking_match:
        thinking_content = thinking_match.group(1).strip()

        # Extract title (## heading)
        title_match = re.search(r'^##\s*(.+)$', thinking_content, re.MULTILINE)
        if title_match:
            result["title"] = title_match.group(1).strip()

        # Extract bullets (• or - or * prefixed lines)
        bullets = re.findall(r'^[•\-\*]\s*(.+)$', thinking_content, re.MULTILINE)
        result["bullets"] = [b.strip() for b in bullets if b.strip()]

        # If no bullets found, try to split by newlines and use non-empty lines
        if not result["bullets"]:
            lines = [l.strip() for l in thinking_content.split('\n') if l.strip() and not l.strip().startswith('##')]
            result["bullets"] = lines[:5]

    else:
        # No <thinking> block - generate action-based description
        action_info = get_action_thinking_info(action, thought, state_summary)
        result["title"] = action_info["title"]
        result["bullets"] = action_info["bullets"]

    return result


def get_action_thinking_info(action: str, thought: str, state_summary: dict | None = None) -> dict:
    """Generate thinking description based on action and actual LLM thought.

    Prioritizes actual LLM thought content over generic descriptions.
    Falls back to action-specific templates only when thought is empty.

    Args:
        action: The tool/action being executed
        thought: Raw thought from LLM (prioritized for display)
        state_summary: Current state for context

    Returns:
        Dict with title and bullets
    """
    # Action-specific titles (used when no custom title in thought)
    action_titles = {
        "parse_hypothesis": "가설 분석 및 구조화",
        "decompose_questions": "검증 질문 분해",
        "search_rag": "관련 논문 검색",
        "search_epmc": "Europe PMC 검색",
        "search_web": "웹 검색 수행",
        "design_experiment": "실험 설계",
        "design_controls": "대조군 설계",
        "suggest_measurements": "측정 항목 도출",
        "critique_design": "설계 검토 및 개선",
        "validate_controls": "대조군 검증",
        "validate_coverage": "커버리지 검증",
        "synthesize_plan": "실험 계획서 작성 (Plan A)",
        "generate_plan_b": "대안 계획 작성 (Plan B)",
        "analyze_methodology": "방법론 분석",
        "FINISH": "작업 완료",
    }

    title = action_titles.get(action, f"{action} 실행")
    bullets = []

    # Priority 1: Extract meaningful content from actual LLM thought
    if thought and len(thought) > 30:
        # Clean up the thought text
        cleaned_thought = thought.strip()

        # Try to extract bullet-like sentences
        # Look for patterns like "I need to...", "The hypothesis...", "This will help..."
        sentences = re.split(r'(?<=[.!?])\s+', cleaned_thought)

        for sentence in sentences:
            sentence = sentence.strip()
            # Skip very short sentences or meta-comments
            if len(sentence) < 15:
                continue
            if sentence.lower().startswith(('deciding', 'let me', 'i will', 'now i')):
                continue

            # Clean and add meaningful sentences
            bullet = sentence[:250]  # Limit length
            if bullet and bullet not in bullets:
                bullets.append(bullet)

            if len(bullets) >= 4:  # Max 4 bullets from thought
                break

    # Priority 2: If no bullets extracted, generate from action context
    if not bullets:
        # Generate contextual bullets based on action and state
        if action == "parse_hypothesis":
            bullets = [
                "입력된 가설에서 독립변수(IV)와 종속변수(DV)를 식별하고 있어요",
                "가설의 핵심 메커니즘과 연구 대상을 파악하고 있어요",
                "검증 가능한 형태로 가설을 구조화할게요",
            ]
        elif action == "decompose_questions":
            bullets = [
                "가설을 검증하기 위한 핵심 질문들을 NSPE 프레임워크로 도출하고 있어요",
                "Necessity, Sufficiency, Plausibility, Ethicality 관점에서 분석해요",
            ]
        elif action in ("search_rag", "search_epmc", "search_web"):
            bullets = [
                "가설과 관련된 선행 연구를 검색하고 있어요",
                "관련도 높은 논문과 evidence를 수집할게요",
            ]
        elif action == "design_experiment":
            bullets = [
                "검증 질문에 맞는 실험 방법을 설계하고 있어요",
                "실험 유형과 구체적인 조건을 정의할게요",
            ]
        elif action == "design_controls":
            bullets = [
                "실험 결과의 신뢰도를 높이기 위한 대조군을 설계해요",
                "Vehicle, Positive, Negative control을 고려하고 있어요",
            ]
        elif action == "synthesize_plan":
            bullets = [
                "지금까지 수집한 모든 정보를 종합하고 있어요",
                "이상적인 조건의 완전한 실험 계획서를 작성해요",
            ]
        elif action == "generate_plan_b":
            bullets = [
                "현실적 제약을 고려한 대안 계획을 작성해요",
                "Go/No-Go 기준을 명시하고 Plan A 확장 조건을 포함할게요",
            ]
        elif action == "FINISH":
            bullets = [
                "모든 작업이 완료되었는지 최종 확인하고 있어요",
            ]
        else:
            bullets = [f"{action} 도구를 실행할 준비를 하고 있어요"]

    return {"title": title, "bullets": bullets}


def create_reason_node(reasoner: "Reasoner"):
    """Factory function to create a reason node with injected dependencies.

    Args:
        reasoner: The Reasoner instance to use for decision making

    Returns:
        An async function that can be used as a LangGraph node
    """

    async def reason_node(state: StudyPlanState) -> dict:
        """Decide the next action based on current state.

        Wraps the Reasoner component, converting between
        LangGraph state and WorkingMemory.

        Args:
            state: Current LangGraph state

        Returns:
            Updated state with action decision
        """
        import sys
        iteration = state.get("iteration_count", 0) + 1

        # 확실한 로그
        experiments_count = len(state.get("experiments", []))
        print(f"\n[REASON] ===== Iteration {iteration} =====", file=sys.stderr, flush=True)
        print(f"[REASON] Experiments in state: {experiments_count}", file=sys.stderr, flush=True)
        if experiments_count > 0:
            for i, exp in enumerate(state.get("experiments", [])[:3]):
                print(f"[REASON]   Exp {i}: {exp.get('name', 'N/A')[:50]}", file=sys.stderr, flush=True)

        logger.info(f"=== Reason Node (iteration {iteration}) ===")

        # Debug: Log experiments count in state
        experiments_in_state = state.get("experiments", [])
        logger.info(f"[DEBUG] Experiments in LangGraph state: {len(experiments_in_state)}")
        if experiments_in_state:
            for i, exp in enumerate(experiments_in_state[:3]):
                logger.info(f"[DEBUG]   Exp {i}: id={exp.get('id')}, name={exp.get('name', 'N/A')[:50]}")

        # Convert LangGraph state to WorkingMemory
        working_memory = _state_to_working_memory(state)

        # Reconstruct ExecutionHistory from trace
        history = _state_to_execution_history(state)

        # Get goal
        goal = state.get("goal", "Create a study plan")

        # Call reasoner with token tracking
        thought, action, token_usage = await reasoner.reason_with_tokens(
            working_memory, history, goal
        )

        logger.info(f"Thought: {thought[:100]}...")
        logger.info(f"Action: {action.name}")
        logger.debug(f"Action input: {action.input}")

        # Parse extended thinking from LLM response (with action fallback)
        parsed_thinking = parse_extended_thinking(thought, action.name)
        logger.debug(f"Parsed thinking title: {parsed_thinking.get('title')}")
        logger.debug(f"Parsed thinking bullets: {len(parsed_thinking.get('bullets', []))}")

        # Get phase information
        phase_tracker = PhaseTracker(working_memory)
        current_phase = phase_tracker.get_current_phase()
        phase_progress = phase_tracker.get_phase_progress()
        allowed_tools = phase_tracker.get_allowed_tools()

        logger.info(f"Current phase: {current_phase.value}, allowed tools: {allowed_tools}")

        # Update cumulative tokens
        cumulative = state.get("cumulative_tokens") or {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
        }

        if token_usage:
            cumulative = {
                "prompt_tokens": cumulative["prompt_tokens"] + token_usage.get("prompt_tokens", 0),
                "completion_tokens": cumulative["completion_tokens"] + token_usage.get("completion_tokens", 0),
                "total_tokens": cumulative["total_tokens"] + token_usage.get("total_tokens", 0),
            }

        # Create reasoning event for streaming (Extended Thinking format)
        reasoning_event = (
            "thinking",  # Changed from "reasoning" for frontend compatibility
            {
                "iteration": iteration,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                # Phase information
                "phase": current_phase.value,
                "phase_number": phase_progress.phase_number,
                "total_phases": phase_progress.total_phases,
                "allowed_tools": allowed_tools,
                "phase_progress": {
                    "current": phase_progress.current_phase.value,
                    "completed": [p.value for p in phase_progress.completed_phases],
                    "exit_condition": phase_progress.exit_condition,
                    "progress_detail": phase_progress.progress_detail,
                },
                # Extended Thinking structure
                "title": parsed_thinking.get("title") or f"반복 {iteration}: 다음 행동 결정 중",
                "bullets": parsed_thinking.get("bullets") or [],
                "message": thought,  # Keep raw thought for backward compatibility
                "confidence": action.confidence,
                "token_usage": token_usage,
                "status": "completed",  # This thinking step is complete
            },
        )

        # Check if action is allowed in current phase
        is_allowed, blocked_reason = phase_tracker.is_tool_allowed(action.name)

        # ============================================================
        # Phase Guard: Force redirect if tool not allowed in phase
        # ============================================================
        if not is_allowed:
            logger.warning(f"[Phase Guard] Action '{action.name}' blocked: {blocked_reason}")

            # Get the first allowed tool for current phase
            if allowed_tools:
                redirected_action = allowed_tools[0]
                original_action = action.name

                # Create new action with default parameters
                from app.services.agent.study_plan.v4.core.types import Action
                action = Action(
                    name=redirected_action,
                    input={},  # Will be auto-filled by executor
                    confidence=0.5,
                )
                thought = (
                    f"[Phase Guard] '{original_action}'는 현재 Phase({current_phase.value})에서 "
                    f"사용할 수 없습니다. '{redirected_action}'로 전환합니다."
                )

                logger.info(f"[Phase Guard] Redirected: {original_action} → {redirected_action}")

                # Update the reasoning event with redirect info
                reasoning_event = (
                    "thinking",
                    {
                        **reasoning_event[1],
                        "title": f"[Phase Guard] {redirected_action}로 전환",
                        "bullets": [
                            f"LLM이 '{original_action}'를 선택했지만 현재 Phase에서 허용되지 않음",
                            f"현재 Phase: {current_phase.value}",
                            f"허용된 도구로 자동 전환: {redirected_action}",
                        ],
                        "phase_redirect": {
                            "original": original_action,
                            "redirected": redirected_action,
                            "reason": blocked_reason,
                        },
                    },
                )

        # ============================================================
        # Anti-Infinite-Loop: Force phase advancement if stuck
        # ============================================================
        # Build action sequence from execution trace
        execution_trace = state.get("execution_trace") or []
        action_sequence = [step.get("action", "") for step in execution_trace]

        # Check if we should force advance to next phase
        should_advance, advance_reason = phase_tracker.should_force_advance(
            iteration=iteration,
            failed_actions=history.failed_actions,
            action_sequence=action_sequence,
        )

        if should_advance:
            logger.warning(f"[Anti-Loop] Forcing phase advance: {advance_reason}")

            # Get fallback tool from next phase
            fallback_tool = phase_tracker.get_fallback_tool_for_advance()
            next_phase = phase_tracker.get_next_phase()

            if fallback_tool:
                original_action = action.name
                from app.services.agent.study_plan.v4.core.types import Action
                action = Action(
                    name=fallback_tool,
                    input={},  # Will be auto-filled by executor
                    confidence=0.4,
                )
                thought = (
                    f"[Anti-Loop] {current_phase.value} phase에서 막힘 감지. "
                    f"'{fallback_tool}'로 강제 전환하여 {next_phase.value} phase로 진행합니다. "
                    f"이유: {advance_reason}"
                )

                logger.info(f"[Anti-Loop] Forced advance: {original_action} → {fallback_tool} (to {next_phase.value})")

                # Update the reasoning event
                reasoning_event = (
                    "thinking",
                    {
                        **reasoning_event[1],
                        "title": f"[Anti-Loop] {next_phase.value} phase로 강제 전환",
                        "bullets": [
                            f"현재 Phase({current_phase.value})에서 진행 불가 감지",
                            f"이유: {advance_reason}",
                            f"다음 Phase({next_phase.value})의 '{fallback_tool}'로 강제 전환",
                        ],
                        "forced_advance": {
                            "from_phase": current_phase.value,
                            "to_phase": next_phase.value,
                            "tool": fallback_tool,
                            "reason": advance_reason,
                        },
                    },
                )

        # Create acting event for streaming
        # Note: After redirect, the action is now allowed
        acting_event = (
            "acting",
            {
                "iteration": iteration,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "phase": current_phase.value,
                "action": action.name,
                "thought": thought,  # Include thought for display
                "parameters": action.input,
                "confidence": action.confidence,
                "allowed": True,  # After redirect, always allowed
                "blocked_reason": None,
                "was_redirected": not is_allowed,  # Track if redirect happened
            },
        )

        # Get existing events and add new ones
        pending_events = list(state.get("pending_events") or [])
        pending_events.extend([reasoning_event, acting_event])

        return {
            "iteration_count": iteration,
            "current_action": action.name,
            "current_action_input": action.input,
            "current_thought": thought,
            "current_confidence": action.confidence,
            "cumulative_tokens": cumulative,
            "pending_events": pending_events,
        }

    return reason_node


def _state_to_working_memory(state: StudyPlanState) -> WorkingMemory:
    """Convert LangGraph state to WorkingMemory.

    This allows reusing the existing Reasoner without modification.
    """
    memory = WorkingMemory()

    # Copy relevant fields
    memory.run_id = state.get("run_id", memory.run_id)
    memory.goal = state.get("goal", "")
    memory.original_hypothesis = state.get("original_hypothesis", "")
    memory.research_context = state.get("research_context")
    memory.constraints = state.get("constraints") or []
    memory.preferred_experiment_types = state.get("preferred_experiment_types") or []

    # Parsed state
    memory.structured_hypothesis = state.get("structured_hypothesis")
    memory.hypothesis_confidence = state.get("hypothesis_confidence", 0.0)
    memory.test_questions = state.get("test_questions") or []
    memory.answered_questions = set(state.get("answered_questions") or [])

    # Search results
    memory.retrieved_papers = state.get("retrieved_papers") or []
    memory.evidence_snippets = state.get("evidence_snippets") or []
    memory.search_coverage = state.get("search_coverage", 0.0)
    memory.search_tiers_used = state.get("search_tiers_used") or []

    # Design results
    memory.experiments = state.get("experiments") or []
    memory.controls = state.get("controls") or {}
    memory.measurements = state.get("measurements") or []

    # Validation
    memory.validation_results = state.get("validation_results") or []
    memory.quality_score = state.get("quality_score", 0.0)
    memory.critique_history = state.get("critique_history") or []

    # Output
    memory.plan_a = state.get("plan_a")
    memory.plan_b = state.get("plan_b")
    memory.executive_summary = state.get("executive_summary")

    # Metadata
    memory.iteration_count = state.get("iteration_count", 0)
    memory.total_cost = state.get("total_cost", 0.0)

    return memory


def _state_to_execution_history(state: StudyPlanState) -> ExecutionHistory:
    """Reconstruct ExecutionHistory from state.

    Builds history from execution_trace for failure tracking
    and loop detection.
    """
    history = ExecutionHistory()

    # Reconstruct from execution trace
    trace = state.get("execution_trace") or []
    for step_data in trace:
        # Count failures
        if not step_data.get("success", True):
            action = step_data.get("action", "unknown")
            history.failed_actions[action] = history.failed_actions.get(action, 0) + 1
            history._consecutive_failures += 1
            history._last_error = step_data.get("error")
        else:
            history._consecutive_failures = 0

        # Track action sequence for loop detection
        history._action_sequence.append(step_data.get("action", "unknown"))

    # Also use state's consecutive_failures if available
    if state.get("consecutive_failures", 0) > history._consecutive_failures:
        history._consecutive_failures = state["consecutive_failures"]

    return history
