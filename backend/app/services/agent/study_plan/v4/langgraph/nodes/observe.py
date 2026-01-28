"""Observe node for LangGraph agent.

This node processes the execution result and updates the state
with extracted information (papers, experiments, etc.).
"""

import logging
from typing import Any

from app.services.agent.study_plan.v4.langgraph.state import StudyPlanState

logger = logging.getLogger(__name__)


def observe_node(state: StudyPlanState) -> dict:
    """Process execution result and extract state updates.

    Analyzes the action result and extracts relevant information
    to update the state (papers, experiments, etc.).

    Args:
        state: Current LangGraph state with execution result

    Returns:
        Updated state fields based on action type
    """
    # 맨 처음 실행 확인용 (이 로그가 안 보이면 observe_node 자체가 실행 안 되는 것)
    import sys
    print("\n" + "="*70, file=sys.stderr, flush=True)
    print("[OBSERVE NODE CALLED]", file=sys.stderr, flush=True)
    print("="*70 + "\n", file=sys.stderr, flush=True)

    iteration = state.get("iteration_count", 0)
    action_name = state.get("current_action", "")
    action_success = state.get("action_success", False)
    action_result = state.get("action_result")

    print(f"[OBSERVE] iteration={iteration}, action={action_name}, success={action_success}", file=sys.stderr, flush=True)
    print(f"[OBSERVE] action_result type: {type(action_result)}", file=sys.stderr, flush=True)
    print(f"[OBSERVE] action_result preview: {str(action_result)[:300] if action_result else 'None'}", file=sys.stderr, flush=True)
    print(f"[OBSERVE] experiments in state: {len(state.get('experiments', []))}", file=sys.stderr, flush=True)

    logger.info(f"=== Observe Node (iteration {iteration}) ===")
    logger.info(f"Processing result of: {action_name} (success={action_success})")
    logger.debug(f"action_result type: {type(action_result)}, value: {str(action_result)[:200] if action_result else 'None'}")

    # If action failed, track failure
    if not action_success:
        logger.warning(f"Action {action_name} failed. Error: {state.get('action_error')}")
        return {}

    # If no result, nothing to extract
    if action_result is None:
        logger.warning(f"Action {action_name} succeeded but returned None result")
        return {}

    # Extract updates based on action type
    updates = _extract_updates(action_name, action_result, state)

    if updates:
        logger.info(f"Extracted updates for {action_name}: {list(updates.keys())}")
        # Log specific important updates
        if "structured_hypothesis" in updates:
            logger.info(f"  - structured_hypothesis: IV={updates['structured_hypothesis'].get('iv')}, DV={updates['structured_hypothesis'].get('dv')}")
        if "test_questions" in updates:
            logger.info(f"  - test_questions: {len(updates['test_questions'])} questions")
        if "experiments" in updates:
            logger.info(f"  - experiments: {len(updates['experiments'])} new experiments")
            logger.info(f"  - RETURNING experiments update: {updates['experiments']}")
        if "plan_a" in updates:
            logger.info(f"  - plan_a: {len(updates['plan_a'])} chars")
        if "plan_b" in updates:
            logger.info(f"  - plan_b: {len(updates['plan_b'])} chars")
    else:
        logger.warning(f"No updates extracted from {action_name} result")

    import sys
    print(f"[OBSERVE] RETURNING updates: {list(updates.keys()) if updates else 'EMPTY'}", file=sys.stderr, flush=True)
    if "experiments" in updates:
        print(f"[OBSERVE] Experiments count in return: {len(updates['experiments'])}", file=sys.stderr, flush=True)
    print("="*70 + "\n", file=sys.stderr, flush=True)

    logger.info(f"observe_node RETURNING: {list(updates.keys()) if updates else 'EMPTY DICT'}")
    return updates


