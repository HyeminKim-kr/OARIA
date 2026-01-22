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
                    await self._handle_failure(
                        action, observation, state, history
                    )
                    continue

                # Update state based on observation
                self._update_state(state, action, observation)

                # Track cost
                state.add_cost(observation.cost)

            # Final goal check
            final_status = self.goal_checker.check(state)

            total_duration = int((time.time() - start_time) * 1000)

            return AgentResult(
                success=final_status.achieved,
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
                error=None if final_status.achieved else f"Missing: {', '.join(final_status.missing)}",
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
                    await self._handle_failure(action, observation, state, history)
                    continue

                # Update state
                self._update_state(state, action, observation)
                state.add_cost(observation.cost)

            # Final result
            final_status = self.goal_checker.check(state)
            total_duration = int((time.time() - start_time) * 1000)

            yield (AgentLoopEvent.COMPLETED, {
                "success": final_status.achieved,
                "plan_a": state.plan_a,
                "plan_b": state.plan_b,
                "executive_summary": state.executive_summary,
                "experiment_count": len(state.experiments),
                "quality_score": state.quality_score,
                "iteration_count": state.iteration_count,
                "total_duration_ms": total_duration,
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
    ) -> None:
        """Handle a failed action using the failure handler."""
        failure_type = self.failure_handler.classify_failure(
            observation.error or "Unknown error",
            action.name,
        )

        context = FailureContext(
            failure_type=failure_type,
            error_message=observation.error or "Unknown error",
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
