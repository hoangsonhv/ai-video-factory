"""Director value objects (domain layer).

The shot plan laid over a movie: each scene is broken into an ordered list of
:class:`Shot` objects — the unit an AI video model actually renders. Pure and
immutable (docs/ai-tool.md §2.1) — no I/O, no vendor SDKs. This is the schema
of ``output/movie_directed.json``.

:class:`DirectedScene` and :class:`DirectedMovie` **extend** the Movie Builder's
models rather than altering them, so ``movie.json`` and every existing stage
keep their exact schema: a directed movie is a movie whose scenes carry shots.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from ai_video_factory.domain.value_objects.movie import Movie, Scene

MIN_SHOT_SECONDS = 2
MAX_SHOT_SECONDS = 5
"""A shot is the span an AI video model renders in one go."""


class Shot(BaseModel):
    """One continuous camera setup within a scene.

    ``video_prompt`` is the composed, ready-to-send prompt for this shot; the
    remaining fields are the plan it was built from, kept so the plan stays
    inspectable and editable.
    """

    model_config = ConfigDict(frozen=True)

    id: int = Field(ge=1)
    duration: int = Field(ge=MIN_SHOT_SECONDS, le=MAX_SHOT_SECONDS)
    camera: str = ""
    camera_motion: str = ""
    lens: str = ""
    framing: str = ""
    subject: str = ""
    action: str = ""
    expression: str = ""
    environment_motion: str = ""
    lighting: str = ""
    transition: str = ""
    video_prompt: str = ""


class DirectedScene(Scene):
    """A scene broken into shots."""

    model_config = ConfigDict(frozen=True)

    shots: tuple[Shot, ...] = ()

    @property
    def is_planned(self) -> bool:
        """Whether the director produced shots for this scene."""
        return bool(self.shots)

    @property
    def shot_seconds(self) -> int:
        """Total planned running time of this scene's shots."""
        return sum(shot.duration for shot in self.shots)


class DirectedMovie(Movie):
    """A movie whose scenes carry shot lists."""

    model_config = ConfigDict(frozen=True)

    scenes: tuple[DirectedScene, ...] = ()

    @property
    def shot_count(self) -> int:
        """Total shots across every scene."""
        return sum(len(scene.shots) for scene in self.scenes)
