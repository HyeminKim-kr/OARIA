"""Executor component for v4 agent.

The Executor is responsible for:
1. Running tools based on actions
2. Capturing results and errors
3. Tracking execution metrics
4. Auto-filling missing parameters from state
"""

import logging
import time
from typing import TYPE_CHECKING, Any

from app.services.agent.study_plan.v4.core.types import Action, Observation

if TYPE_CHECKING:
    from app.services.agent.study_plan.v4.tools.registry import ToolRegistry
    from app.services.agent.study_plan.v4.core.state import WorkingMemory

logger = logging.getLogger(__name__)


class Executor:
    """Executes agent actions using the tool registry.

    Handles:
    - Tool invocation
    - Error capture
    - Timing and cost tracking
    - Auto-filling missing parameters from state
    """

    def __init__(self, tools: "ToolRegistry"):
        self.tools = tools

    def _auto_fill_params(
        self,
        action_name: str,
        action_input: dict[str, Any],
        state: "WorkingMemory | None",
    ) -> dict[str, Any]:
        """Auto-fill missing parameters from WorkingMemory state.

        This solves the problem where LLM calls tools without required params.
        We intelligently fill in the missing data from current state.

        Args:
            action_name: Name of the tool being called
            action_input: Original input from LLM
            state: Current WorkingMemory state

        Returns:
            Enriched action input with auto-filled params
        """
        if not state:
            return action_input

        enriched = dict(action_input)

        # design_experiment: auto-fill question from test_questions
        if action_name == "design_experiment":
            if not enriched.get("question") and state.test_questions:
                # Pick the first unanswered question, or first question if none answered
                unanswered = [
                    q for q in state.test_questions
                    if q.get("id") not in state.answered_questions
                ]
                question = unanswered[0] if unanswered else state.test_questions[0]
                enriched["question"] = question
                logger.info(f"Auto-filled question for design_experiment: {question.get('question', str(question))[:50]}...")

            # Also auto-fill hypothesis if not provided
            if not enriched.get("hypothesis") and state.structured_hypothesis:
                enriched["hypothesis"] = state.structured_hypothesis

            # Auto-fill evidence from search results
            if not enriched.get("evidence") and state.evidence_snippets:
                enriched["evidence"] = state.evidence_snippets[:5]

        # design_controls: auto-fill experiment from experiments list
        elif action_name == "design_controls":
            if not enriched.get("experiment") and state.experiments:
                # Use the most recently designed experiment
                experiment = state.experiments[-1]
                enriched["experiment"] = experiment
                logger.info(f"Auto-filled experiment for design_controls: {experiment.get('name', experiment.get('id', 'unknown'))}")

        # suggest_measurements: auto-fill experiment (singular) and hypothesis_vars
        elif action_name == "suggest_measurements":
            # Tool expects "experiment" (singular), not "experiments"
            if not enriched.get("experiment") and state.experiments:
                enriched["experiment"] = state.experiments[-1]  # Use latest experiment
                logger.info(f"Auto-filled experiment for suggest_measurements: {enriched['experiment'].get('name', 'unknown')}")

            # Extract hypothesis_vars from structured_hypothesis
            if not enriched.get("hypothesis_vars") and state.structured_hypothesis:
                hyp = state.structured_hypothesis
                hypothesis_vars = []
                if hyp.get("iv"):
                    hypothesis_vars.append(hyp["iv"])
                if hyp.get("dv"):
                    hypothesis_vars.append(hyp["dv"])
                if hyp.get("mediators"):
                    hypothesis_vars.extend(hyp["mediators"])
                if hyp.get("moderators"):
                    hypothesis_vars.extend(hyp["moderators"])
                if hypothesis_vars:
                    enriched["hypothesis_vars"] = hypothesis_vars
                    logger.info(f"Auto-filled hypothesis_vars for suggest_measurements: {hypothesis_vars[:3]}...")

        # validate_controls: auto-fill experiment (singular) and controls
        elif action_name == "validate_controls":
            # Tool expects "experiment" (singular)
            if not enriched.get("experiment") and state.experiments:
                enriched["experiment"] = state.experiments[-1]
                logger.info(f"Auto-filled experiment for validate_controls")

            # Flatten controls dict to list for the latest experiment
            if not enriched.get("controls") and state.controls:
                # state.controls is dict[exp_id, list[controls]]
                # Get controls for latest experiment or flatten all
                if state.experiments:
                    exp_id = state.experiments[-1].get("id", "default")
                    if exp_id in state.controls:
                        enriched["controls"] = state.controls[exp_id]
                    else:
                        # Flatten all controls
                        all_controls = []
                        for ctrls in state.controls.values():
                            all_controls.extend(ctrls)
                        enriched["controls"] = all_controls
                    logger.info(f"Auto-filled controls for validate_controls: {len(enriched.get('controls', []))} controls")

        # validate_coverage: auto-fill measurements and hypothesis
        elif action_name == "validate_coverage":
            if not enriched.get("measurements") and state.measurements:
                enriched["measurements"] = state.measurements

            if not enriched.get("hypothesis") and state.structured_hypothesis:
                enriched["hypothesis"] = state.structured_hypothesis

        # synthesize_plan: auto-fill experiments, evidence, metadata
        elif action_name == "synthesize_plan":
            if not enriched.get("experiments") and state.experiments:
                enriched["experiments"] = state.experiments
                logger.info(f"Auto-filled experiments for synthesize_plan: {len(state.experiments)} experiments")

            if not enriched.get("evidence") and state.evidence_snippets:
                enriched["evidence"] = state.evidence_snippets

            if not enriched.get("metadata"):
                enriched["metadata"] = {
                    "hypothesis": state.structured_hypothesis or {"raw": state.original_hypothesis},
                    "constraints": state.constraints,
                    "test_questions": state.test_questions,
                }

        # generate_plan_b: auto-fill plan_a
        elif action_name == "generate_plan_b":
            if not enriched.get("plan_a") and state.plan_a:
                enriched["plan_a"] = {"plan": state.plan_a}
                logger.info("Auto-filled plan_a for generate_plan_b")

            if not enriched.get("constraints") and state.constraints:
                enriched["constraints"] = state.constraints

        # critique_design: auto-fill design (combines experiments, controls, measurements)
        elif action_name == "critique_design":
            if not enriched.get("design") and state.experiments:
                # Create a complete design dict from state
                enriched["design"] = {
                    "experiments": state.experiments,
                    "controls": state.controls,
                    "measurements": state.measurements,
                    "hypothesis": state.structured_hypothesis,
                }
                logger.info(f"Auto-filled design for critique_design: {len(state.experiments)} experiments")

        # decompose_questions: auto-fill structured_hypothesis
        elif action_name == "decompose_questions":
            # Tool expects "structured_hypothesis", NOT "hypothesis"
            if not enriched.get("structured_hypothesis") and state.structured_hypothesis:
                enriched["structured_hypothesis"] = state.structured_hypothesis
                logger.info("Auto-filled structured_hypothesis for decompose_questions")

        return enriched

    async def execute(
        self,
        action: Action,
        state: "WorkingMemory | None" = None,
    ) -> Observation:
        """Execute an action and return observation.

        Args:
            action: The action to execute
            state: Optional WorkingMemory for auto-filling missing params

        Returns:
            Observation with results or error
        """
        # Handle terminal action
        if action.name == "FINISH":
            logger.info("Agent reached FINISH action")
            return Observation(
                success=True,
                result=action.input.get("final_result", "Plan generation complete"),
                is_terminal=True,
            )

        # Get tool from registry
        tool = self.tools.get(action.name)
        if not tool:
            logger.error(f"Unknown tool: {action.name}")
            return Observation(
                success=False,
                error=f"Unknown tool: {action.name}. Available tools: {list(self.tools.list_tools())}",
            )

        # Execute tool
        start_time = time.time()
        try:
            # Auto-fill missing parameters from state
            enriched_input = self._auto_fill_params(action.name, action.input, state)

            # 도구의 허용된 파라미터만 필터링
            allowed_params = {p.name for p in tool._get_parameters()}
            filtered_input = {
                k: v for k, v in enriched_input.items()
                if k in allowed_params
            }

            # 무시된 파라미터 로깅
            ignored_params = set(enriched_input.keys()) - allowed_params
            if ignored_params:
                logger.warning(
                    f"Tool {action.name}: ignoring unexpected parameters: {ignored_params}"
                )

            # 로그에 auto-fill 여부 표시
            auto_filled = set(enriched_input.keys()) - set(action.input.keys())
            if auto_filled:
                logger.info(f"Executing tool: {action.name} with input: {list(filtered_input.keys())} (auto-filled: {auto_filled})")
            else:
                logger.info(f"Executing tool: {action.name} with input: {list(filtered_input.keys())}")

            result = await tool.run(**filtered_input)
            duration_ms = int((time.time() - start_time) * 1000)

            logger.info(
                f"Tool {action.name} completed in {duration_ms}ms"
            )

            return Observation(
                success=True,
                result=result,
                duration_ms=duration_ms,
                cost=tool.cost,
            )

        except TypeError as e:
            # Missing or invalid parameters
            duration_ms = int((time.time() - start_time) * 1000)
            error_msg = f"Invalid parameters for {action.name}: {e}"
            logger.error(error_msg)
            return Observation(
                success=False,
                error=error_msg,
                duration_ms=duration_ms,
            )

        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            error_msg = f"Tool {action.name} failed: {type(e).__name__}: {e}"
            logger.error(error_msg, exc_info=True)
            return Observation(
                success=False,
                error=error_msg,
                duration_ms=duration_ms,
            )

    async def execute_with_retry(
        self,
        action: Action,
        state: "WorkingMemory | None" = None,
        max_retries: int = 2,
        delay_seconds: float = 1.0,
    ) -> Observation:
        """Execute action with automatic retry on failure.

        Args:
            action: The action to execute
            state: Optional WorkingMemory for auto-filling missing params
            max_retries: Maximum number of retry attempts
            delay_seconds: Delay between retries

        Returns:
            Observation from successful attempt or final failure
        """
        last_observation = None

        for attempt in range(max_retries + 1):
            observation = await self.execute(action, state)

            if observation.success:
                return observation

            last_observation = observation
            logger.warning(
                f"Attempt {attempt + 1}/{max_retries + 1} failed for {action.name}: "
                f"{observation.error}"
            )

            if attempt < max_retries:
                import asyncio
                await asyncio.sleep(delay_seconds)
                delay_seconds *= 2  # Exponential backoff

        return last_observation or Observation(
            success=False,
            error="All retry attempts exhausted",
        )
