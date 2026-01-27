"""TTS Service for Podcast Audio Generation.

F-11: Agentic Podcast System
Uses OpenAI TTS to generate multi-speaker audio from dialogue scripts.
"""

import io
import logging
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from openai import AsyncOpenAI

from app.config import settings

logger = logging.getLogger(__name__)


# OpenAI TTS voice mapping
VOICE_MAP = {
    # Two hosts style
    "Alex": "alloy",      # Neutral, clear voice
    "Sam": "nova",        # Warm, friendly voice

    # Interview style
    "Dr. Kim": "onyx",    # Deep, authoritative voice

    # Fallback
    "default": "alloy",
}


@dataclass
class TTSResult:
    """Result from TTS generation."""

    audio_data: bytes
    duration_seconds: int
    format: str  # "mp3"
    speaker_count: int
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

    async def generate_speech(
        self,
        text: str,
        voice: str = "alloy",
        speed: float = 1.0,
    ) -> bytes:
        """
        Generate speech audio for a single text segment.

        Args:
            text: Text to convert to speech
            voice: OpenAI voice ID (alloy, echo, fable, onyx, nova, shimmer)
            speed: Speech speed (0.25 to 4.0)

        Returns:
            Audio bytes in MP3 format
        """
        client = self._get_client()
        if not client:
            raise ValueError("OpenAI API key not configured")

        response = await client.audio.speech.create(
            model="tts-1",  # Use tts-1-hd for higher quality
            voice=voice,
            input=text,
            speed=speed,
            response_format="mp3",
        )

        return response.content

    async def generate_dialogue_audio(
        self,
        script: dict[str, Any],
        speed: float = 1.0,
    ) -> TTSResult:
        """
        Generate audio for a complete dialogue script.

        Generates audio for each turn and concatenates them.

        Args:
            script: DialogueScript as dict with 'turns' list
            speed: Speech speed

        Returns:
            TTSResult with combined audio
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

        for turn in turns:
            speaker = turn.get("speaker", "Alex")
            text = turn.get("text", "")

            if not text.strip():
                continue

            speakers.add(speaker)
            voice = self.get_voice_for_speaker(speaker)

            try:
                audio_data = await self.generate_speech(
                    text=text,
                    voice=voice,
                    speed=speed,
                )
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

        # Estimate duration (rough: ~150 words per minute at 1.0 speed)
        total_words = sum(len(turn.get("text", "").split()) for turn in turns)
        estimated_duration = int((total_words / 150) * 60 / speed)

        return TTSResult(
            audio_data=combined_audio,
            duration_seconds=estimated_duration,
            format="mp3",
            speaker_count=len(speakers),
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
