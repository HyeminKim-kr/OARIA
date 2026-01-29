"""Execute node for LangGraph agent.

This node wraps the existing Executor component to run
the action decided by the Reasoner.
"""

import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from app.services.agent.study_plan.v4.langgraph.state import StudyPlanState
from app.services.agent.study_plan.v4.core.types import Action
from app.services.agent.study_plan.v4.core.state_view import StateView

if TYPE_CHECKING:
    from app.services.agent.study_plan.v4.core.executor import Executor

logger = logging.getLogger(__name__)


def create_execute_node(executor: "Executor"):
    """Factory function to create an execute node with injected dependencies.

    Args:
        executor: The Executor instance to use for action execution

    Returns:
        An async function that can be used as a LangGraph node
    """

    async def execute_node(state: StudyPlanState) -> dict:
        """Execute the decided action.

        Wraps the Executor component, converting between
        LangGraph state and the expected interfaces.

        Args:
            state: Current LangGraph state with action to execute

        Returns:
            Updated state with execution results
        """
        iteration = state.get("iteration_count", 0)
        action_name = state.get("current_action", "")
        action_input = state.get("current_action_input", {})

        logger.info(f"=== Execute Node (iteration {iteration}) ===")
        logger.info(f"Executing action: {action_name}")

        # Create Action object
        action = Action(
            name=action_name,
            input=action_input,
            confidence=state.get("current_confidence", 0.5),
        )

        # Create StateView (read-only view of state) for auto-fill functionality
        state_view = StateView(state)

        # Execute the action
        observation = await executor.execute(action, state_view)

        logger.info(f"Execution result: success={observation.success}")
        if not observation.success:
            logger.warning(f"Execution error: {observation.error}")

        # Create execution event for streaming
        # Extract sources for search actions (Perplexity-style cards)
        sources = _extract_sources(action_name, observation.result) if observation.success else None
        friendly_summary = _get_friendly_summary(action_name, observation.result, observation.success)
        # Extract detailed result for UI display
        result_details = _extract_result_details(action_name, observation.result) if observation.success else None

        execution_event = (
            "observation",
            {
                "iteration": iteration,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "action": action_name,
                "success": observation.success,
                "result": _truncate_result(observation.result) if observation.success else None,
                "error": observation.error,
                "duration_ms": observation.duration_ms,
                "is_terminal": observation.is_terminal,
                # New fields for Sources cards
                "sources": sources,
                "summary": friendly_summary,
                # Detailed result for UI (hypothesis, questions, experiments, etc.)
                "details": result_details,
            },
        )

        # Get existing events and add new one
        pending_events = list(state.get("pending_events") or [])
        pending_events.append(execution_event)

        # Update consecutive failures
        consecutive_failures = state.get("consecutive_failures", 0)
        if observation.success:
            consecutive_failures = 0
        else:
            consecutive_failures += 1

        # Add to execution trace
        trace_entry = {
            "iteration": iteration,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "action": action_name,
            "action_input": action_input,
            "success": observation.success,
            "error": observation.error,
            "duration_ms": observation.duration_ms,
        }
        execution_trace = list(state.get("execution_trace") or [])
        execution_trace.append(trace_entry)

        return {
            "action_success": observation.success,
            "action_error": observation.error,
            "action_result": observation.result,
            "is_terminal": observation.is_terminal,
            "consecutive_failures": consecutive_failures,
            "pending_events": pending_events,
            "execution_trace": execution_trace,
            "last_duration_ms": observation.duration_ms,
        }

    return execute_node


def _truncate_result(result, max_length: int = 500) -> str:
    """Truncate result for logging/events."""
    if result is None:
        return None

    result_str = str(result)
    if len(result_str) > max_length:
        return result_str[:max_length] + "..."
    return result_str


