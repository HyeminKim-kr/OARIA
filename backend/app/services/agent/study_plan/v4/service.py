"""Study Plan Agent v4 service.

Main entry point for v4 agent functionality.
Provides both sync and streaming interfaces using LangGraph StateGraph.
"""

import json
import logging
import time
import uuid
from typing import AsyncIterator

from langchain_openai import ChatOpenAI

from app.config import get_settings
from app.services.agent.study_plan.v4.core.types import AgentResult
from app.services.agent.study_plan.v4.core.goal_checker import GoalChecker
from app.services.agent.study_plan.v4.core.failure_handler import FailureHandler
from app.services.agent.study_plan.v4.core.reasoner import Reasoner
from app.services.agent.study_plan.v4.core.executor import Executor
from app.services.agent.study_plan.v4.tools.registry import (
    ToolRegistry,
    create_default_registry,
)
from app.services.agent.study_plan.v4.memory.long_term import LongTermMemory

# LangGraph imports
from app.services.agent.study_plan.v4.langgraph import (
    compile_graph,
    create_initial_state,
)
from app.services.agent.study_plan.v4.langgraph.streaming import (
    stream_with_events,
    SSEEventType,
)
from app.services.agent.study_plan.v4.langgraph.checkpointer import (
    create_checkpointer,
    create_thread_config,
    get_default_checkpointer_config,
)

logger = logging.getLogger(__name__)


