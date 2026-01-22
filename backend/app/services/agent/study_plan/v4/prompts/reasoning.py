"""Reasoning prompts for v4 agent.

These prompts guide the LLM in making decisions about
which tool to use next and how to handle failures.
"""

TOOL_SELECTION_PROMPT = """You are an AI agent designing a research study plan.
Your goal is to create a comprehensive, scientifically rigorous experimental design
to test the given hypothesis.

## Goal
{goal}

## Original Hypothesis
{hypothesis}

## Current State
{state_summary}

## Available Tools
{tool_descriptions}

## Recent Actions
{recent_actions}

## Instructions
Based on the current state and goal, decide the next action.

Think step by step:
1. What information do I have now?
2. What information do I still need?
3. What is blocking progress toward the goal?
4. Which tool would help most right now?

Consider these priorities:
- Parse hypothesis before searching
- Search for evidence before designing experiments
- Validate designs before synthesizing the final plan
- If stuck, try a different approach or ask the user

## Response Format
Respond in this exact JSON format:
```json
{{
    "thought": "My reasoning about what to do next...",
    "action": "tool_name",
    "action_input": {{
        "param1": "value1"
    }},
    "confidence": 0.85,
    "alternative": "backup_tool_name if this fails"
}}
```

If the goal is fully achieved, respond:
```json
{{
    "thought": "Goal achieved because [list specific completions]...",
    "action": "FINISH",
    "action_input": {{
        "final_result": "summary of what was accomplished"
    }}
}}
```

Important rules:
- Only use tools from the available tools list
- Provide all required parameters for the chosen tool
- Be specific in your thought process
- If quality_score >= 0.8 and all validations pass, you may FINISH
"""

ALTERNATIVE_SELECTION_PROMPT = """You are an AI agent that needs to find an alternative approach.

## Original Plan
Action: {original_action}
Reason it failed: {failure_reason}

## Current State
{state_summary}

## Available Tools
{tool_descriptions}

## What has been tried
{tried_actions}

## Instructions
Find an alternative approach to make progress. Consider:
1. Can a different tool achieve the same goal?
2. Should we simplify the task first?
3. Is there missing information we need?
4. Should we ask the user for guidance?

Respond in this exact JSON format:
```json
{{
    "thought": "Why this alternative might work...",
    "action": "alternative_tool_name",
    "action_input": {{
        "param1": "value1"
    }},
    "confidence": 0.7
}}
```
"""

GOAL_COMPLETION_PROMPT = """Evaluate whether the research plan generation goal has been achieved.

## Original Goal
{goal}

## Hypothesis
{hypothesis}

## Current State Summary
{state_summary}

## Requirements Checklist
- Hypothesis parsed and structured: {hypothesis_parsed}
- Test questions generated: {questions_count} (minimum 3)
- Experiments designed: {experiments_count} (minimum 1)
- Controls validated: {controls_complete}
- Measurements cover hypothesis variables: {measurements_coverage:.0%} (minimum 80%)
- Quality score: {quality_score:.0%} (minimum 70%)

## Evaluation
Based on the above, determine if the plan is complete enough.

Respond in JSON:
```json
{{
    "is_complete": true/false,
    "missing_items": ["list of missing requirements"],
    "quality_assessment": "brief quality assessment",
    "recommendation": "FINISH or next action to take"
}}
```
"""
