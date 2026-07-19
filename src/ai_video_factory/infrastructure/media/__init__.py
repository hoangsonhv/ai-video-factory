"""Media adapters (infrastructure) — filesystem storage for generated assets."""

from ai_video_factory.infrastructure.media.audio_storage import AudioStorage
from ai_video_factory.infrastructure.media.image_storage import ImageStorage

__all__ = ["AudioStorage", "ImageStorage"]
