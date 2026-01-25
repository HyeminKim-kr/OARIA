"""Main agent loop for v4.

Implements the ReAct (Reasoning + Acting) pattern:
Thought -> Action -> Observation -> Thought -> ...

Until goal is achieved or max iterations reached.
"""

import logging
import time
from datetime import datetime
from typing import AsyncIterator, TYPE_CHECKING

from langchain_openai import ChatOpenAI

from app.services.agent.study_plan.v4.core.types import (
    Action,
    Observation,
    AgentResult,
)
from app.services.agent.study_plan.v4.core.state import (
    WorkingMemory,
    ExecutionHistory,
    ExecutionStep,
)
from app.services.agent.study_plan.v4.core.reasoner import Reasoner
from app.services.agent.study_plan.v4.core.executor import Executor
from app.services.agent.study_plan.v4.core.goal_checker import GoalChecker
from app.services.agent.study_plan.v4.core.failure_handler import (
    FailureHandler,
    FailureContext,
)

if TYPE_CHECKING:
    from app.services.agent.study_plan.v4.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)


class AgentLoopEvent:
    """Event types emitted during agent execution."""

    STARTED = "started"
    THINKING = "thinking"
    ACTING = "acting"
    OBSERVATION = "observation"
    RECOVERY = "recovery"
    GOAL_CHECK = "goal_check"
    COMPLETED = "completed"
    ERROR = "error"


