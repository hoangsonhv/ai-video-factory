"""Movie / Character / Scene value objects (domain layer).

A structured "movie bible": persistent characters with a fixed appearance, the
locations they inhabit, and an ordered list of cinematic scenes. Pure and
immutable (docs/ai-tool.md §2.1) — no I/O, no vendor SDKs. This is the schema
of ``output/movie.json``.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class Appearance(BaseModel):
    """A character's fixed visual appearance (never changes across scenes)."""

    model_config = ConfigDict(frozen=True)

    hair: str = ""
    eyes: str = ""
    face: str = ""
    body: str = ""
    clothes: str = ""
    accessories: str = ""


class Character(BaseModel):
    """A persistent story character with a stable identity and appearance."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    gender: str = ""
    age: int = Field(default=0, ge=0)
    appearance: Appearance = Field(default_factory=Appearance)
    personality: str = ""
    voice: str = ""
    negative_prompt: str = ""


class Location(BaseModel):
    """A place a scene can take place in."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    description: str = ""


class Camera(BaseModel):
    """The camera language for a scene (shot / movement / lens)."""

    model_config = ConfigDict(frozen=True)

    shot: str = ""
    movement: str = ""
    lens: str = ""


class Scene(BaseModel):
    """One cinematic scene referencing characters and a location."""

    model_config = ConfigDict(frozen=True)

    id: int = Field(ge=1)
    duration: int = Field(gt=0)
    location: str = ""
    characters: tuple[str, ...] = ()
    camera: Camera = Field(default_factory=Camera)
    action: str = ""
    emotion: str = ""
    dialogue: str = ""
    image_prompt: str = ""
    video_prompt: str = ""


class Movie(BaseModel):
    """The full structured movie: characters, locations, and ordered scenes."""

    model_config = ConfigDict(frozen=True)

    title: str = Field(min_length=1)
    genre: str = ""
    style: str = ""
    duration: int = Field(gt=0)
    characters: tuple[Character, ...] = ()
    locations: tuple[Location, ...] = ()
    scenes: tuple[Scene, ...] = ()
