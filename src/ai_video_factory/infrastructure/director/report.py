"""Outcome of a direction run (domain-free reporting value)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class DirectionReport(BaseModel):
    """How a direction run went: what was planned, what failed, what it cost."""

    model_config = ConfigDict(frozen=True)

    directed: int = Field(default=0, ge=0)
    failed: int = Field(default=0, ge=0)
    retries: int = Field(default=0, ge=0)
    skipped: int = Field(default=0, ge=0)
    failed_scene_ids: tuple[int, ...] = ()

    @property
    def is_complete(self) -> bool:
        """Whether every scene ended up with a shot plan."""
        return self.failed == 0

    @property
    def is_partial(self) -> bool:
        """Whether some scenes succeeded and some did not."""
        return self.failed > 0 and self.directed + self.skipped > 0
