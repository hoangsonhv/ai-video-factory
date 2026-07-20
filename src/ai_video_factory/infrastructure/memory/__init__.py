"""Character memory stage (infrastructure).

Freezes each character's canonical look, adopts the first generated image of
them as the reference, and rewrites every prompt to restate that identity — so
the tenth image of someone matches the first.

Deterministic and offline: no provider is contacted, no image generated, and
no video or compose stage touched.
"""

from ai_video_factory.infrastructure.memory.builder import (
    adopt_references,
    derive_memory,
    first_image_for,
    merge_memory,
)
from ai_video_factory.infrastructure.memory.engine import CharacterMemoryEngine, MemoryResult
from ai_video_factory.infrastructure.memory.enricher import (
    enrich_prompt,
    supports_image_reference,
)
from ai_video_factory.infrastructure.memory.errors import CharacterMemoryError
from ai_video_factory.infrastructure.memory.validator import PASS_THRESHOLD, AppearanceValidator

__all__ = [
    "PASS_THRESHOLD",
    "AppearanceValidator",
    "CharacterMemoryEngine",
    "CharacterMemoryError",
    "MemoryResult",
    "adopt_references",
    "derive_memory",
    "enrich_prompt",
    "first_image_for",
    "merge_memory",
    "supports_image_reference",
]
