"""Goal Generator for Scheduled Podcast Generation.

F-11: Agentic Podcast System
Converts subscription topics to podcast goals.
"""

import logging
from datetime import datetime, timedelta
from typing import Any

from openai import AsyncOpenAI

from app.config import settings
from app.models.podcast import PodcastSubscription, PodcastFrequency

logger = logging.getLogger(__name__)


# Template-based goal generation (fallback when LLM unavailable)
GOAL_TEMPLATES = {
    "ko": {
        "daily": "{topics}의 최신 연구 동향 요약",
        "weekly": "이번 주 {topics} 관련 주요 연구 정리",
        "monthly": "이번 달 {topics} 분야의 핵심 발전 사항",
    },
    "en": {
        "daily": "Latest research updates on {topics}",
        "weekly": "This week's key research on {topics}",
        "monthly": "Monthly highlights in {topics} research",
    },
}


GOAL_GENERATION_PROMPT = """You are a podcast goal generator for oncology research.

Generate a clear, focused podcast goal based on the subscription topics.
The goal should be specific enough to guide RAG search but broad enough to find relevant papers.

## Subscription Details
- Topics: {topics}
- Frequency: {frequency}
- Language: {language}

## Time Context
- Today: {today}
- Period: {period_description}

## Requirements
1. The goal must be in {language_name}
2. Focus on recent developments, not general overview
3. Be specific to the topics provided
4. Make it suitable for a podcast episode (informative, engaging)

## Output
Return ONLY the goal text, nothing else. No quotes, no explanation.

Example outputs:
- Korean: "HER2 양성 유방암의 최신 표적치료제 비교 분석"
- English: "Comparing latest targeted therapies for HER2-positive breast cancer"
"""


def generate_goal_from_template(
    subscription: PodcastSubscription,
) -> str:
    """
    Generate a goal using templates (no LLM).

    Simple fallback when OpenAI is unavailable.
    """
    language = subscription.language or "ko"
    frequency = subscription.frequency or "weekly"
    topics = ", ".join(subscription.topics)

    templates = GOAL_TEMPLATES.get(language, GOAL_TEMPLATES["en"])
    template = templates.get(frequency, templates["weekly"])

    return template.format(topics=topics)


async def generate_goal_with_llm(
    subscription: PodcastSubscription,
) -> str:
    """
    Generate a podcast goal using LLM.

    Creates a more natural, context-aware goal based on topics and timing.
    """
    if not settings.openai_api_key:
        logger.warning("OpenAI API key not set, using template-based goal")
        return generate_goal_from_template(subscription)

    try:
        # Prepare context
        topics = ", ".join(subscription.topics)
        today = datetime.utcnow().strftime("%Y-%m-%d")

        frequency = subscription.frequency or "weekly"
        if frequency == "daily":
            period_description = "Today's research"
        elif frequency == "weekly":
            week_start = (datetime.utcnow() - timedelta(days=7)).strftime("%Y-%m-%d")
            period_description = f"Research from {week_start} to {today}"
        else:  # monthly
            month_start = datetime.utcnow().replace(day=1).strftime("%Y-%m-%d")
            period_description = f"Research from {month_start} to {today}"

        language = subscription.language or "ko"
        language_name = "Korean (한국어)" if language == "ko" else "English"

        # Build prompt
        prompt = GOAL_GENERATION_PROMPT.format(
            topics=topics,
            frequency=frequency,
            language=language,
            today=today,
            period_description=period_description,
            language_name=language_name,
        )

        # Call LLM
        client = AsyncOpenAI(api_key=settings.openai_api_key)
        response = await client.chat.completions.create(
            model=settings.openai_chat_model,
            messages=[
                {"role": "system", "content": "You are a podcast goal generator. Be concise and focused."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.7,
            max_tokens=100,
        )

        goal = response.choices[0].message.content or ""
        goal = goal.strip().strip('"').strip("'")

        if not goal:
            logger.warning("LLM returned empty goal, using template")
            return generate_goal_from_template(subscription)

        logger.info(f"Generated goal for subscription {subscription.id}: {goal}")
        return goal

    except Exception as e:
        logger.error(f"Goal generation failed: {e}, using template")
        return generate_goal_from_template(subscription)


def get_subscriptions_for_frequency(
    subscriptions: list[PodcastSubscription],
    frequency: str,
) -> list[PodcastSubscription]:
    """
    Filter subscriptions by frequency.

    Args:
        subscriptions: List of all subscriptions
        frequency: "daily", "weekly", or "monthly"

    Returns:
        Filtered list of active subscriptions matching the frequency
    """
    return [
        sub for sub in subscriptions
        if sub.is_active and sub.frequency == frequency
    ]


def should_generate_for_subscription(
    subscription: PodcastSubscription,
) -> bool:
    """
    Check if we should generate a new episode for this subscription.

    Prevents generating too frequently (respects the frequency setting).
    """
    if not subscription.is_active:
        return False

    if not subscription.last_generated_at:
        return True  # Never generated before

    now = datetime.utcnow()
    last = subscription.last_generated_at

    frequency = subscription.frequency or "weekly"

    if frequency == "daily":
        return (now - last) >= timedelta(hours=20)  # At least 20 hours
    elif frequency == "weekly":
        return (now - last) >= timedelta(days=6)  # At least 6 days
    else:  # monthly
        return (now - last) >= timedelta(days=25)  # At least 25 days
