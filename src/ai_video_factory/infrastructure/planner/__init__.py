"""Shot planner stage (infrastructure).

Decides how every frame of the film is composed — size, distance, angle, lens,
composition, visible body, environment depth, light and motion — validates the
coverage as a distribution, and rebuilds every image prompt from that plan.

Deterministic and offline: no provider is contacted, and no video or compose
stage is touched.
"""

from ai_video_factory.infrastructure.planner.classifier import classify_scene, classify_scenes
from ai_video_factory.infrastructure.planner.distribution import measure, rebalance
from ai_video_factory.infrastructure.planner.engine import PlanResult, ShotPlanningEngine
from ai_video_factory.infrastructure.planner.environment import build_environment
from ai_video_factory.infrastructure.planner.errors import PlannerError
from ai_video_factory.infrastructure.planner.planner import ShotPlanner
from ai_video_factory.infrastructure.planner.statistics import build_statistics

__all__ = [
    "PlanResult",
    "PlannerError",
    "ShotPlanner",
    "ShotPlanningEngine",
    "build_environment",
    "build_statistics",
    "classify_scene",
    "classify_scenes",
    "measure",
    "rebalance",
]
