"""AI video-generation provider layer (infrastructure).

A vendor-neutral :class:`VideoProvider` contract, its request/result models, a
:class:`VideoProviderRegistry` that selects the configured driver, and two
drivers: :class:`MockVideoProvider` (development — renders scene clips with the
existing local ffmpeg pipeline) and :class:`KlingVideoProvider` (Kling AI
image-to-video: submit → poll → download).

``mock`` stays the default so the CLI runs without paid credentials. Further
drivers plug in by satisfying the protocol and registering a builder — no
existing code changes (ADR-005). This layer is additive: the slideshow compose
pipeline (``FfmpegVideoComposer``) is untouched and keeps working exactly as
before.
"""

from ai_video_factory.infrastructure.video.providers.base.models import (
    VideoGenerationRequest,
    VideoGenerationResult,
    VideoJobStatus,
    VideoProviderStatus,
)
from ai_video_factory.infrastructure.video.providers.base.provider import VideoProvider
from ai_video_factory.infrastructure.video.providers.base.writer import (
    VideoManifestEntry,
    write_video_manifest,
)
from ai_video_factory.infrastructure.video.providers.cost import (
    GenerationPlan,
    build_plan,
    estimate_cost,
)
from ai_video_factory.infrastructure.video.providers.errors import VideoProviderError
from ai_video_factory.infrastructure.video.providers.kling.models import KlingJob
from ai_video_factory.infrastructure.video.providers.kling.provider import KlingVideoProvider
from ai_video_factory.infrastructure.video.providers.mock.provider import MockVideoProvider
from ai_video_factory.infrastructure.video.providers.registry import (
    KLING_PROVIDER,
    MOCK_PROVIDER,
    VideoProviderRegistry,
    build_default_registry,
)
from ai_video_factory.infrastructure.video.providers.scene_reader import (
    build_requests,
    read_scene_movie,
)

__all__ = [
    "KLING_PROVIDER",
    "MOCK_PROVIDER",
    "GenerationPlan",
    "KlingJob",
    "KlingVideoProvider",
    "MockVideoProvider",
    "VideoGenerationRequest",
    "VideoGenerationResult",
    "VideoJobStatus",
    "VideoManifestEntry",
    "VideoProvider",
    "VideoProviderError",
    "VideoProviderRegistry",
    "VideoProviderStatus",
    "build_default_registry",
    "build_plan",
    "build_requests",
    "estimate_cost",
    "read_scene_movie",
    "write_video_manifest",
]
