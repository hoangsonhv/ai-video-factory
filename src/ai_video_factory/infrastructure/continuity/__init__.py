"""Visual continuity stage (infrastructure).

Makes consecutive images look like frames of one film: a character bible and a
world bible fix what never changes, a per-shot visual context says what must
carry across each cut, and every image prompt is composed from all of it rather
than from the current shot alone. A scorer checks each prompt and recomposes it
more explicitly when it falls short.

Deterministic and offline — no provider is contacted, no video stage touched.
"""

from ai_video_factory.infrastructure.continuity.bibles import (
    build_character_bible,
    build_world_bible,
)
from ai_video_factory.infrastructure.continuity.context import build_visual_context
from ai_video_factory.infrastructure.continuity.engine import (
    ContinuityResult,
    VisualContinuityEngine,
)
from ai_video_factory.infrastructure.continuity.errors import ContinuityError
from ai_video_factory.infrastructure.continuity.prompt_composer import (
    PromptSource,
    build_prompt,
)
from ai_video_factory.infrastructure.continuity.scorer import PASS_THRESHOLD, score_prompt

__all__ = [
    "PASS_THRESHOLD",
    "ContinuityError",
    "ContinuityResult",
    "PromptSource",
    "VisualContinuityEngine",
    "build_character_bible",
    "build_prompt",
    "build_visual_context",
    "build_world_bible",
    "score_prompt",
]
