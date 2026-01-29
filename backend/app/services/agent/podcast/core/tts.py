"""TTS Service for Podcast Audio Generation.

F-11: Agentic Podcast System
Uses OpenAI TTS to generate multi-speaker audio from dialogue scripts.
"""

import io
import logging
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from openai import AsyncOpenAI

from app.config import settings

logger = logging.getLogger(__name__)


# OpenAI TTS voice mapping - distinctive male/female voices
VOICE_MAP = {
    # Two hosts style - clearly different male & female
    "Alex": "onyx",       # Deep male voice - lead host
    "Sam": "shimmer",     # Bright female voice - co-host

    # Interview style
    "Dr. Kim": "onyx",    # Deep, authoritative expert (male)
    "Host": "nova",       # Warm female interviewer

    # Solo narration
    "Narrator": "fable",  # Expressive, British accent

    # Fallback
    "default": "onyx",
}

# Speaker-specific instructions for natural, engaging delivery
VOICE_INSTRUCTIONS = {
    # Two hosts style - male & female co-hosts
    "Alex": (
        "You are Alex, a male podcast host with a warm, deep voice. "
        "Speak with genuine enthusiasm and authority about scientific topics. "
        "Be engaging and conversational, like explaining fascinating discoveries to a friend. "
        "Use natural pacing with thoughtful pauses. Sound confident but approachable."
    ),
    "Sam": (
        "You are Sam, a female co-host with a bright, energetic voice. "
        "Speak with curiosity and warmth. React naturally - sound genuinely impressed, "
        "curious, or excited as appropriate. Be lively and conversational, "
        "bringing energy to the discussion. Ask insightful follow-up questions."
    ),

    # Interview style - professional but engaging
    "Dr. Kim": (
        "You are Dr. Kim, a distinguished male researcher being interviewed. "
        "Speak with authority and deep expertise, but remain passionate and accessible. "
        "Explain complex topics clearly, with the enthusiasm of someone who loves their field. "
        "Use a measured, confident pace."
    ),
    "Host": (
        "You are a professional female podcast interviewer. "
        "Speak with warmth, curiosity, and genuine interest in your guest's expertise. "
        "Ask thoughtful questions and react naturally to answers. "
        "Be engaging and guide the conversation smoothly."
    ),

    # Solo narration - documentary style
    "Narrator": (
        "You are a narrator for a science documentary podcast. "
        "Speak with a sophisticated British accent, calm and measured. "
        "Be clear and engaging, with subtle emphasis on key discoveries. "
        "Sound knowledgeable yet accessible, inspiring wonder about the topic."
    ),

    # Default fallback
    "default": (
        "Speak as an engaging podcast host. Be warm, conversational, and enthusiastic. "
        "Use natural pacing with appropriate pauses. Sound genuinely interested in the topic."
    ),
}


@dataclass
class TurnTiming:
    """Timing info for a single dialogue turn."""

    turn_index: int
    start_time: float
    end_time: float
    speaker: str


@dataclass
class TTSResult:
    """Result from TTS generation."""

    audio_data: bytes
    duration_seconds: int
    format: str  # "mp3"
    speaker_count: int
    turn_timings: list[TurnTiming] = field(default_factory=list)
    error: str | None = None


