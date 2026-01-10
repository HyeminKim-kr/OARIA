"""LangGraph graph builder for agent workflow."""

from langgraph.graph import StateGraph, END

from .state import AgentState, ComplexityLevel


def should_decompose(state: AgentState) -> str:
    """
    Routing function: decide whether to decompose or go directly to RAG.

    Returns:
        "decompose" for medium/complex queries
        "direct_rag" for simple queries
    """
    complexity = state.get("complexity", ComplexityLevel.SIMPLE)

    if complexity == ComplexityLevel.SIMPLE:
        return "direct_rag"
    else:
        return "decompose"


def build_agent_graph() -> StateGraph:
    """
    Build the agent workflow graph.

    Graph structure:
    ```
    START
      │
      ▼
    [analyze_complexity]
      │
      ├─ simple ──► [direct_rag] ──► [synthesize] ──► END
      │
      └─ medium/complex ──► [decompose_tasks]
                              │
                              ▼
                          [route_tools]
                              │
                              ▼
                          [execute_tasks]
                              │
                              ▼
                          [synthesize] ──► END
    ```
    """
    # Import nodes here to avoid circular imports
    from .nodes import (
        analyze_complexity,
        decompose_tasks,
        route_tools,
        execute_tasks,
        synthesize_answer,
    )
    from .nodes.executor import execute_direct_rag

    # Create the graph
    graph = StateGraph(AgentState)

    # Add nodes
    graph.add_node("analyze_complexity", analyze_complexity)
    graph.add_node("decompose_tasks", decompose_tasks)
    graph.add_node("route_tools", route_tools)
    graph.add_node("execute_tasks", execute_tasks)
    graph.add_node("direct_rag", execute_direct_rag)
    graph.add_node("synthesize", synthesize_answer)

    # Set entry point
    graph.set_entry_point("analyze_complexity")

    # Add conditional edge from complexity analyzer
    graph.add_conditional_edges(
        "analyze_complexity",
        should_decompose,
        {
            "decompose": "decompose_tasks",
            "direct_rag": "direct_rag",
        },
    )

    # Add edges for decomposition path
    graph.add_edge("decompose_tasks", "route_tools")
    graph.add_edge("route_tools", "execute_tasks")
    graph.add_edge("execute_tasks", "synthesize")

    # Add edge for direct RAG path
    graph.add_edge("direct_rag", "synthesize")

    # Add edge to END
    graph.add_edge("synthesize", END)

    return graph


def compile_agent_graph():
    """Compile the agent graph for execution."""
    graph = build_agent_graph()
    return graph.compile()


def build_agent_graph_no_synth() -> StateGraph:
    """
    Build the agent workflow graph WITHOUT synthesis node.

    Used for streaming mode where synthesis is done manually
    to enable real-time token streaming.
    """
    from .nodes import (
        analyze_complexity,
        decompose_tasks,
        route_tools,
        execute_tasks,
    )
    from .nodes.executor import execute_direct_rag

    graph = StateGraph(AgentState)

    # Add nodes (without synthesize)
    graph.add_node("analyze_complexity", analyze_complexity)
    graph.add_node("decompose_tasks", decompose_tasks)
    graph.add_node("route_tools", route_tools)
    graph.add_node("execute_tasks", execute_tasks)
    graph.add_node("direct_rag", execute_direct_rag)

    # Set entry point
    graph.set_entry_point("analyze_complexity")

    # Add conditional edge from complexity analyzer
    graph.add_conditional_edges(
        "analyze_complexity",
        should_decompose,
        {
            "decompose": "decompose_tasks",
            "direct_rag": "direct_rag",
        },
    )

    # Add edges for decomposition path (ends at execute_tasks)
    graph.add_edge("decompose_tasks", "route_tools")
    graph.add_edge("route_tools", "execute_tasks")
    graph.add_edge("execute_tasks", END)

    # Direct RAG also ends (no synthesis)
    graph.add_edge("direct_rag", END)

    return graph


def compile_agent_graph_no_synth():
    """Compile the agent graph without synthesis for streaming mode."""
    graph = build_agent_graph_no_synth()
    return graph.compile()
