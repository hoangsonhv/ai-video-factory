"""Speech provider contract: protocol, models, and metadata writer."""

from ai_video_factory.infrastructure.providers.speech.base.models import (
    SpeechSynthesisRequest,
    SpeechSynthesisResponse,
    SynthesizedAudio,
)
from ai_video_factory.infrastructure.providers.speech.base.provider import SpeechProvider
from ai_video_factory.infrastructure.providers.speech.base.writer import write_audio_metadata

__all__ = [
    "SpeechProvider",
    "SpeechSynthesisRequest",
    "SpeechSynthesisResponse",
    "SynthesizedAudio",
    "write_audio_metadata",
]
