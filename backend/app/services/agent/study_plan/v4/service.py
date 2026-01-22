"""Study Plan Agent v4 service.

Main entry point for v4 agent functionality.
Provides both sync and streaming interfaces.
"""

import logging
import time
from typing import AsyncIterator

from langchain_openai import ChatOpenAI

from app.config import get_settings
from app.services.agent.study_plan.v4.core.loop import AgentLoop, AgentLoopEvent
from app.services.agent.study_plan.v4.core.types import AgentResult
from app.services.agent.study_plan.v4.core.goal_checker import GoalChecker
from app.services.agent.study_plan.v4.core.failure_handler import FailureHandler
from app.services.agent.study_plan.v4.tools.registry import (
    ToolRegistry,
    create_default_registry,
)
from app.services.agent.study_plan.v4.memory.long_term import LongTermMemory

logger = logging.getLogger(__name__)


class StudyPlanAgentV4:
    """Main v4 agent service.

    Features:
    - ReAct-based reasoning loop
    - Dynamic tool selection
    - Failure recovery
    - Long-term memory for learning
    """

    def __init__(
        self,
        llm: ChatOpenAI | None = None,
        tools: ToolRegistry | None = None,
        memory: LongTermMemory | None = None,
        max_iterations: int = 30,
    ):
        """Initialize v4 agent.

        Args:
            llm: Language model (uses default if not provided)
            tools: Tool registry (uses default if not provided)
            memory: Long-term memory (optional)
            max_iterations: Maximum loop iterations
        """
        settings = get_settings()

        self.llm = llm or ChatOpenAI(
            model=settings.openai_model,
            temperature=0.1,
        )

        self.tools = tools or create_default_registry()
        self.memory = memory or LongTermMemory()
        self.max_iterations = max_iterations

        # Create agent loop
        self.loop = AgentLoop(
            llm=self.llm,
            tools=self.tools,
            max_iterations=max_iterations,
            failure_handler=FailureHandler(self.llm),
            goal_checker=GoalChecker(),
        )

        logger.info(
            f"Initialized StudyPlanAgentV4 with {len(self.tools)} tools, "
            f"max_iterations={max_iterations}"
        )

    async def execute(
        self,
        hypothesis: str,
        research_context: str | None = None,
        constraints: list[str] | None = None,
        preferred_experiment_types: list[str] | None = None,
        user_id: str | None = None,
    ) -> AgentResult:
        """Execute agent synchronously.

        Args:
            hypothesis: Research hypothesis to test
            research_context: Optional research context
            constraints: Optional constraints
            preferred_experiment_types: Optional preferences
            user_id: Optional user ID for tracking

        Returns:
            AgentResult with plan and metadata
        """
        logger.info(f"Starting v4 agent execution for: {hypothesis[:100]}...")
        start_time = time.time()

        try:
            # Check for similar past runs
            similar_runs = await self.memory.recall_similar(hypothesis, top_k=3)
            if similar_runs:
                logger.info(f"Found {len(similar_runs)} similar past runs")

            # Run agent loop
            result = await self.loop.run(
                hypothesis=hypothesis,
                research_context=research_context,
                constraints=constraints,
                preferred_experiment_types=preferred_experiment_types,
            )

            # Store result in long-term memory
            await self.memory.store_run(
                run_id=result.execution_trace[0]["step_number"] if result.execution_trace else "unknown",
                hypothesis=hypothesis,
                result={
                    "success": result.success,
                    "quality_score": result.quality_score,
                    "experiment_count": result.experiment_count,
                    "iteration_count": result.iteration_count,
                },
                metadata={
                    "user_id": user_id,
                    "research_context": research_context,
                },
            )

            duration = time.time() - start_time
            logger.info(
                f"v4 agent completed in {duration:.2f}s, "
                f"success={result.success}, quality={result.quality_score:.0%}"
            )

            return result

        except Exception as e:
            logger.error(f"v4 agent error: {e}", exc_info=True)
            return AgentResult(
                success=False,
                error=str(e),
                total_duration_ms=int((time.time() - start_time) * 1000),
            )

    async def execute_stream(
        self,
        hypothesis: str,
        research_context: str | None = None,
        constraints: list[str] | None = None,
        preferred_experiment_types: list[str] | None = None,
        user_id: str | None = None,
    ) -> AsyncIterator[tuple[str, dict]]:
        """Execute agent with streaming events.

        Args:
            hypothesis: Research hypothesis
            research_context: Optional context
            constraints: Optional constraints
            preferred_experiment_types: Optional preferences
            user_id: Optional user ID

        Yields:
            Tuple of (event_type, event_data)
        """
        logger.info(f"Starting v4 agent stream for: {hypothesis[:100]}...")

        try:
            async for event_type, event_data in self.loop.run_stream(
                hypothesis=hypothesis,
                research_context=research_context,
                constraints=constraints,
                preferred_experiment_types=preferred_experiment_types,
            ):
                yield (event_type, event_data)

                # Store result when completed
                if event_type == AgentLoopEvent.COMPLETED:
                    await self.memory.store_run(
                        run_id=event_data.get("run_id", "unknown"),
                        hypothesis=hypothesis,
                        result={
                            "success": event_data.get("success", False),
                            "quality_score": event_data.get("quality_score", 0),
                            "experiment_count": event_data.get("experiment_count", 0),
                            "iteration_count": event_data.get("iteration_count", 0),
                        },
                        metadata={"user_id": user_id},
                    )

        except Exception as e:
            logger.error(f"v4 agent stream error: {e}", exc_info=True)
            yield (AgentLoopEvent.ERROR, {"error": str(e)})

    def get_tool_summary(self) -> dict:
        """Get summary of available tools."""
        return self.tools.get_tool_summary()


# Singleton instance for use in API
_agent_instance: StudyPlanAgentV4 | None = None


def get_study_plan_agent_v4() -> StudyPlanAgentV4:
    """Get or create singleton v4 agent instance."""
    global _agent_instance
    if _agent_instance is None:
        _agent_instance = StudyPlanAgentV4()
    return _agent_instance