def _extract_sources(action_name: str, result: Any) -> list[dict] | None:
    """Extract sources from search results for Perplexity-style cards.

    Args:
        action_name: Name of the executed action
        result: The action result

    Returns:
        List of source objects or None if not a search action
    """
    # Only extract sources for search actions
    search_actions = {"search_rag", "search_epmc", "search_web"}
    if action_name not in search_actions:
        return None

    if not isinstance(result, dict):
        return None

    # Determine search source from action name
    source_type_map = {
        "search_rag": "rag",
        "search_epmc": "epmc",
        "search_web": "web",
    }
    search_source = source_type_map.get(action_name, "unknown")

    sources = []
    papers = result.get("papers", [])

    for i, paper in enumerate(papers[:10]):  # Limit to 10 sources
        # Get URL with fallback logic
        url = paper.get("url")
        doi = paper.get("doi", "")
        pmcid = paper.get("pmcid", "")
        pmid = paper.get("pmid", paper.get("paper_id", ""))

        if not url:
            # Fallback: construct URL from identifiers
            if doi:
                url = f"https://doi.org/{doi}"
            elif pmcid:
                url = f"https://europepmc.org/article/PMC/{pmcid}"
            elif pmid:
                url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"

        # Create title for citation
        title = paper.get("title", "Unknown Title")
        title_short = title[:50] + "..." if len(title) > 50 else title

        source = {
            "id": i + 1,
            "type": "paper",
            "title": title,
            "journal": paper.get("journal", ""),
            "year": paper.get("year"),
            "authors": paper.get("authors", [])[:3],  # First 3 authors
            "relevance": paper.get("score", paper.get("relevance_score", 0)),
            "pmid": pmid,
            "pmcid": pmcid,
            "doi": doi,
            # New unified fields
            "url": url,
            "source": paper.get("source", search_source),  # rag, epmc, or web
            "citation_text": paper.get("citation_text", title_short),
            "markdown_link": paper.get("markdown_link") or (f"[{title_short}]({url})" if url else title_short),
        }
        sources.append(source)

    # Also extract any snippets as evidence sources
    snippets = result.get("snippets", [])[:5]  # Limit to 5 snippets
    for i, snippet in enumerate(snippets):
        if snippet.get("text"):
            source = {
                "id": len(sources) + 1,
                "type": "snippet",
                "text": snippet.get("text", "")[:300],  # Truncate snippet
                "section": snippet.get("section", ""),
                "paper_id": snippet.get("paper_id", ""),
                "relevance": snippet.get("relevance_score", 0),
                "source": search_source,
            }
            sources.append(source)

    return sources if sources else None


def _get_friendly_summary(action_name: str, result: Any, success: bool) -> str:
    """Generate a friendly, user-facing summary of the action result.

    Args:
        action_name: Name of the executed action
        result: The action result
        success: Whether the action succeeded

    Returns:
        Human-friendly summary string
    """
    if not success:
        return f"{_get_action_label(action_name)} 중 문제가 발생했어요. 다시 시도해볼게요."

    if not isinstance(result, dict):
        return f"{_get_action_label(action_name)}을(를) 완료했어요."

    # Generate action-specific summaries
    if action_name in {"search_rag", "search_epmc", "search_web"}:
        paper_count = len(result.get("papers", []))
        coverage = result.get("coverage", 0)
        if paper_count > 0:
            return f"관련 논문 {paper_count}편을 찾았어요! 관련도 {coverage * 100:.0f}%"
        return "검색 결과가 없어요. 다른 키워드로 시도해볼게요."

    elif action_name == "parse_hypothesis":
        iv = result.get("iv", result.get("independent_variable", ""))
        dv = result.get("dv", result.get("dependent_variable", ""))
        if iv and dv:
            return f"가설을 분석했어요: '{iv}'가 '{dv}'에 미치는 영향"
        return "가설 구조를 파악했어요."

    elif action_name == "decompose_questions":
        q_count = len(result.get("questions", result.get("test_questions", [])))
        return f"검증이 필요한 질문 {q_count}개를 도출했어요."

    elif action_name == "design_experiment":
        # Result is wrapped in "experiment" key
        exp = result.get("experiment", result)
        exp_type = exp.get("approach", exp.get("type", ""))
        name = exp.get("name", "")
        if name:
            return f"'{name}' 실험을 설계했어요. ({exp_type})"
        return "실험 설계를 완료했어요."

    elif action_name == "design_controls":
        ctrl_count = len(result.get("controls", []))
        return f"대조군 {ctrl_count}개를 설계했어요."

    elif action_name == "suggest_measurements":
        m_count = len(result.get("measurements", []))
        return f"측정 항목 {m_count}개를 도출했어요."

    elif action_name == "critique_design":
        score = result.get("score", 0)
        issues = len(result.get("issues", []))
        if score >= 0.8:
            return f"설계 품질 {score * 100:.0f}점! 좋은 설계예요."
        return f"설계 품질 {score * 100:.0f}점, 개선점 {issues}개를 발견했어요."

    elif action_name == "synthesize_plan":
        return "실험 계획서(Plan A)를 작성했어요!"

    elif action_name == "generate_plan_b":
        return "대안 계획(Plan B)도 준비했어요!"

    # Default summary
    return f"{_get_action_label(action_name)}을(를) 완료했어요."


def _get_action_label(action_name: str) -> str:
    """Get human-friendly label for an action."""
    labels = {
        "search_rag": "논문 검색",
        "search_epmc": "Europe PMC 검색",
        "search_web": "웹 검색",
        "parse_hypothesis": "가설 분석",
        "decompose_questions": "질문 분해",
        "design_experiment": "실험 설계",
        "design_controls": "대조군 설계",
        "suggest_measurements": "측정 항목 도출",
        "validate_controls": "대조군 검증",
        "validate_coverage": "커버리지 검증",
        "critique_design": "설계 검토",
        "synthesize_plan": "계획서 작성",
        "generate_plan_b": "대안 계획 작성",
        "analyze_methodology": "방법론 분석",
    }
    return labels.get(action_name, action_name)


