"""Asset pipeline (infrastructure).

A uniform layer over asset generation: a common ``AssetResult``, generator
Protocols (image, speech, subtitle, video), working adapters that wrap the
existing provider layers, and an ``AssetPipelineRunner`` that orchestrates them.
"""

from ai_video_factory.infrastructure.asset_pipeline.adapters import (
    ImageAssetGenerator,
    SpeechAssetGenerator,
)
from ai_video_factory.infrastructure.asset_pipeline.errors import AssetStageUnavailableError
from ai_video_factory.infrastructure.asset_pipeline.generators import (
    ImageGenerator,
    SpeechGenerator,
    SubtitleGenerator,
    VideoComposer,
)
from ai_video_factory.infrastructure.asset_pipeline.models import AssetResult, AssetStage
from ai_video_factory.infrastructure.asset_pipeline.runner import AssetPipelineRunner

__all__ = [
    "AssetPipelineRunner",
    "AssetResult",
    "AssetStage",
    "AssetStageUnavailableError",
    "ImageAssetGenerator",
    "ImageGenerator",
    "SpeechAssetGenerator",
    "SpeechGenerator",
    "SubtitleGenerator",
    "VideoComposer",
]
