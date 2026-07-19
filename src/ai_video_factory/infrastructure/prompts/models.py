"""Value models for the prompt engine."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class PromptValidation(BaseModel):
    """Result of validating a single prompt template."""

    model_config = ConfigDict(frozen=True)

    name: str
    required_variables: list[str]
