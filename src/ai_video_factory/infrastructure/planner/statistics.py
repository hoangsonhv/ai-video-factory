"""Count how the finished plan is distributed (pure, no I/O).

The histograms are the sprint's evidence, not decoration: "a 30-shot movie must
not produce mostly portraits" is a claim about a distribution, and this is what
makes it checkable at a glance instead of by opening thirty images.
"""

from __future__ import annotations

from collections import Counter

from ai_video_factory.domain.value_objects.shot_plan import ShotPlan, ShotStatistics
from ai_video_factory.infrastructure.planner.distribution import measure


def _histogram(values: list[str]) -> dict[str, int]:
    """Counts, largest first, so the dominant choice is the first line."""
    counts = Counter(values)
    return {name: count for name, count in counts.most_common()}


def build_statistics(plan: ShotPlan) -> ShotStatistics:
    """Count the plan across every axis the sprint asks about."""
    shots = plan.shots
    return ShotStatistics(
        total=len(shots),
        shot_types=_histogram([shot.shot_type.value for shot in shots]),
        lenses=_histogram([shot.lens.value for shot in shots]),
        cameras=_histogram([shot.camera_angle.value for shot in shots]),
        body_visibility=_histogram([shot.visible_body.value for shot in shots]),
        distribution=measure([shot.shot_type for shot in shots]),
    )