class AgentLoop:
    """ReAct-based agent loop for study plan generation.

    The loop follows this pattern:
    1. Perceive: Analyze current state
    2. Reason: Decide next action (LLM)
    3. Act: Execute tool
    4. Observe: Capture result
    5. Update: Modify state
    6. Check: Goal achieved or failure?

    Repeat until goal achieved or max iterations.
    """

    DEFAULT_GOAL = (
        "Generate a comprehensive research study plan to test the given hypothesis. "
        "The plan should include: structured hypothesis, test questions (NSPE framework), "
        "experiment designs with proper controls, measurements that cover hypothesis variables, "
        "and achieve a quality score of at least 70%."
    )

    def __init__(
        self,
        llm: ChatOpenAI,
        tools: "ToolRegistry",
        max_iterations: int = 30,
        failure_handler: FailureHandler | None = None,
        goal_checker: GoalChecker | None = None,
    ):
        """Initialize agent loop.

        Args:
            llm: Language model for reasoning
            tools: Tool registry with available tools
            max_iterations: Maximum iterations before forced stop
            failure_handler: Handler for failures (optional)
            goal_checker: Checker for goal completion (optional)
        """
        self.llm = llm
        self.tools = tools
        self.max_iterations = max_iterations

        # Initialize components
        self.reasoner = Reasoner(llm, tools)
        self.executor = Executor(tools)
        self.failure_handler = failure_handler or FailureHandler(llm)
        self.goal_checker = goal_checker or GoalChecker()

    async def run(
        self,
        hypothesis: str,
        research_context: str | None = None,
        constraints: list[str] | None = None,
        preferred_experiment_types: list[str] | None = None,
        goal: str | None = None,
    ) -> AgentResult:
        """Run the agent loop to completion.

        Args:
            hypothesis: The research hypothesis to test
            research_context: Optional context about the research area
            constraints: Optional constraints on the experiment design
            preferred_experiment_types: Optional preferred experiment types
            goal: Optional custom goal (uses default if not provided)

        Returns:
            AgentResult with final plan and metadata
        """
        start_time = time.time()

        # Initialize state
        state = self._initialize_state(
            hypothesis, research_context, constraints, preferred_experiment_types
        )
        history = ExecutionHistory()
        goal = goal or self.DEFAULT_GOAL

        logger.info(f"Starting agent loop for hypothesis: {hypothesis[:100]}...")

        try:
            # Main loop
            while state.iteration_count < self.max_iterations:
                state.increment_iteration()

                # Check for goal completion
                goal_status = self.goal_checker.check(state)
                if goal_status.achieved:
                    logger.info(f"Goal achieved at iteration {state.iteration_count}")
                    break

                # Reason: Decide next action
                thought, action = await self.reasoner.reason(state, history, goal)
                logger.debug(f"Thought: {thought[:200]}...")
                logger.debug(f"Action: {action.name}")

                # Check for terminal action
                if action.name == "FINISH":
                    logger.info("Agent decided to finish")
                    break

                # Act: Execute tool
                observation = await self.executor.execute(action)

                # Record step
                step = ExecutionStep(
                    step_number=state.iteration_count,
                    timestamp=datetime.utcnow(),
                    thought=thought,
                    action=action.name,
                    action_input=action.input,
                    observation=observation.result if observation.success else {"error": observation.error},
                    success=observation.success,
                    error=observation.error,
                    duration_ms=observation.duration_ms,
                )
                history.add_step(step)

                # Handle failure
                if not observation.success:
                    should_abort = await self._handle_failure(
                        action, observation, state, history
                    )
                    if should_abort:
                        logger.warning(f"Aborting due to: {history.get_abort_reason()}")
                        break
                    continue

                # Update state based on observation
                self._update_state(state, action, observation)

                # Track cost
                state.add_cost(observation.cost)

            # Fallback Synthesis: plan_a가 없고 experiments가 있으면 강제 synthesis
            if not state.plan_a and state.experiments:
                logger.warning(
                    f"No plan_a generated after {state.iteration_count} iterations. "
                    f"Attempting fallback synthesis with {len(state.experiments)} experiments..."
                )
                synthesize_tool = self.tools.get("synthesize_plan")
                if synthesize_tool:
                    try:
                        synthesis_result = await synthesize_tool.run(
                            experiments=state.experiments,
                            evidence=state.evidence_snippets,
                            metadata={
                                "hypothesis": state.structured_hypothesis or {"raw": state.original_hypothesis},
                                "constraints": state.constraints,
                            },
                        )
                        if isinstance(synthesis_result, dict):
                            state.plan_a = synthesis_result.get("plan")
                            state.executive_summary = synthesis_result.get("summary")
                            if state.plan_a:
                                logger.info("Fallback synthesis successful - plan_a generated")
                            else:
                                logger.warning("Fallback synthesis returned empty plan")
                    except Exception as e:
                        logger.error(f"Fallback synthesis failed: {e}")

            # Fallback Plan B: plan_a는 있지만 plan_b가 없으면 강제 생성
            if state.plan_a and not state.plan_b:
                logger.warning("No plan_b generated, attempting fallback Plan B generation...")
                plan_b_tool = self.tools.get("generate_plan_b")
                if plan_b_tool:
                    try:
                        plan_b_result = await plan_b_tool.run(
                            plan_a={"plan": state.plan_a},
                            constraints=state.constraints or ["Limited budget", "Time constraints"],
                        )
                        if isinstance(plan_b_result, dict):
                            state.plan_b = plan_b_result.get("plan_b")
                            if state.plan_b:
                                logger.info("Fallback Plan B generation successful")
                            else:
                                logger.warning("Fallback Plan B generation returned empty plan")
                    except Exception as e:
                        logger.error(f"Fallback Plan B generation failed: {e}")

            # Final goal check
            final_status = self.goal_checker.check(state)

            total_duration = int((time.time() - start_time) * 1000)

            # Log final state for debugging
            logger.info(
                f"Agent loop completed: "
                f"plan_a={'Yes' if state.plan_a else 'No'}, "
                f"plan_b={'Yes' if state.plan_b else 'No'}, "
                f"experiments={len(state.experiments)}, "
                f"iterations={state.iteration_count}"
            )

            # 에러 메시지 결정
            error_message = None
            if history.has_critical_error():
                error_message = history.get_critical_error()
            elif history.should_abort():
                error_message = history.get_abort_reason()
            elif not final_status.achieved:
                error_message = f"Missing: {', '.join(final_status.missing)}"

            # plan_a가 생성되었으면 성공으로 간주 (strict 목표 체크와 별개로)
            has_valid_plan = bool(state.plan_a and len(state.plan_a) > 100)
            is_success = (final_status.achieved or has_valid_plan) and not history.has_critical_error()

            return AgentResult(
                success=is_success,
                final_plan=state.plan_a or "",  # v3 호환성
                plan_a=state.plan_a,
                plan_b=state.plan_b,
                executive_summary=state.executive_summary,
                experiment_count=len(state.experiments),
                quality_score=state.quality_score,
                iteration_count=state.iteration_count,
                total_duration_ms=total_duration,
                experiments=state.experiments,
                evidence_snippets=state.evidence_snippets,
                measurements=state.measurements,
                validation_results=state.validation_results,
                execution_trace=history.to_trace(),
                error=error_message,
                goals_achieved=final_status.achieved,
                goals_missing=final_status.missing,
            )

        except Exception as e:
            logger.error(f"Agent loop error: {e}", exc_info=True)
            total_duration = int((time.time() - start_time) * 1000)

            return AgentResult(
                success=False,
                iteration_count=state.iteration_count,
                total_duration_ms=total_duration,
                execution_trace=history.to_trace(),
                error=str(e),
            )

    async def run_stream(
        self,
        hypothesis: str,
        research_context: str | None = None,
        constraints: list[str] | None = None,
        preferred_experiment_types: list[str] | None = None,
        goal: str | None = None,
    ) -> AsyncIterator[tuple[str, dict]]:
        """Run agent loop with streaming events.

        Yields (event_type, data) tuples for real-time updates.

        Args:
            hypothesis: The research hypothesis
            research_context: Optional context
            constraints: Optional constraints
            preferred_experiment_types: Optional preferences
            goal: Optional custom goal

        Yields:
            Tuple of (event_type, event_data)
        """
        start_time = time.time()

        # Initialize state
        state = self._initialize_state(
            hypothesis, research_context, constraints, preferred_experiment_types
        )
        history = ExecutionHistory()
        goal = goal or self.DEFAULT_GOAL

        yield (AgentLoopEvent.STARTED, {
            "run_id": state.run_id,
            "hypothesis": hypothesis[:100],
            "goal": goal,
        })

        try:
            while state.iteration_count < self.max_iterations:
                state.increment_iteration()

                # Check goal
                goal_status = self.goal_checker.check(state)

                yield (AgentLoopEvent.GOAL_CHECK, {
                    "iteration": state.iteration_count,
                    "achieved": goal_status.achieved,
                    "details": goal_status.details,
                    "missing": goal_status.missing,
                })

                if goal_status.achieved:
                    break

                # Reason
                yield (AgentLoopEvent.THINKING, {
                    "iteration": state.iteration_count,
                    "message": "Deciding next action...",
                })

                thought, action = await self.reasoner.reason(state, history, goal)

                yield (AgentLoopEvent.ACTING, {
                    "iteration": state.iteration_count,
                    "thought": thought,
                    "action": action.name,
                    "action_input": action.input,
                    "confidence": action.confidence,
                })

                if action.name == "FINISH":
                    break

                # Execute
                observation = await self.executor.execute(action)

                yield (AgentLoopEvent.OBSERVATION, {
                    "iteration": state.iteration_count,
                    "action": action.name,
                    "success": observation.success,
                    "duration_ms": observation.duration_ms,
                    "error": observation.error,
                })

                # Record
                step = ExecutionStep(
                    step_number=state.iteration_count,
                    timestamp=datetime.utcnow(),
                    thought=thought,
                    action=action.name,
                    action_input=action.input,
                    observation=observation.result if observation.success else {"error": observation.error},
                    success=observation.success,
                    error=observation.error,
                    duration_ms=observation.duration_ms,
                )
                history.add_step(step)

                # Handle failure
                if not observation.success:
                    yield (AgentLoopEvent.RECOVERY, {
                        "iteration": state.iteration_count,
                        "error": observation.error,
                        "message": "Attempting recovery...",
                    })
                    should_abort = await self._handle_failure(action, observation, state, history)
                    if should_abort:
                        abort_reason = history.get_abort_reason()
                        logger.warning(f"Aborting stream due to: {abort_reason}")
                        yield (AgentLoopEvent.ERROR, {
                            "iteration": state.iteration_count,
                            "error": abort_reason,
                            "critical": history.has_critical_error(),
                        })
                        return
                    continue

                # Update state
                self._update_state(state, action, observation)
                state.add_cost(observation.cost)

            # Fallback Synthesis: plan_a가 없고 experiments가 있으면 강제 synthesis
            if not state.plan_a and state.experiments:
                logger.warning(
                    f"No plan_a generated after {state.iteration_count} iterations. "
                    f"Attempting fallback synthesis with {len(state.experiments)} experiments..."
                )
                synthesize_tool = self.tools.get("synthesize_plan")
                if synthesize_tool:
                    try:
                        synthesis_result = await synthesize_tool.run(
                            experiments=state.experiments,
                            evidence=state.evidence_snippets,
                            metadata={
                                "hypothesis": state.structured_hypothesis or {"raw": state.original_hypothesis},
                                "constraints": state.constraints,
                            },
                        )
                        if isinstance(synthesis_result, dict):
                            state.plan_a = synthesis_result.get("plan")
                            state.executive_summary = synthesis_result.get("summary")
                            if state.plan_a:
                                logger.info("Fallback synthesis successful - plan_a generated")
                            else:
                                logger.warning("Fallback synthesis returned empty plan")
                    except Exception as e:
                        logger.error(f"Fallback synthesis failed: {e}")

            # Fallback Plan B: plan_a는 있지만 plan_b가 없으면 강제 생성
            if state.plan_a and not state.plan_b:
                logger.warning("No plan_b generated, attempting fallback Plan B generation...")
                plan_b_tool = self.tools.get("generate_plan_b")
                if plan_b_tool:
                    try:
                        plan_b_result = await plan_b_tool.run(
                            plan_a={"plan": state.plan_a},
                            constraints=state.constraints or ["Limited budget", "Time constraints"],
                        )
                        if isinstance(plan_b_result, dict):
                            state.plan_b = plan_b_result.get("plan_b")
                            if state.plan_b:
                                logger.info("Fallback Plan B generation successful")
                            else:
                                logger.warning("Fallback Plan B generation returned empty plan")
                    except Exception as e:
                        logger.error(f"Fallback Plan B generation failed: {e}")

            # Final result
            final_status = self.goal_checker.check(state)
            total_duration = int((time.time() - start_time) * 1000)

            # Log final state for debugging
            logger.info(
                f"Agent loop (stream) completed: "
                f"plan_a={'Yes' if state.plan_a else 'No'}, "
                f"plan_b={'Yes' if state.plan_b else 'No'}, "
                f"experiments={len(state.experiments)}, "
                f"iterations={state.iteration_count}"
            )

            # plan_a가 생성되었으면 성공으로 간주 (strict 목표 체크와 별개로)
            has_valid_plan = bool(state.plan_a and len(state.plan_a) > 100)
            is_success = final_status.achieved or has_valid_plan

            # final_plan을 v3와 호환되도록 plan_a로 설정
            final_plan = state.plan_a or ""

            yield (AgentLoopEvent.COMPLETED, {
                "success": is_success,
                "final_plan": final_plan,  # v3 호환성
                "plan_a": state.plan_a,
                "plan_b": state.plan_b,
                "executive_summary": state.executive_summary,
                "experiment_count": len(state.experiments),
                "quality_score": state.quality_score,
                "iteration_count": state.iteration_count,
                "total_duration_ms": total_duration,
                "goals_achieved": final_status.achieved,
                "goals_missing": final_status.missing if not final_status.achieved else [],
            })

        except Exception as e:
            logger.error(f"Agent loop error: {e}", exc_info=True)
            yield (AgentLoopEvent.ERROR, {
                "error": str(e),
                "iteration": state.iteration_count,
            })

    def _initialize_state(
        self,
        hypothesis: str,
        research_context: str | None,
        constraints: list[str] | None,
        preferred_experiment_types: list[str] | None,
    ) -> WorkingMemory:
        """Initialize working memory with input parameters."""
        return WorkingMemory(
            goal=self.DEFAULT_GOAL,
            original_hypothesis=hypothesis,
            research_context=research_context,
            constraints=constraints or [],
            preferred_experiment_types=preferred_experiment_types or [],
        )

    async def _handle_failure(
        self,
        action: Action,
        observation: Observation,
        state: WorkingMemory,
        history: ExecutionHistory,
    ) -> bool:
        """Handle a failed action using the failure handler.

        Returns:
            True if agent should abort, False to continue
        """
        error_message = observation.error or "Unknown error"
        failure_type = self.failure_handler.classify_failure(
            error_message,
            action.name,
        )

        # Critical 에러는 즉시 중단
        if self.failure_handler.is_critical(failure_type):
            logger.error(f"Critical error detected: {failure_type} - {error_message}")
            history.set_critical_error(error_message)
            return True

        # 연속 실패/동일 에러 체크
        if history.should_abort():
            logger.warning(f"Abort threshold reached: {history.get_abort_reason()}")
            return True

        context = FailureContext(
            failure_type=failure_type,
            error_message=error_message,
            failed_action=action.name,
            failed_input=action.input,
            attempt_count=history.failed_actions.get(action.name, 0) + 1,
        )

        recovery_plan = await self.failure_handler.handle(context, state, history)

        logger.info(
            f"Recovery plan: {recovery_plan.strategy}, "
            f"actions: {[a.name for a in recovery_plan.next_actions]}"
        )

        # Execute recovery actions (limited to 1 to prevent cascade)
        if recovery_plan.next_actions:
            recovery_action = recovery_plan.next_actions[0]
            recovery_obs = await self.executor.execute(recovery_action)

            if recovery_obs.success:
                self._update_state(state, recovery_action, recovery_obs)

        return False

    def _update_state(
        self,
        state: WorkingMemory,
        action: Action,
        observation: Observation,
    ) -> None:
        """Update working memory based on action result."""
        result = observation.result
        if not result:
            return

        # Handle different action types
        if action.name == "parse_hypothesis":
            if isinstance(result, dict):
                state.structured_hypothesis = result
                state.hypothesis_confidence = result.get("confidence", 0.0)

        elif action.name == "decompose_questions":
            if isinstance(result, dict) and "questions" in result:
                state.test_questions = result["questions"]
            elif isinstance(result, list):
                state.test_questions = result

        elif action.name in ("search_rag", "search_epmc", "search_web"):
            tier_map = {"search_rag": 1, "search_epmc": 2, "search_web": 3}
            state.search_tiers_used.append(tier_map.get(action.name, 1))

            if isinstance(result, dict):
                if "papers" in result:
                    state.retrieved_papers.extend(result["papers"])
                if "coverage" in result:
                    state.search_coverage = max(state.search_coverage, result["coverage"])
                if "snippets" in result:
                    state.evidence_snippets.extend(result["snippets"])

        elif action.name == "design_experiment":
            if isinstance(result, dict) and "experiment" in result:
                state.experiments.append(result["experiment"])
            elif isinstance(result, dict):
                state.experiments.append(result)

        elif action.name == "design_controls":
            if isinstance(result, dict):
                exp_id = action.input.get("experiment", {}).get("id", "default")
                if "controls" in result:
                    state.controls[exp_id] = result["controls"]
                elif isinstance(result, list):
                    state.controls[exp_id] = result

        elif action.name == "suggest_measurements":
            if isinstance(result, dict) and "measurements" in result:
                state.measurements.extend(result["measurements"])
            elif isinstance(result, list):
                state.measurements.extend(result)

        elif action.name == "critique_design":
            if isinstance(result, dict):
                state.critique_history.append(result)
                if "score" in result:
                    state.quality_score = result["score"]
                if "validation_results" in result:
                    state.validation_results.extend(result["validation_results"])

        elif action.name in ("validate_controls", "validate_coverage"):
            if isinstance(result, dict):
                state.validation_results.append({
                    "type": action.name,
                    **result,
                })

        elif action.name == "synthesize_plan":
            if isinstance(result, dict):
                state.plan_a = result.get("plan")
                state.executive_summary = result.get("summary")

        elif action.name == "generate_plan_b":
            if isinstance(result, dict):
                state.plan_b = result.get("plan_b")