class TTSService:
    """
    Text-to-Speech service using OpenAI TTS.

    Supports multi-speaker dialogue by generating audio for each turn
    and concatenating them.
    """

    def __init__(self):
        self._client: AsyncOpenAI | None = None

    def _get_client(self) -> AsyncOpenAI | None:
        """Get or create OpenAI client."""
        if self._client is None and settings.openai_api_key:
            self._client = AsyncOpenAI(api_key=settings.openai_api_key)
        return self._client

    @property
    def is_enabled(self) -> bool:
        """Check if TTS is available."""
        return bool(settings.openai_api_key)

    def get_voice_for_speaker(self, speaker: str) -> str:
        """Get the OpenAI voice ID for a speaker name."""
        return VOICE_MAP.get(speaker, VOICE_MAP["default"])

    def get_instructions_for_speaker(self, speaker: str) -> str:
        """Get the voice instructions for a speaker name."""
        return VOICE_INSTRUCTIONS.get(speaker, VOICE_INSTRUCTIONS["default"])

    async def generate_speech(
        self,
        text: str,
        voice: str = "coral",
        speed: float = 1.0,
        instructions: str | None = None,
    ) -> bytes:
        """
        Generate speech audio for a single text segment.

        Args:
            text: Text to convert to speech
            voice: OpenAI voice ID (alloy, ash, coral, echo, fable, nova, onyx, sage, shimmer)
            speed: Speech speed (0.25 to 4.0)
            instructions: Optional instructions for how the voice should speak (gpt-4o-mini-tts only)

        Returns:
            Audio bytes in MP3 format
        """
        client = self._get_client()
        if not client:
            raise ValueError("OpenAI API key not configured")

        # Use the newest model with instructions support for natural voices
        create_params: dict = {
            "model": "gpt-4o-mini-tts",
            "voice": voice,
            "input": text,
            "speed": speed,
            "response_format": "mp3",
        }

        # Add instructions if provided (makes voices much more natural)
        if instructions:
            create_params["instructions"] = instructions

        response = await client.audio.speech.create(**create_params)

        return response.content

    def _get_mp3_duration(self, audio_bytes: bytes) -> float:
        """Get the duration of an MP3 audio segment in seconds using mutagen."""
        try:
            from mutagen.mp3 import MP3

            mp3 = MP3(io.BytesIO(audio_bytes))
            return mp3.info.length
        except Exception as e:
            logger.warning(f"Failed to measure MP3 duration with mutagen: {e}")
            return 0.0

    async def generate_dialogue_audio(
        self,
        script: dict[str, Any],
        speed: float = 1.05,
    ) -> TTSResult:
        """
        Generate audio for a complete dialogue script.

        Generates audio for each turn and concatenates them.
        Tracks per-turn timing for frontend transcript highlighting.

        Uses gpt-4o-mini-tts with speaker-specific instructions for
        natural, engaging podcast-style delivery.

        Args:
            script: DialogueScript as dict with 'turns' list
            speed: Speech speed (default 1.05 for natural conversational pacing)

        Returns:
            TTSResult with combined audio and turn_timings
        """
        if not self.is_enabled:
            return TTSResult(
                audio_data=b"",
                duration_seconds=0,
                format="mp3",
                speaker_count=0,
                error="TTS not enabled (OpenAI API key not set)",
            )

        turns = script.get("turns", [])
        if not turns:
            return TTSResult(
                audio_data=b"",
                duration_seconds=0,
                format="mp3",
                speaker_count=0,
                error="No dialogue turns in script",
            )

        speakers = set()
        audio_segments: list[bytes] = []
        turn_timings: list[TurnTiming] = []
        cumulative_time = 0.0

        for idx, turn in enumerate(turns):
            speaker = turn.get("speaker", "Alex")
            text = turn.get("text", "")

            if not text.strip():
                continue

            speakers.add(speaker)
            voice = self.get_voice_for_speaker(speaker)
            instructions = self.get_instructions_for_speaker(speaker)

            try:
                audio_data = await self.generate_speech(
                    text=text,
                    voice=voice,
                    speed=speed,
                    instructions=instructions,
                )
                segment_duration = self._get_mp3_duration(audio_data)
                turn_timings.append(
                    TurnTiming(
                        turn_index=idx,
                        start_time=cumulative_time,
                        end_time=cumulative_time + segment_duration,
                        speaker=speaker,
                    )
                )
                cumulative_time += segment_duration
                audio_segments.append(audio_data)
            except Exception as e:
                logger.error(f"TTS generation failed for turn: {e}")
                # Continue with other turns

        if not audio_segments:
            return TTSResult(
                audio_data=b"",
                duration_seconds=0,
                format="mp3",
                speaker_count=len(speakers),
                error="No audio segments generated",
            )

        # Concatenate audio segments
        combined_audio = self._concatenate_mp3_segments(audio_segments)

        # Use actual cumulative duration instead of WPM estimate
        total_duration = int(cumulative_time)

        return TTSResult(
            audio_data=combined_audio,
            duration_seconds=total_duration,
            format="mp3",
            speaker_count=len(speakers),
            turn_timings=turn_timings,
        )

    def _concatenate_mp3_segments(self, segments: list[bytes]) -> bytes:
        """
        Concatenate MP3 audio segments.

        Simple concatenation works for MP3 files as they are frame-based.
        For production, consider using pydub or ffmpeg for proper handling.
        """
        return b"".join(segments)

    async def generate_and_upload(
        self,
        script: dict[str, Any],
        episode_id: uuid.UUID,
        speed: float = 1.0,
    ) -> tuple[str | None, int | None, str | None]:
        """
        Generate audio and upload to S3.

        Args:
            script: DialogueScript as dict
            episode_id: Episode ID for file naming
            speed: Speech speed

        Returns:
            Tuple of (audio_url, duration_seconds, error)
        """
        # Generate audio
        result = await self.generate_dialogue_audio(script, speed)

        if result.error or not result.audio_data:
            return None, None, result.error

        # Upload to S3
        try:
            from app.services.s3_service import s3_service

            # Upload path: podcast/episodes/{episode_id}/audio.mp3
            object_key = f"podcast/episodes/{episode_id}/audio.mp3"

            url = await s3_service.upload_bytes(
                data=result.audio_data,
                object_key=object_key,
                content_type="audio/mpeg",
            )

            return url, result.duration_seconds, None

        except Exception as e:
            logger.error(f"Failed to upload podcast audio: {e}")
            return None, result.duration_seconds, f"Upload failed: {e}"


# Singleton instance
tts_service = TTSService()


def get_tts_service() -> TTSService:
    """Get TTS service instance."""
    return tts_service