def _extract_result_details(action_name: str, result: Any) -> dict | None:
    """Extract detailed result information for UI display.

    This provides structured data that can be rendered in the ExtendedThinkingPanel.

    Args:
        action_name: Name of the executed action
        result: The action result

    Returns:
        Dictionary with detailed result info, or None
    """
    if not isinstance(result, dict):
        return None

    details = {"type": action_name}

    if action_name == "parse_hypothesis":
        # Extract structured hypothesis components
        details["hypothesis"] = {
            "iv": result.get("iv", result.get("independent_variable", "")),
            "dv": result.get("dv", result.get("dependent_variable", "")),
            "mechanism": result.get("mechanism", ""),
            "mediators": result.get("mediators", []),
            "moderators": result.get("moderators", []),
            "confidence": result.get("confidence", 0),
        }

    elif action_name == "decompose_questions":
        # Extract test questions
        questions = result.get("questions", result.get("test_questions", []))
        details["questions"] = [
            {
                "id": q.get("id", f"q{i+1}"),
                "question": q.get("question", q.get("text", str(q))),
                "category": q.get("category", "unknown"),
                "priority": q.get("priority", "medium"),
            }
            for i, q in enumerate(questions[:10])  # Limit to 10
        ]
        details["count"] = len(questions)

    elif action_name in {"search_rag", "search_epmc", "search_web"}:
        # Determine search source from action name
        source_type_map = {
            "search_rag": "rag",
            "search_epmc": "epmc",
            "search_web": "web",
        }
        search_source = source_type_map.get(action_name, "unknown")

        # Extract paper/evidence info
        papers = result.get("papers", result.get("results", []))
        details_papers = []
        for p in papers[:5]:  # Limit to 5
            # Get URL with fallback logic
            url = p.get("url")
            doi = p.get("doi", "")
            pmcid = p.get("pmcid", "")
            pmid = p.get("pmid", p.get("paper_id", ""))

            if not url:
                if doi:
                    url = f"https://doi.org/{doi}"
                elif pmcid:
                    url = f"https://europepmc.org/article/PMC/{pmcid}"
                elif pmid:
                    url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"

            title = p.get("title", "")[:100]
            details_papers.append({
                "title": title,
                "authors": p.get("authors", [])[:3],
                "year": p.get("year"),
                "journal": p.get("journal", ""),
                "relevance": p.get("score", p.get("relevance_score", 0)),
                # New unified fields
                "url": url,
                "source": p.get("source", search_source),
                "doi": doi,
                "pmcid": pmcid,
                "pmid": pmid,
            })
        details["papers"] = details_papers
        details["total_count"] = len(papers)
        details["coverage"] = result.get("coverage", 0)
        details["search_source"] = search_source

    elif action_name == "design_experiment":
        # Extract experiment design - result is wrapped in "experiment" key
        exp = result.get("experiment", result)
        details["experiment"] = {
            "name": exp.get("name", ""),
            "type": exp.get("approach", exp.get("type", "")),  # Tool uses "approach"
            "objective": exp.get("objective", ""),
            "methods": exp.get("methods", [])[:3],
            "duration": exp.get("timeline", exp.get("duration", "")),  # Tool uses "timeline"
            "sample_size": exp.get("sample_size", ""),
        }

    elif action_name == "design_controls":
        # Extract control group designs
        controls = result.get("controls", [])
        details["controls"] = [
            {
                "type": c.get("type", ""),
                "name": c.get("name", ""),
                "purpose": c.get("purpose", ""),
            }
            for c in controls[:5]
        ]
        details["count"] = len(controls)

    elif action_name == "suggest_measurements":
        # Extract measurements
        measurements = result.get("measurements", [])
        details["measurements"] = [
            {
                "name": m.get("name", ""),
                "type": m.get("type", ""),  # primary/secondary
                "method": m.get("method", ""),
                "unit": m.get("unit", ""),
            }
            for m in measurements[:8]
        ]
        details["count"] = len(measurements)

    elif action_name == "critique_design":
        # Extract critique results
        details["critique"] = {
            "score": result.get("score", 0),
            "issues": result.get("issues", [])[:5],
            "suggestions": result.get("suggestions", [])[:5],
            "strengths": result.get("strengths", [])[:3],
        }

    elif action_name == "synthesize_plan":
        # Extract plan summary
        details["plan"] = {
            "has_plan": bool(result.get("plan", result.get("text", ""))),
            "sections": result.get("sections", []),
            "experiment_count": len(result.get("experiments", [])),
        }

    elif action_name == "generate_plan_b":
        # Extract Plan B summary
        details["plan_b"] = {
            "has_plan": bool(result.get("plan", result.get("text", ""))),
            "approach": result.get("approach", "pragmatic"),
            "cost_reduction": result.get("cost_reduction", ""),
        }

    return details if len(details) > 1 else None
