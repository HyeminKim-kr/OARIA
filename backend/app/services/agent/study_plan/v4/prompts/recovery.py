"""Recovery prompts for handling failures."""

RECOVERY_STRATEGY_PROMPT = """You are an AI agent that needs to recover from a failure.

## Failure Type
{failure_type}

## Error Details
{error_details}

## Current State
{state_summary}

## Available Recovery Strategies
{available_strategies}

## What Has Been Tried
{tried_strategies}

## Instructions
Select the best recovery strategy based on:
1. The nature of the failure
2. What has already been tried
3. The current state of progress
4. Cost/benefit of each strategy

Respond in JSON:
```json
{{
    "chosen_strategy": "strategy_name",
    "reason": "why this strategy is most likely to work",
    "fallback": "what to do if this also fails",
    "should_notify_user": true/false
}}
```
"""

USER_INTERVENTION_PROMPT = """The agent needs user input to proceed.

## Current Situation
{situation}

## What Was Attempted
{attempts}

## Options for User
{options}

## Question for User
Please provide guidance on how to proceed:
"""
