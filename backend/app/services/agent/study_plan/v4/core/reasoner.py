"""Reasoner component for v4 agent.

The Reasoner is responsible for:
1. Analyzing current state
2. Deciding the next action
3. Selecting appropriate tools
4. Generating alternative plans when needed

Uses OpenAI Function Calling for structured, validated tool invocation.
"""

import json
import logging
import re
from typing import TYPE_CHECKING

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

from app.services.agent.study_plan.v4.core.types import Action, TokenUsageDict
from app.services.agent.study_plan.v4.core.state import (
    WorkingMemory,
    ExecutionHistory,
)
from app.services.agent.study_plan.v4.core.phase_tracker import PhaseTracker
from app.services.agent.study_plan.v4.prompts.reasoning import (
    TOOL_SELECTION_PROMPT,
    ALTERNATIVE_SELECTION_PROMPT,
    FUNCTION_CALLING_SYSTEM_PROMPT,
    FUNCTION_CALLING_USER_PROMPT,
)

if TYPE_CHECKING:
    from app.services.agent.study_plan.v4.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)


class Reasoner:
    """LLM-based reasoner for deciding agent actions.

    Uses OpenAI Function Calling for structured, validated tool invocation.
    Falls back to ReAct-style prompting if function calling fails.
    """

    def __init__(
        self,
        llm: ChatOpenAI,
        tools: "ToolRegistry",
        temperature: float = 0.1,
        use_function_calling: bool = True,
    ):
        self.llm = llm
        self.tools = tools
        self.temperature = temperature
        self.use_function_calling = use_function_calling
        self._last_token_usage: TokenUsageDict | None = None

    @staticmethod
    def _extract_token_usage(response) -> TokenUsageDict | None:
        """Extract token usage from LLM response.

        Args:
            response: LangChain LLM response object

        Returns:
            TokenUsageDict with token counts, or None if not available
        """
        try:
            # Try response_metadata (newer LangChain)
            if hasattr(response, 'response_metadata'):
                metadata = response.response_metadata
                if 'token_usage' in metadata:
                    usage = metadata['token_usage']
                    return TokenUsageDict(
                        prompt_tokens=usage.get('prompt_tokens', 0),
                        completion_tokens=usage.get('completion_tokens', 0),
                        total_tokens=usage.get('total_tokens', 0),
                    )
                # OpenAI format
                if 'usage' in metadata:
                    usage = metadata['usage']
                    return TokenUsageDict(
                        prompt_tokens=usage.get('prompt_tokens', 0),
                        completion_tokens=usage.get('completion_tokens', 0),
                        total_tokens=usage.get('total_tokens', 0),
                    )

            # Try usage_metadata (LangChain ChatOpenAI)
            if hasattr(response, 'usage_metadata') and response.usage_metadata:
                usage = response.usage_metadata
                return TokenUsageDict(
                    prompt_tokens=getattr(usage, 'input_tokens', 0),
                    completion_tokens=getattr(usage, 'output_tokens', 0),
                    total_tokens=getattr(usage, 'total_tokens', 0),
                )

            return None
        except Exception as e:
            logger.debug(f"Failed to extract token usage: {e}")
            return None

    def get_last_token_usage(self) -> TokenUsageDict | None:
        """Get token usage from the last reason() call.

        Returns:
            TokenUsageDict or None if not available
        """
        return self._last_token_usage

    async def reason(
        self,
        state: WorkingMemory,
        history: ExecutionHistory,
        goal: str,
    ) -> tuple[str, Action]:
        """Decide the next action based on current state.

        Uses OpenAI Function Calling for structured tool invocation.
        Falls back to prompt-based reasoning if function calling fails.

        Args:
            state: Current working memory
            history: Execution history
            goal: The goal to achieve

        Returns:
            Tuple of (thought, action)
        """
        if self.use_function_calling:
            try:
                return await self._reason_with_function_calling(state, history, goal)
            except Exception as e:
                logger.warning(f"Function calling failed, falling back to prompt-based: {e}")
                return await self._reason_with_prompt(state, history, goal)
        else:
            return await self._reason_with_prompt(state, history, goal)

    async def reason_with_tokens(
        self,
        state: WorkingMemory,
        history: ExecutionHistory,
        goal: str,
    ) -> tuple[str, Action, TokenUsageDict | None]:
        """Decide the next action and return token usage.

        Same as reason() but also returns token usage information.
        This is used by LangGraph nodes for token tracking.

        Args:
            state: Current working memory
            history: Execution history
            goal: The goal to achieve

        Returns:
            Tuple of (thought, action, token_usage)
        """
        thought, action = await self.reason(state, history, goal)
        return thought, action, self._last_token_usage

    async def _reason_with_function_calling(
        self,
        state: WorkingMemory,
        history: ExecutionHistory,
        goal: str,
    ) -> tuple[str, Action]:
        """Use OpenAI Function Calling for structured tool invocation.

        This approach provides:
        - Automatic parameter validation
        - Structured JSON Schema for each tool
        - No manual JSON parsing needed
        - Guaranteed parameter types

        Args:
            state: Current working memory
            history: Execution history
            goal: The goal to achieve

        Returns:
            Tuple of (thought, action)
        """
        print(f"[FC DEBUG] === Starting function calling reasoning (iteration: {state.iteration_count}) ===")
        context = self._build_context(state, history, goal)

        # Prepare messages
        system_msg = SystemMessage(content=FUNCTION_CALLING_SYSTEM_PROMPT)
        user_msg = HumanMessage(content=FUNCTION_CALLING_USER_PROMPT.format(**context))

        # Get OpenAI function definitions - FILTERED BY PHASE
        allowed_tools = context.get("allowed_tools")
        functions = self.tools.get_openai_functions(allowed_tools)

        logger.info(f"[Phase Filter] Providing {len(functions)} functions to LLM (allowed: {allowed_tools})")
        print(f"[FC DEBUG] Phase-filtered functions: {[f['function']['name'] for f in functions]}")

        # Call LLM with tools (function calling)
        response = await self.llm.ainvoke(
            [system_msg, user_msg],
            tools=functions,
            tool_choice="auto",  # Let model decide which tool to call
        )

        # Extract and store token usage
        self._last_token_usage = self._extract_token_usage(response)
        if self._last_token_usage:
            logger.debug(f"Token usage: {self._last_token_usage}")

        # Debug logging (using print for visibility)
        print(f"[FC DEBUG] LLM response type: {type(response)}")
        print(f"[FC DEBUG] Has tool_calls: {hasattr(response, 'tool_calls')}")
        if hasattr(response, 'tool_calls'):
            print(f"[FC DEBUG] tool_calls: {response.tool_calls}")
        if hasattr(response, 'additional_kwargs'):
            print(f"[FC DEBUG] additional_kwargs: {response.additional_kwargs}")

        # Extract thought from content (if any)
        thought = response.content or "Deciding next action..."

        # Check for tool calls
        if hasattr(response, 'tool_calls') and response.tool_calls:
            tool_call = response.tool_calls[0]

            # LangChain ToolCall is an object with .name and .args attributes
            # Also handle dict format for compatibility
            if hasattr(tool_call, 'name'):
                # LangChain ToolCall object
                action_name = tool_call.name
                action_args = tool_call.args if hasattr(tool_call, 'args') else {}
            elif isinstance(tool_call, dict):
                # Dict format (older LangChain or OpenAI direct)
                action_name = tool_call.get("name", tool_call.get("function", {}).get("name", ""))
                action_args = tool_call.get("args", tool_call.get("function", {}).get("arguments", {}))
            else:
                logger.warning(f"Unknown tool_call format: {type(tool_call)}")
                return await self._reason_with_prompt(state, history, goal)

            # Parse args if it's a string
            if isinstance(action_args, str):
                try:
                    action_args = json.loads(action_args)
                except json.JSONDecodeError:
                    action_args = {}

            # Ensure action_args is a dict
            if not isinstance(action_args, dict):
                logger.warning(f"action_args is not a dict: {type(action_args)}")
                action_args = {}

            print(f"[FC DEBUG] Function calling selected tool: {action_name}")
            print(f"[FC DEBUG] Tool arguments keys: {list(action_args.keys()) if action_args else 'none'}")
            print(f"[FC DEBUG] Full tool arguments: {action_args}")

            # Validate FINISH is not premature (same check as prompt-based)
            if action_name == "FINISH":
                blocked, reason, suggested_action = self._validate_finish_allowed(state)
                if blocked:
                    logger.warning(f"[FC] Premature FINISH blocked: {reason}")
                    print(f"[FC DEBUG] Premature FINISH blocked: {reason}. Redirecting to {suggested_action}")
                    action = Action(
                        name=suggested_action,
                        input={},
                        confidence=0.7,
                        alternative=None,
                    )
                    thought = f"Cannot finish yet: {reason}. Proceeding with {suggested_action}."
                    return thought, action

            # Check if we should avoid this action
            if history.should_avoid(action_name):
                logger.warning(f"Action {action_name} has failed multiple times, seeking alternative")
                return await self._reason_with_prompt(state, history, goal)

            action = Action(
                name=action_name,
                input=action_args,
                confidence=0.9,  # Function calling is more reliable
                alternative=None,
            )

            return thought, action

        # No tool call - might be FINISH or need fallback
        print(f"[FC DEBUG] No tool_calls in response, falling back to prompt-based")
        print(f"[FC DEBUG] Response content: {response.content[:300] if response.content else 'empty'}")
        return await self._reason_with_prompt(state, history, goal)

    async def _reason_with_prompt(
        self,
        state: WorkingMemory,
        history: ExecutionHistory,
        goal: str,
    ) -> tuple[str, Action]:
        """Fallback: Use prompt-based reasoning (original method).

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

        # Extract and store token usage
        self._last_token_usage = self._extract_token_usage(response)
        if self._last_token_usage:
            logger.debug(f"Token usage: {self._last_token_usage}")

        logger.debug(f"Reasoner response: {content[:500]}...")

        # Parse response
        parsed = self._parse_response(content)

        # Validate FINISH is not premature
        if parsed["action"] == "FINISH":
            blocked, reason, suggested_action = self._validate_finish_allowed(state)
            if blocked:
                logger.warning(f"Premature FINISH blocked: {reason}")
                parsed = {
                    "thought": f"Cannot finish yet: {reason}. Proceeding with {suggested_action}.",
                    "action": suggested_action,
                    "action_input": {},
                    "confidence": 0.7,
                }

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

    def _validate_finish_allowed(
        self,
        state: WorkingMemory,
    ) -> tuple[bool, str, str]:
        """Check if FINISH is allowed based on current state.

        Returns:
            Tuple of (is_blocked, reason, suggested_action)
            - is_blocked: True if FINISH should be blocked
            - reason: Why FINISH is blocked
            - suggested_action: What action to take instead
        """
        # Priority order of checks
        if not state.structured_hypothesis:
            return True, "Hypothesis not parsed yet", "parse_hypothesis"

        if len(state.test_questions) < 1:
            return True, "No test questions generated", "decompose_questions"

        if len(state.experiments) < 1:
            return True, "No experiments designed yet", "design_experiment"

        if not state.plan_a:
            return True, "Plan A not generated", "synthesize_plan"

        if not state.plan_b:
            return True, "Plan B not generated", "generate_plan_b"

        # All minimum requirements met - FINISH is allowed
        return False, "", ""

    def _build_context(
        self,
        state: WorkingMemory,
        history: ExecutionHistory,
        goal: str,
    ) -> dict:
        """Build context dictionary for prompt."""
        # 실패한 액션들 (피해야 할 액션)
        failed_actions_info = []
        for action, count in history.failed_actions.items():
            if count >= 2:
                failed_actions_info.append(f"- {action}: failed {count} times (AVOID)")
            elif count == 1:
                failed_actions_info.append(f"- {action}: failed {count} time (use with caution)")

        failed_actions_str = "\n".join(failed_actions_info) if failed_actions_info else "None"

        # Phase context 생성
        phase_tracker = PhaseTracker(state)
        phase_context = phase_tracker.get_phase_prompt()
        allowed_tools = phase_tracker.get_allowed_tools()

        logger.info(f"[Phase] Current phase: {phase_tracker.get_current_phase().value}, allowed tools: {allowed_tools}")

        return {
            "goal": goal,
            "hypothesis": state.original_hypothesis,
            "phase_context": phase_context,
            "allowed_tools": allowed_tools,  # Phase별 허용된 도구 목록
            "state_summary": state.get_summary(),
            "tool_descriptions": self.tools.get_descriptions_for_llm(allowed_tools),  # 필터링된 도구만
            "recent_actions": history.get_context_for_llm(),
            "failed_actions": failed_actions_str,
            "consecutive_failures": history._consecutive_failures,
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
            # Try to fix common JSON issues before parsing
            json_str = self._fix_json_string(json_str)
            parsed = json.loads(json_str)

            # Validate required fields
            if "action" not in parsed:
                parsed["action"] = "ask_user"
                parsed["action_input"] = {
                    "question": "Unable to determine next action. Please provide guidance."
                }

            if "thought" not in parsed:
                parsed["thought"] = "No explicit reasoning provided"

            # Validate and sanitize action name
            parsed["action"] = self._sanitize_action_name(parsed["action"])

            return parsed

        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error: {e}, content: {json_str}")
            # Try to extract action from text as fallback
            return self._extract_action_from_text(content, str(e))

    def _sanitize_action_name(self, action: str) -> str:
        """Sanitize and validate action name.

        LLM sometimes outputs action names with extra text like:
        "design_experiment for another test question if this fails"

        This extracts just the valid tool name.
        """
        if not action:
            return "ask_user"

        # Get list of valid tool names
        valid_tools = self.tools.list_tools() + ["FINISH"]

        # Check if action is already valid
        if action in valid_tools:
            return action

        # Try to extract tool name from the beginning
        action_lower = action.lower().strip()
        for tool in valid_tools:
            tool_lower = tool.lower()
            # Check if the action starts with a valid tool name
            if action_lower.startswith(tool_lower):
                # Make sure it's followed by a space or end of string
                rest = action_lower[len(tool_lower):]
                if not rest or rest[0] in (' ', '_', '-', ',', '.'):
                    logger.warning(
                        f"Sanitized action name: '{action}' -> '{tool}'"
                    )
                    return tool

        # Try fuzzy matching - find best match
        for tool in valid_tools:
            if tool.lower() in action_lower:
                logger.warning(
                    f"Fuzzy matched action name: '{action}' -> '{tool}'"
                )
                return tool

        # If nothing matches, log error and return ask_user
        logger.error(
            f"Could not match action '{action}' to any valid tool. "
            f"Available: {valid_tools}"
        )
        return "ask_user"

    def _fix_json_string(self, json_str: str) -> str:
        """Fix common JSON formatting issues.

        Handles:
        - Trailing commas
        - Single quotes instead of double quotes
        - Unquoted keys
        """
        # Remove trailing commas before } or ]
        json_str = re.sub(r',\s*([}\]])', r'\1', json_str)

        # Replace single quotes with double quotes (careful with apostrophes)
        # Only do this if there are no double quotes in the string
        if '"' not in json_str and "'" in json_str:
            json_str = json_str.replace("'", '"')

        return json_str

    def _extract_action_from_text(self, content: str, error_msg: str) -> dict:
        """Extract action from text when JSON parsing fails.

        Tries to find tool names mentioned in the text and
        make a reasonable guess about what the agent intended.
        """
        logger.warning(f"JSON parsing failed, attempting text extraction: {error_msg}")

        valid_tools = self.tools.list_tools()
        content_lower = content.lower()

        # Look for tool mentions in the content
        for tool in valid_tools:
            tool_lower = tool.lower()
            if tool_lower in content_lower:
                # Found a tool mention - try to use it
                logger.info(f"Extracted tool '{tool}' from failed JSON response")
                return {
                    "thought": f"JSON parsing failed but found tool mention: {tool}",
                    "action": tool,
                    "action_input": {},  # Will need default handling
                    "confidence": 0.3,
                }

        # Check for FINISH mention
        if "finish" in content_lower:
            return {
                "thought": "JSON parsing failed but found FINISH mention",
                "action": "FINISH",
                "action_input": {"final_result": "Partial completion due to parsing issues"},
            }

        # Default fallback
        return {
            "thought": f"JSON parsing failed: {error_msg}",
            "action": "ask_user",
            "action_input": {
                "question": "The agent encountered a parsing issue. Please provide guidance.",
                "options": ["Continue", "Cancel"],
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

        # Extract and accumulate token usage (for alternative calls)
        alt_token_usage = self._extract_token_usage(response)
        if alt_token_usage and self._last_token_usage:
            # Accumulate tokens from alternative call
            self._last_token_usage = TokenUsageDict(
                prompt_tokens=self._last_token_usage.get("prompt_tokens", 0) + alt_token_usage.get("prompt_tokens", 0),
                completion_tokens=self._last_token_usage.get("completion_tokens", 0) + alt_token_usage.get("completion_tokens", 0),
                total_tokens=self._last_token_usage.get("total_tokens", 0) + alt_token_usage.get("total_tokens", 0),
            )
        elif alt_token_usage:
            self._last_token_usage = alt_token_usage

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