def _extract_updates(action_name: str, result: Any, state: StudyPlanState) -> dict:
    """Extract state updates from action result.

    Routes to specific extractors based on action type.
    Returns empty dict on failure (logged with details).
    """
    import sys

    extractors = {
        "parse_hypothesis": _extract_hypothesis,
        "decompose_questions": _extract_questions,
        "search_rag": _extract_papers,
        "search_epmc": _extract_papers,
        "search_web": _extract_papers,
        "analyze_methodology": _extract_methodology,
        "design_experiment": _extract_experiment,
        "design_controls": _extract_controls,
        "suggest_measurements": _extract_measurements,
        "validate_controls": _extract_validation,
        "validate_coverage": _extract_validation,
        "critique_design": _extract_critique,
        "synthesize_plan": _extract_plan_a,
        "generate_plan_b": _extract_plan_b,
    }

    extractor = extractors.get(action_name)
    if extractor:
        try:
            print(f"[Extractor:{action_name}] CALLING extractor...", file=sys.stderr, flush=True)
            updates = extractor(result, state)

            # Log extraction success/failure details (to stderr for visibility)
            if updates:
                print(
                    f"[Extractor:{action_name}] SUCCESS - "
                    f"Extracted fields: {list(updates.keys())}",
                    file=sys.stderr, flush=True
                )
                logger.info(f"[Extractor:{action_name}] SUCCESS - Extracted: {list(updates.keys())}")
            else:
                print(
                    f"[Extractor:{action_name}] EMPTY - "
                    f"Result type: {type(result).__name__}",
                    file=sys.stderr, flush=True
                )
                logger.warning(f"[Extractor:{action_name}] EMPTY - Result type: {type(result).__name__}")
            return updates

        except Exception as e:
            # Log detailed error for debugging
            print(
                f"[Extractor:{action_name}] FAILED - {type(e).__name__}: {e}",
                file=sys.stderr, flush=True
            )
            logger.error(
                f"[Extractor:{action_name}] FAILED - {type(e).__name__}: {e}",
                exc_info=True
            )
            return {}

    # Unknown action - no extractor found
    print(f"[Extractor:{action_name}] No extractor registered", file=sys.stderr, flush=True)
    return {}


def _extract_hypothesis(result: Any, state: StudyPlanState) -> dict:
    """Extract parsed hypothesis."""
    if isinstance(result, dict):
        return {
            "structured_hypothesis": result,
            "hypothesis_confidence": result.get("confidence", 0.5),
        }
    return {}


def _extract_questions(result: Any, state: StudyPlanState) -> dict:
    """Extract decomposed test questions."""
    import sys
    print(f"[OBSERVE] _extract_questions called", file=sys.stderr, flush=True)
    print(f"[OBSERVE] result type: {type(result)}", file=sys.stderr, flush=True)
    print(f"[OBSERVE] result: {str(result)[:500] if result else 'None'}", file=sys.stderr, flush=True)

    questions = []

    if isinstance(result, dict):
        questions = result.get("questions", result.get("test_questions", []))
        print(f"[OBSERVE] Extracted questions count: {len(questions)}", file=sys.stderr, flush=True)
    elif isinstance(result, list):
        questions = result
        print(f"[OBSERVE] Result was list, count: {len(questions)}", file=sys.stderr, flush=True)

    if questions:
        print(f"[OBSERVE] RETURNING test_questions: {len(questions)} items", file=sys.stderr, flush=True)
        return {"test_questions": questions}

    print(f"[OBSERVE] WARNING: No questions extracted, returning empty dict", file=sys.stderr, flush=True)
    return {}


def _extract_papers(result: Any, state: StudyPlanState) -> dict:
    """Extract papers and evidence from search results.

    Note: Uses Annotated[list, add] so returns items to append.
    """
    updates = {}

    if isinstance(result, dict):
        papers = result.get("papers", result.get("results", []))
        snippets = result.get("snippets", result.get("evidence", []))

        if papers:
            # These will be appended due to Annotated[list, add]
            updates["retrieved_papers"] = papers

        if snippets:
            updates["evidence_snippets"] = snippets

        # Update search coverage if provided
        if "coverage" in result:
            updates["search_coverage"] = result["coverage"]

        # Track search tier (uses add reducer, return single item)
        if "tier" in result:
            tier = result["tier"]
            current_tiers = state.get("search_tiers_used") or []
            if tier not in current_tiers:
                updates["search_tiers_used"] = [tier]  # Single item for add reducer

    elif isinstance(result, list):
        # Assume list of papers
        updates["retrieved_papers"] = result

    return updates


def _extract_methodology(result: Any, state: StudyPlanState) -> dict:
    """Extract methodology analysis."""
    if isinstance(result, dict):
        methods = result.get("methodologies", result.get("methods", []))
        if methods:
            return {"analyzed_methodologies": methods}
    return {}