class StudyPlanAgentV4:
    """Main v4 agent service using LangGraph StateGraph.

    Features:
    - LangGraph StateGraph for execution flow
    - Dynamic tool selection
    - Failure recovery
    - Long-term memory for learning
    - Extended Thinking UI support
    """

    def __init__(
        self,
        llm: ChatOpenAI | None = None,
        tools: ToolRegistry | None = None,
        memory: LongTermMemory | None = None,
        max_iterations: int = 30,
        checkpointer_type: str = "memory",
    ):
        """Initialize v4 agent.

        Args:
            llm: Language model (uses default if not provided)
            tools: Tool registry (uses default if not provided)
            memory: Long-term memory (optional)
            max_iterations: Maximum loop iterations
            checkpointer_type: Checkpointer type ("memory", "postgres", "none")
        """
        settings = get_settings()

        self.llm = llm or ChatOpenAI(
            model=settings.openai_model,
            temperature=0.1,
        )

        self.tools = tools or create_default_registry()
        self.memory = memory or LongTermMemory()
        self.max_iterations = max_iterations

        # Create core components
        self.goal_checker = GoalChecker()
        self.failure_handler = FailureHandler(self.llm)
        self.reasoner = Reasoner(llm=self.llm, tools=self.tools)
        self.executor = Executor(tools=self.tools)

        # Create checkpointer
        checkpointer_config = get_default_checkpointer_config()
        checkpointer_config["checkpointer_type"] = checkpointer_type
        self.checkpointer = create_checkpointer(**checkpointer_config)

        # Compile graph
        self.graph = compile_graph(
            reasoner=self.reasoner,
            executor=self.executor,
            goal_checker=self.goal_checker,
            checkpointer=self.checkpointer,
        )

        logger.info(
            f"Initialized StudyPlanAgentV4 with {len(self.tools)} tools, "
            f"max_iterations={max_iterations}, checkpointer={checkpointer_type}"
        )

    async def execute(
        self,
        hypothesis: str,
        research_context: str | None = None,
        constraints: list[str] | None = None,
        preferred_experiment_types: list[str] | None = None,
        user_id: str | None = None,
        thread_id: str | None = None,
    ) -> AgentResult:
        """Execute agent synchronously.

        Args:
            hypothesis: Research hypothesis to test
            research_context: Optional research context
            constraints: Optional constraints
            preferred_experiment_types: Optional preferences
            user_id: Optional user ID for tracking
            thread_id: Optional thread ID for checkpointing

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

            # Create initial state
            initial_state = create_initial_state(
                hypothesis=hypothesis,
                goal="Create a comprehensive study plan based on the hypothesis",
                research_context=research_context,
                constraints=constraints or [],
                preferred_experiment_types=preferred_experiment_types or [],
            )

            # Create thread config
            thread_id = thread_id or str(uuid.uuid4())
            config = create_thread_config(thread_id)

            # Run graph to completion
            final_state = None
            async for event in self.graph.astream(initial_state, config=config):
                for node_name, output in event.items():
                    final_state = {**initial_state, **output}

            if not final_state:
                return AgentResult(success=False, error="No state produced")

            # Store result in long-term memory
            await self.memory.store_run(
                run_id=thread_id,
                hypothesis=hypothesis,
                result={
                    "success": final_state.get("goal_achieved", False),
                    "quality_score": final_state.get("quality_score", 0),
                    "experiment_count": len(final_state.get("experiments") or []),
                    "iteration_count": final_state.get("iteration_count", 0),
                },
                metadata={
                    "user_id": user_id,
                    "research_context": research_context,
                },
            )

            duration = time.time() - start_time
            logger.info(
                f"v4 agent completed in {duration:.2f}s, "
                f"success={final_state.get('goal_achieved', False)}"
            )

            # Convert state to AgentResult
            return AgentResult(
                success=final_state.get("goal_achieved", False),
                final_plan=final_state.get("plan_a"),
                plan_a=final_state.get("plan_a"),
                plan_b=final_state.get("plan_b"),
                executive_summary=final_state.get("executive_summary"),
                experiment_count=len(final_state.get("experiments") or []),
                quality_score=final_state.get("quality_score", 0.0),
                iteration_count=final_state.get("iteration_count", 0),
                total_duration_ms=int((time.time() - start_time) * 1000),
                goals_achieved=final_state.get("goal_achieved", False),
                goals_missing=final_state.get("goals_missing") or [],
                experiments=final_state.get("experiments") or [],
                evidence_snippets=final_state.get("evidence_snippets") or [],
                measurements=final_state.get("measurements") or [],
                validation_results=final_state.get("validation_results") or [],
                execution_trace=final_state.get("execution_trace") or [],
            )

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
        thread_id: str | None = None,
    ) -> AsyncIterator[tuple[str, dict]]:
        """Execute agent with streaming events.

        Args:
            hypothesis: Research hypothesis
            research_context: Optional context
            constraints: Optional constraints
            preferred_experiment_types: Optional preferences
            user_id: Optional user ID
            thread_id: Optional thread ID for checkpointing

        Yields:
            Tuple of (event_type, event_data)
        """
        logger.info(f"Starting v4 agent stream for: {hypothesis[:100]}...")

        try:
            # Create initial state
            initial_state = create_initial_state(
                hypothesis=hypothesis,
                goal="Create a comprehensive study plan based on the hypothesis",
                research_context=research_context,
                constraints=constraints or [],
                preferred_experiment_types=preferred_experiment_types or [],
            )

            # Create thread config
            thread_id = thread_id or str(uuid.uuid4())
            config = create_thread_config(thread_id)

            # Stream events
            import sys
            async for sse_event in stream_with_events(self.graph, initial_state, config):
                # Parse SSE event
                lines = sse_event.strip().split("\n")
                event_type = None
                event_data = None

                for line in lines:
                    if line.startswith("event: "):
                        event_type = line[7:]
                    elif line.startswith("data: "):
                        event_data = json.loads(line[6:])

                if event_type and event_data:
                    print(f"[SERVICE] Yielding event: {event_type}", file=sys.stderr, flush=True)
                    yield (event_type, event_data)

                    # Store result when completed
                    if event_type == SSEEventType.COMPLETED:
                        print(f"[SERVICE] COMPLETED event matched!", file=sys.stderr, flush=True)
                        await self.memory.store_run(
                            run_id=thread_id,
                            hypothesis=hypothesis,
                            result={
                                "success": event_data.get("goal_achieved", False),
                                "quality_score": event_data.get("quality_score", 0),
                                "experiment_count": event_data.get("experiment_count", 0),
                                "iteration_count": event_data.get("iteration_count", 0),
                            },
                            metadata={"user_id": user_id},
                        )

        except Exception as e:
            logger.error(f"v4 agent stream error: {e}", exc_info=True)
            yield (SSEEventType.ERROR, {"error": str(e)})

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
