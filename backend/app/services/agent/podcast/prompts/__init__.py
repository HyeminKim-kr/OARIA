"""Podcast prompts module.

F-11: Agentic Podcast System
Prompts for paper analysis and script generation.
"""

from .podcast import (
    PAPER_ANALYSIS_PROMPT,
    SCRIPT_GENERATION_TWO_HOSTS_PROMPT,
    SCRIPT_GENERATION_INTERVIEW_PROMPT,
    SCRIPT_GENERATION_SOLO_PROMPT,
    get_duration_instruction,
    get_language_instruction,
    get_script_prompt,
)

__all__ = [
    "PAPER_ANALYSIS_PROMPT",
    "SCRIPT_GENERATION_TWO_HOSTS_PROMPT",
    "SCRIPT_GENERATION_INTERVIEW_PROMPT",
    "SCRIPT_GENERATION_SOLO_PROMPT",
    "get_duration_instruction",
    "get_language_instruction",
    "get_script_prompt",
]
