"""Agent service for LangGraph-based task decomposition."""

import logging
import time
from dataclasses import dataclass
from typing import Any, Generator

from langgraph.graph.state import CompiledStateGraph

from .state import AgentState, create_initial_state, SubTask, TaskResult, ComplexityLevel
from app.schemas.chat import Reference

logger = logging.getLogger(__name__)


@dataclass
class AgentEvent:
    """Event emitted during agent execution."""

    event_type: str  # status, complexity, subtasks, task_start, task_complete, etc.
    data: dict[str, Any]


@dataclass
class AgentResult:
    """Final result from agent execution."""

    answer: str
    references: list[Reference]
    complexity: ComplexityLevel
    subtasks: list[SubTask]
    total_duration_ms: int
    agent_execution: dict[str, Any]  # For AnswerLog.evidence


class AgentService:
    """
    Singleton service for agent-based query processing.

    Uses LangGraph to orchestrate:
    1. Complexity analysis
    2. Task decomposition (for medium/complex queries)
    3. Tool routing
    4. Parallel/sequential task execution
    5. Evidence synthesis
    """

    _instance: "AgentService | None" = None
    _graph: CompiledStateGraph | None = None
    _graph_no_synth: CompiledStateGraph | None = None

    def __new__(cls) -> "AgentService":
        """Singleton pattern."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def _get_graph(self) -> CompiledStateGraph:
        """Lazy initialize the LangGraph (with synthesis)."""
        if self._graph is None:
            from .graph import compile_agent_graph

            logger.info("Compiling agent graph...")
            self._graph = compile_agent_graph()
            logger.info("Agent graph compiled successfully")
        return self._graph

    def _get_graph_no_synth(self) -> CompiledStateGraph:
        """Lazy initialize the LangGraph without synthesis (for streaming)."""
        if self._graph_no_synth is None:
            from .graph import compile_agent_graph_no_synth

            logger.info("Compiling agent graph (no synth) for streaming...")
            self._graph_no_synth = compile_agent_graph_no_synth()
            logger.info("Agent graph (no synth) compiled successfully")
        return self._graph_no_synth

    def execute(
        self,
        query: str,
        conversation_id: str | None = None,
    ) -> AgentResult:
        """
        Execute the agent workflow synchronously.

        Args:
            query: User's question
            conversation_id: Optional conversation context

        Returns:
            AgentResult with answer, references, and metadata
        """
        start_time = time.perf_counter()

        # Create initial state
        initial_state = create_initial_state(query, conversation_id)

        # Run the graph
        graph = self._get_graph()
        final_state = graph.invoke(initial_state)

        # Calculate total duration
        total_duration_ms = int((time.perf_counter() - start_time) * 1000)

        # Build agent execution metadata for AnswerLog
        agent_execution = self._build_execution_metadata(final_state, total_duration_ms)

        return AgentResult(
            answer=final_state.get("final_answer", ""),
            references=final_state.get("citations", []),
            complexity=final_state.get("complexity", ComplexityLevel.SIMPLE),
            subtasks=final_state.get("subtasks", []),
            total_duration_ms=total_duration_ms,
            agent_execution=agent_execution,
        )

    def execute_stream(
        self,
        query: str,
        conversation_id: str | None = None,
    ) -> Generator[AgentEvent, None, AgentResult]:
        """
        Execute the agent workflow with streaming events.

        Yields AgentEvent objects for real-time progress updates.
        Returns AgentResult when complete.

        Uses a graph WITHOUT synthesis, then manually streams synthesis
        for real-time token output.

        Args:
            query: User's question
            conversation_id: Optional conversation context

        Yields:
            AgentEvent for each step

        Returns:
            Final AgentResult
        """
        from .nodes.synthesizer import synthesize_answer_stream

        start_time = time.perf_counter()

        # Create initial state
        initial_state = create_initial_state(query, conversation_id)

        # Get the graph WITHOUT synthesis (for streaming)
        graph = self._get_graph_no_synth()

        # Stream execution with step callbacks
        yield AgentEvent(
            event_type="status",
            data={"step": "analyzing", "message": "쿼리 복잡도 분석 중..."},
        )

        # Execute graph and capture intermediate states
        final_state = initial_state
        for state_update in graph.stream(initial_state):
            # state_update is dict with node_name: state
            for node_name, state in state_update.items():
                final_state = {**final_state, **state}

                # Emit events based on which node just completed
                yield from self._emit_node_events(node_name, state)

        # Now manually stream synthesis with real-time tokens
        yield AgentEvent(
            event_type="status",
            data={"step": "synthesizing", "message": "결과 종합 중..."},
        )

        # Stream synthesis and collect final answer
        final_answer_parts = []
        all_citations = []

        synth_gen = synthesize_answer_stream(final_state)
        try:
            while True:
                token = next(synth_gen)
                final_answer_parts.append(token)
                yield AgentEvent(
                    event_type="token",
                    data={"token": token},
                )
        except StopIteration as e:
            # Generator returned the final state with citations
            synth_result = e.value
            if synth_result:
                all_citations = synth_result.get("citations", [])

        final_answer = "".join(final_answer_parts)

        # Update state with synthesis results
        final_state["final_answer"] = final_answer
        final_state["citations"] = all_citations

        # Calculate total duration
        total_duration_ms = int((time.perf_counter() - start_time) * 1000)

        # Build metadata
        agent_execution = self._build_execution_metadata(final_state, total_duration_ms)

        # Return final result
        return AgentResult(
            answer=final_answer,
            references=all_citations,
            complexity=final_state.get("complexity", ComplexityLevel.SIMPLE),
            subtasks=final_state.get("subtasks", []),
            total_duration_ms=total_duration_ms,
            agent_execution=agent_execution,
        )

    def _emit_node_events(
        self, node_name: str, state: dict[str, Any]
    ) -> Generator[AgentEvent, None, None]:
        """Emit events based on which node just completed."""
        logger.debug(f"Node completed: {node_name}, state keys: {list(state.keys())}")

        if node_name == "analyze_complexity":
            complexity = state.get("complexity", ComplexityLevel.SIMPLE)
            complexity_val = complexity.value if hasattr(complexity, "value") else str(complexity)
            yield AgentEvent(
                event_type="complexity",
                data={
                    "level": complexity_val,
                    "reasoning": state.get("complexity_reasoning", ""),
                },
            )
            if complexity != ComplexityLevel.SIMPLE:
                yield AgentEvent(
                    event_type="status",
                    data={"step": "decomposing", "message": "복잡한 쿼리 분해 중..."},
                )

        elif node_name == "decompose_tasks":
            subtasks = state.get("subtasks", [])
            yield AgentEvent(
                event_type="subtasks",
                data={
                    "tasks": [
                        {
                            "id": t.id,
                            "query": t.query,
                            "tool": t.tool.value if hasattr(t.tool, "value") else t.tool,
                            "depends_on": t.depends_on,
                        }
                        for t in subtasks
                    ]
                },
            )

        elif node_name == "execute_tasks" or node_name == "direct_rag":
            task_results = state.get("task_results", {})
            for task_id, result in task_results.items():
                yield AgentEvent(
                    event_type="task_complete",
                    data={
                        "task_id": task_id,
                        "summary": result.content[:200] + "..."
                        if len(result.content) > 200
                        else result.content,
                        "references_count": len(result.references),
                        "duration_ms": result.duration_ms,
                    },
                )

        # Note: "synthesize" node is handled separately in execute_stream()
        # with real-time token streaming from the LLM

    def _build_execution_metadata(
        self, state: dict[str, Any], total_duration_ms: int
    ) -> dict[str, Any]:
        """Build metadata for AnswerLog.evidence.agent_execution."""
        subtasks = state.get("subtasks", [])
        task_results = state.get("task_results", {})

        # Count parallel tasks (tasks with no dependencies)
        parallel_count = sum(1 for t in subtasks if not t.depends_on)

        return {
            "complexity": state.get("complexity", ComplexityLevel.SIMPLE).value
            if hasattr(state.get("complexity"), "value")
            else state.get("complexity", "simple"),
            "complexity_reasoning": state.get("complexity_reasoning", ""),
            "subtasks": [
                {
                    "id": t.id,
                    "query": t.query,
                    "tool": t.tool.value if hasattr(t.tool, "value") else t.tool,
                    "status": task_results.get(t.id, TaskResult(t.id, "")).error
                    and "failed"
                    or "completed",
                    "duration_ms": task_results.get(t.id, TaskResult(t.id, "")).duration_ms,
                    "references_count": len(
                        task_results.get(t.id, TaskResult(t.id, "")).references
                    ),
                }
                for t in subtasks
            ],
            "total_subtasks": len(subtasks),
            "parallel_tasks": parallel_count,
            "total_duration_ms": total_duration_ms,
        }


# Singleton instance
agent_service = AgentService()


def get_agent_service() -> AgentService:
    """Dependency injection function."""
    return agent_service