def _extract_experiment(result: Any, state: StudyPlanState) -> dict:
    """Extract designed experiment and manually accumulate.

    NOTE: experiments field does NOT use add reducer anymore.
    We manually accumulate by reading current list and appending.
    """
    logger.info(f"_extract_experiment called with result type: {type(result)}")
    logger.info(f"_extract_experiment result keys: {result.keys() if isinstance(result, dict) else 'N/A'}")

    if isinstance(result, dict):
        # Unwrap if experiment is wrapped in "experiment" key
        exp = result.get("experiment", result)

        # Make a copy to avoid mutating the original
        exp = dict(exp)

        logger.info(f"After unwrap - exp keys: {exp.keys() if isinstance(exp, dict) else 'N/A'}")

        # Get current experiments from state and make a copy
        current_experiments = list(state.get('experiments') or [])
        logger.info(f"[OBSERVE] Current experiments in state BEFORE adding: {len(current_experiments)}")

        # Ensure it has an id
        if "id" not in exp:
            exp["id"] = f"exp_{len(current_experiments)}"

        # Append to the list
        current_experiments.append(exp)

        logger.info(f"[OBSERVE] Extracted experiment: id={exp.get('id')}, name={exp.get('name', 'N/A')[:50] if exp.get('name') else 'N/A'}")
        logger.info(f"[OBSERVE] Experiments count AFTER adding: {len(current_experiments)}")

        # Return the FULL accumulated list (no reducer, direct overwrite)
        return {"experiments": current_experiments}

    logger.warning(f"_extract_experiment: result is not a dict, returning empty")
    return {}


def _extract_controls(result: Any, state: StudyPlanState) -> dict:
    """Extract designed controls.

    NOTE: controls is a dict[str, list] - no add reducer.
    We must deep copy to avoid mutating state in-place.
    """
    controls_list = []

    if isinstance(result, dict):
        controls_list = result.get("controls", [])
        # Get the experiment this was designed for
        exp_id = result.get("experiment_id")
    elif isinstance(result, list):
        controls_list = result
        exp_id = None

    if controls_list:
        # Deep copy to avoid in-place mutation of state
        current_controls = {
            k: list(v) for k, v in (state.get("controls") or {}).items()
        }

        # Determine experiment ID
        if not exp_id:
            experiments = state.get("experiments") or []
            exp_id = experiments[-1].get("id", "default") if experiments else "default"

        # Add controls for this experiment (create new list, don't extend in-place)
        if exp_id in current_controls:
            current_controls[exp_id] = current_controls[exp_id] + list(controls_list)
        else:
            current_controls[exp_id] = list(controls_list)

        return {"controls": current_controls}

    return {}


def _extract_measurements(result: Any, state: StudyPlanState) -> dict:
    """Extract suggested measurements.

    Note: Uses Annotated[list, add] so returns items to append.
    """
    measurements = []

    if isinstance(result, dict):
        measurements = result.get("measurements", [])
    elif isinstance(result, list):
        measurements = result

    if measurements:
        return {"measurements": measurements}
    return {}


def _extract_validation(result: Any, state: StudyPlanState) -> dict:
    """Extract validation results.

    Note: Uses Annotated[list, add] so returns items to append.
    """
    if isinstance(result, dict):
        validation = {
            "type": result.get("validation_type", "unknown"),
            "passed": result.get("passed", result.get("valid", False)),
            "issues": result.get("issues", []),
            "score": result.get("score"),
        }
        return {"validation_results": [validation]}
    return {}


def _extract_critique(result: Any, state: StudyPlanState) -> dict:
    """Extract critique results.

    Note: critique_history uses Annotated[list, add] reducer.
    We return a single-item list [critique] which LangGraph will append.
    DO NOT return the full accumulated list - that causes nested lists!
    """
    if isinstance(result, dict):
        critique = {
            "score": result.get("score", 0),
            "issues": result.get("issues", []),
            "suggestions": result.get("suggestions", []),
            "iteration": state.get("iteration_count", 0),
        }

        return {
            "quality_score": result.get("score", state.get("quality_score", 0)),
            # Return single-item list for add reducer (NOT full history!)
            "critique_history": [critique],
        }
    return {}


def _extract_plan_a(result: Any, state: StudyPlanState) -> dict:
    """Extract synthesized Plan A."""
    if isinstance(result, dict):
        plan_text = result.get("plan", result.get("text", ""))
        summary = result.get("executive_summary", result.get("summary", ""))

        updates = {}
        if plan_text:
            updates["plan_a"] = plan_text
        if summary:
            updates["executive_summary"] = summary

        return updates

    elif isinstance(result, str):
        return {"plan_a": result}

    return {}


def _extract_plan_b(result: Any, state: StudyPlanState) -> dict:
    """Extract generated Plan B."""
    if isinstance(result, dict):
        # Tool returns "plan_b" key, but also check "plan" and "text" for compatibility
        plan_text = result.get("plan_b", result.get("plan", result.get("text", "")))
        if plan_text:
            return {"plan_b": plan_text}

    elif isinstance(result, str):
        return {"plan_b": result}

    return {}
