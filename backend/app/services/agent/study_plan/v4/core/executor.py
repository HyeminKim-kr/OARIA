"""Executor component for v4 agent.

The Executor is responsible for:
1. Running tools based on actions
2. Capturing results and errors
3. Tracking execution metrics
"""

import logging
import time
from typing import TYPE_CHECKING

from app.services.agent.study_plan.v4.core.types import Action, Observation

if TYPE_CHECKING:
    from app.services.agent.study_plan.v4.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)


class Executor:
    """Executes agent actions using the tool registry.

    Handles:
    - Tool invocation
    - Error capture
    - Timing and cost tracking
    """

    def __init__(self, tools: "ToolRegistry"):
        self.tools = tools

    async def execute(self, action: Action) -> Observation:
        """Execute an action and return observation.

        Args:
            action: The action to execute

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
            # 도구의 허용된 파라미터만 필터링
            allowed_params = {p.name for p in tool._get_parameters()}
            filtered_input = {
                k: v for k, v in action.input.items()
                if k in allowed_params
            }

            # 무시된 파라미터 로깅
            ignored_params = set(action.input.keys()) - allowed_params
            if ignored_params:
                logger.warning(
                    f"Tool {action.name}: ignoring unexpected parameters: {ignored_params}"
                )

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
        max_retries: int = 2,
        delay_seconds: float = 1.0,
    ) -> Observation:
        """Execute action with automatic retry on failure.

        Args:
            action: The action to execute
            max_retries: Maximum number of retry attempts
            delay_seconds: Delay between retries

        Returns:
            Observation from successful attempt or final failure
        """
        last_observation = None

        for attempt in range(max_retries + 1):
            observation = await self.execute(action)

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
