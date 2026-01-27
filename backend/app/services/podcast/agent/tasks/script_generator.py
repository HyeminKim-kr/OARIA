"""Task 3: Script Generation

Generates podcast dialogue script using LLM.
Uses RAG context from Task 1 and analysis from Task 2.
"""

import json
import logging
import time
from collections.abc import AsyncGenerator
from typing import Any

from openai import AsyncOpenAI

from app.config import settings
from app.schemas.chat import Reference
from ..state import PodcastTaskResult, PodcastTaskType, DialogueScript, DialogueTurn
from ..prompts import (
    get_script_prompt,
    get_duration_instruction,
    get_language_instruction,
)
from .rag_search import format_references_for_podcast
from .paper_analysis import format_analysis_for_script

logger = logging.getLogger(__name__)


async def execute_script_generation(
    goal: str,
    references: list[Reference],
    context: str,
    analysis_result: PodcastTaskResult,
    style: str = "two_hosts",
    duration: str = "short",
    language: str = "ko",
) -> PodcastTaskResult:
    """
    Generate podcast script using LLM (Task 3).

    Uses:
    - RAG context from Task 1 (for citations)
    - Analysis summary from Task 2 (for key points)

    Args:
        goal: User's podcast goal
        references: References from Task 1
        context: Context string from Task 1
        analysis_result: Completed Task 2 result
        style: Podcast style (two_hosts/interview/solo)
        duration: Episode duration (short/medium/long)
        language: Output language (ko/en)

    Returns:
        PodcastTaskResult with DialogueScript
    """
    start_time = time.perf_counter()

    result = PodcastTaskResult(
        task_type=PodcastTaskType.SCRIPT_GENERATION,
        status="running",
    )

    try:
        # Format inputs
        formatted_context = format_references_for_podcast(references)
        analysis_summary = format_analysis_for_script(analysis_result)
        duration_instruction = get_duration_instruction(duration)
        language_instruction = get_language_instruction(language)

        # Get appropriate prompt for style
        prompt_template = get_script_prompt(style)
        prompt = prompt_template.format(
            goal=goal,
            context=formatted_context,
            analysis_summary=analysis_summary,
            duration_instruction=duration_instruction,
            language_instruction=language_instruction,
        )

        # Call LLM
        if not settings.openai_api_key:
            logger.warning("OpenAI API key not set, using mock script")
            script_data = _mock_script(goal, style, duration, language)
        else:
            client = AsyncOpenAI(api_key=settings.openai_api_key)
            response = await client.chat.completions.create(
                model=settings.openai_chat_model,
                messages=[
                    {"role": "system", "content": "You are a podcast script writer. Respond only in valid JSON."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.7,  # Slightly more creative for scripts
                max_tokens=4000,
                response_format={"type": "json_object"},
            )

            script_text = response.choices[0].message.content or "{}"
            script_data = json.loads(script_text)

        # Parse into DialogueScript
        script = _parse_script_data(script_data)

        # Store as dict for serialization
        result.script = script.to_dict()
        result.status = "completed"

        logger.info(
            f"Script generation completed: {len(script.turns)} turns, "
            f"~{script.total_estimated_duration}s"
        )

    except json.JSONDecodeError as e:
        logger.error(f"Script generation JSON parse error: {e}")
        result.status = "failed"
        result.error = f"Failed to parse script response: {e}"
    except Exception as e:
        logger.error(f"Script generation failed: {e}", exc_info=True)
        result.status = "failed"
        result.error = str(e)

    result.duration_ms = int((time.perf_counter() - start_time) * 1000)
    return result


async def execute_script_generation_stream(
    goal: str,
    references: list[Reference],
    context: str,
    analysis_result: PodcastTaskResult,
    style: str = "two_hosts",
    duration: str = "short",
    language: str = "ko",
) -> AsyncGenerator[str, None]:
    """
    Generate podcast script with streaming output.

    Yields script content as it's generated for real-time UI updates.

    Args:
        Same as execute_script_generation

    Yields:
        Script chunks as they are generated
    """
    # Format inputs
    formatted_context = format_references_for_podcast(references)
    analysis_summary = format_analysis_for_script(analysis_result)
    duration_instruction = get_duration_instruction(duration)
    language_instruction = get_language_instruction(language)

    # Get appropriate prompt for style
    prompt_template = get_script_prompt(style)
    prompt = prompt_template.format(
        goal=goal,
        context=formatted_context,
        analysis_summary=analysis_summary,
        duration_instruction=duration_instruction,
        language_instruction=language_instruction,
    )

    if not settings.openai_api_key:
        # Mock streaming for testing
        mock_script = json.dumps(_mock_script(goal, style, duration, language), ensure_ascii=False)
        for char in mock_script:
            yield char
        return

    client = AsyncOpenAI(api_key=settings.openai_api_key)
    stream = await client.chat.completions.create(
        model=settings.openai_chat_model,
        messages=[
            {"role": "system", "content": "You are a podcast script writer. Respond only in valid JSON."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.7,
        max_tokens=4000,
        stream=True,
    )

    async for chunk in stream:
        if chunk.choices and chunk.choices[0].delta.content:
            yield chunk.choices[0].delta.content


def _parse_script_data(data: dict[str, Any]) -> DialogueScript:
    """Parse JSON data into DialogueScript dataclass."""
    turns = []
    for turn_data in data.get("turns", []):
        turns.append(
            DialogueTurn(
                speaker=turn_data.get("speaker", "Alex"),
                text=turn_data.get("text", ""),
                citations=turn_data.get("citations", []),
            )
        )

    return DialogueScript(
        title=data.get("title", "Untitled Episode"),
        description=data.get("description", ""),
        speakers=data.get("speakers", ["Alex", "Sam"]),
        turns=turns,
        total_estimated_duration=data.get("total_estimated_duration", 300),
    )


def _mock_script(
    goal: str,
    style: str,
    duration: str,
    language: str,
) -> dict[str, Any]:
    """Generate mock script for testing without OpenAI API."""
    if style == "two_hosts":
        speakers = ["Alex", "Sam"]
    elif style == "interview":
        speakers = ["Alex", "Dr. Kim"]
    else:
        speakers = ["Alex"]

    if language == "ko":
        if style == "two_hosts":
            turns = [
                {"speaker": "Alex", "text": f"안녕하세요! 오늘은 {goal}에 대해 이야기해보겠습니다.", "citations": []},
                {"speaker": "Sam", "text": "흥미로운 주제네요! 이 분야에서 최근 어떤 연구들이 있나요?", "citations": []},
                {"speaker": "Alex", "text": "최근 연구에 따르면 [1], 이 분야에서 중요한 발전이 있었습니다.", "citations": [1]},
                {"speaker": "Sam", "text": "그게 환자들에게는 어떤 의미가 있나요?", "citations": []},
                {"speaker": "Alex", "text": "좋은 질문입니다. 연구 [1, 2]에 의하면, 치료 결과가 크게 개선될 수 있습니다.", "citations": [1, 2]},
                {"speaker": "Sam", "text": "정말 희망적인 소식이네요!", "citations": []},
                {"speaker": "Alex", "text": "네, 오늘 논의한 내용을 정리하면...", "citations": []},
            ]
        elif style == "interview":
            turns = [
                {"speaker": "Alex", "text": f"김 박사님, {goal}에 대해 말씀해 주세요.", "citations": []},
                {"speaker": "Dr. Kim", "text": "최근 이 분야에서 흥미로운 발견이 있었습니다 [1].", "citations": [1]},
                {"speaker": "Alex", "text": "구체적으로 어떤 발견인가요?", "citations": []},
                {"speaker": "Dr. Kim", "text": "연구에 따르면 [1, 2], 새로운 치료 접근법이 효과적입니다.", "citations": [1, 2]},
            ]
        else:  # solo
            turns = [
                {"speaker": "Alex", "text": f"오늘은 {goal}에 대해 알아보겠습니다.", "citations": []},
                {"speaker": "Alex", "text": "먼저, 기본 개념부터 살펴보죠.", "citations": []},
                {"speaker": "Alex", "text": "연구 [1]에 따르면, 중요한 발견이 있었습니다.", "citations": [1]},
                {"speaker": "Alex", "text": "이것이 의미하는 바는...", "citations": []},
            ]
    else:  # English
        if style == "two_hosts":
            turns = [
                {"speaker": "Alex", "text": f"Welcome! Today we'll discuss {goal}.", "citations": []},
                {"speaker": "Sam", "text": "Fascinating topic! What recent research exists in this area?", "citations": []},
                {"speaker": "Alex", "text": "According to recent studies [1], there have been significant advances.", "citations": [1]},
                {"speaker": "Sam", "text": "What does this mean for patients?", "citations": []},
                {"speaker": "Alex", "text": "Great question. Research [1, 2] shows improved treatment outcomes.", "citations": [1, 2]},
            ]
        else:
            turns = [
                {"speaker": "Alex", "text": f"Today we explore {goal}.", "citations": []},
                {"speaker": "Alex", "text": "Recent research [1] reveals important findings.", "citations": [1]},
            ]

    # Estimate duration based on text length
    total_words = sum(len(t["text"].split()) for t in turns)
    estimated_seconds = int(total_words / 2.5)  # ~150 words per minute

    return {
        "title": f"Understanding {goal}" if language == "en" else f"{goal} 이해하기",
        "description": f"An exploration of {goal}" if language == "en" else f"{goal}에 대한 탐구",
        "speakers": speakers,
        "turns": turns,
        "total_estimated_duration": max(estimated_seconds, 60),
    }
