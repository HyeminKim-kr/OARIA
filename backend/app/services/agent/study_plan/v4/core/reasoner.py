"""Reasoner component for v4 agent.

The Reasoner is responsible for:
1. Analyzing current state
2. Deciding the next action
3. Selecting appropriate tools
4. Generating alternative plans when needed
"""

import json
import logging
import re
from typing import TYPE_CHECKING

from langchain_openai import ChatOpenAI

from app.services.agent.study_plan.v4.core.types import Action
from app.services.agent.study_plan.v4.core.state import (
    WorkingMemory,
    ExecutionHistory,
)
from app.services.agent.study_plan.v4.prompts.reasoning import (
    TOOL_SELECTION_PROMPT,
    ALTERNATIVE_SELECTION_PROMPT,
)

if TYPE_CHECKING:
    from app.services.agent.study_plan.v4.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)


class Reasoner:
    """LLM-based reasoner for deciding agent actions.

    Uses ReAct-style prompting to:
    - Think about current state
    - Decide next action
    - Handle failures with alternatives
    """

    def __init__(
        self,
        llm: ChatOpenAI,
        tools: "ToolRegistry",
        temperature: float = 0.1,
    ):
        self.llm = llm
        self.tools = tools
        self.temperature = temperature

    async def reason(
        self,
        state: WorkingMemory,
        history: ExecutionHistory,
        goal: str,
    ) -> tuple[str, Action]:
        """Decide the next action based on current state.

        Args:
            state: Current working memory
            history: Execution history
            goal: The goal to achieve

        Returns:
            Tuple of (thought, action)
        """
        # Build context for LLM
        context = self._build_context(state, history, goal)

        # Format prompt
        prompt = TOOL_SELECTION_PROMPT.format(**context)

        # Call LLM
        response = await self.llm.ainvoke(prompt)
        content = response.content

        logger.debug(f"Reasoner response: {content[:500]}...")

        # Parse response
        parsed = self._parse_response(content)

        # Check if we should avoid this action (failed too many times)
        if history.should_avoid(parsed["action"]):
            logger.warning(
                f"Action {parsed['action']} has failed multiple times, seeking alternative"
            )
            parsed = await self._get_alternative(parsed, state, history)

        # Check for loops
        if history.detect_loop():
            logger.warning("Loop detected in agent execution, forcing alternative")
            parsed = await self._get_alternative(parsed, state, history)

        action = Action(
            name=parsed["action"],
            input=parsed.get("action_input", {}),
            confidence=parsed.get("confidence", 0.5),
            alternative=parsed.get("alternative"),
        )

        return parsed["thought"], action

    def _build_context(
        self,
        state: WorkingMemory,
        history: ExecutionHistory,
        goal: str,
    ) -> dict:
        """Build context dictionary for prompt."""
        return {
            "goal": goal,
            "hypothesis": state.original_hypothesis,
            "state_summary": state.get_summary(),
            "tool_descriptions": self.tools.get_descriptions_for_llm(),
            "recent_actions": history.get_context_for_llm(),
        }

    def _parse_response(self, content: str) -> dict:
        """Parse LLM response to extract action decision.

        Handles various JSON formats and edge cases.
        """
        # Try to extract JSON from response
        json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", content, re.DOTALL)

        if json_match:
            json_str = json_match.group(1)
        else:
            # Try to find raw JSON
            json_match = re.search(r"\{[^{}]*\}", content, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
            else:
                # Fallback: ask user for help
                logger.error(f"Could not parse response: {content}")
                return {
                    "thought": "Failed to parse LLM response, requesting user help",
                    "action": "ask_user",
                    "action_input": {
                        "question": "The agent encountered an issue. Please provide guidance.",
                        "options": ["Continue with default behavior", "Cancel"],
                    },
                }

        try:
            parsed = json.loads(json_str)

            # Validate required fields
            if "action" not in parsed:
                parsed["action"] = "ask_user"
                parsed["action_input"] = {
                    "question": "Unable to determine next action. Please provide guidance."
                }

            if "thought" not in parsed:
                parsed["thought"] = "No explicit reasoning provided"

            return parsed

        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error: {e}, content: {json_str}")
            return {
                "thought": f"JSON parsing failed: {e}",
                "action": "ask_user",
                "action_input": {
                    "question": "The agent encountered a parsing issue. Please provide guidance."
                },
            }

    async def _get_alternative(
        self,
        original: dict,
        state: WorkingMemory,
        history: ExecutionHistory,
    ) -> dict:
        """Get alternative action when original has failed too many times."""
        # First check if alternative was already provided
        if original.get("alternative"):
            return {
                **original,
                "action": original["alternative"],
                "thought": f"Original action {original['action']} failed, trying alternative: {original['alternative']}",
            }

        # Ask LLM for alternative
        tried_actions = list(history.failed_actions.keys())

        prompt = ALTERNATIVE_SELECTION_PROMPT.format(
            original_action=original["action"],
            failure_reason="Action has failed multiple times",
            state_summary=state.get_summary(),
            tool_descriptions=self.tools.get_descriptions_for_llm(),
            tried_actions=", ".join(tried_actions) if tried_actions else "None",
        )

        response = await self.llm.ainvoke(prompt)
        parsed = self._parse_response(response.content)

        # Ensure we don't return the same action
        if parsed["action"] == original["action"]:
            # Default fallback: ask user
            return {
                "thought": "All automatic alternatives exhausted, requesting user input",
                "action": "ask_user",
                "action_input": {
                    "question": f"The agent tried {original['action']} multiple times without success. What should be done?",
                    "options": [
                        "Try a simpler approach",
                        "Skip this step",
                        "Provide manual input",
                    ],
                },
            }

        return parsed
