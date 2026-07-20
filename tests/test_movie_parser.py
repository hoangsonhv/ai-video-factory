"""Tests for the movie parser (JSON -> Movie, dedup, schema validation)."""

from __future__ import annotations

import json

import pytest

from ai_video_factory.infrastructure.story.errors import MovieBuildError
from ai_video_factory.infrastructure.story.movie_parser import parse_movie


def _movie_json(**overrides: object) -> str:
    payload = {
        "title": "The Midnight Delivery",
        "genre": "horror",
        "style": "cinematic",
        "duration": 60,
        "characters": [
            {
                "id": "shipper",
                "name": "Nam",
                "gender": "male",
                "age": 22,
                "appearance": {"hair": "short black", "eyes": "brown", "clothes": "raincoat"},
                "personality": "anxious",
                "voice": "young male",
                "negative_prompt": "extra limbs",
            }
        ],
        "locations": [{"id": "cemetery", "name": "Old Cemetery", "description": "foggy"}],
        "scenes": [
            {
                "id": 1,
                "duration": 5,
                "location": "cemetery",
                "characters": ["shipper"],
                "camera": {"shot": "wide shot", "movement": "drone", "lens": "35mm"},
                "action": "walk",
                "emotion": "fear",
                "dialogue": "Có ai không?",
                "image_prompt": "a lone delivery driver in a foggy cemetery",
                "video_prompt": "driver walks slowly forward",
            }
        ],
    }
    payload.update(overrides)
    return json.dumps(payload)


def test_parses_valid_movie() -> None:
    movie = parse_movie(_movie_json(), style="cinematic", genre="horror", duration=60)
    assert movie.title == "The Midnight Delivery"
    assert movie.characters[0].appearance.hair == "short black"
    assert movie.scenes[0].camera.movement == "drone"
    assert movie.scenes[0].dialogue == "Có ai không?"  # Vietnamese preserved


def test_deduplicates_characters_keeping_first_appearance() -> None:
    # Same id twice with DIFFERENT appearance -> the first (fixed) one wins.
    duplicated = json.loads(_movie_json())
    duplicated["characters"].append(
        {
            "id": "shipper",
            "name": "Nam",
            "appearance": {"hair": "long white"},  # must be ignored
        }
    )
    movie = parse_movie(json.dumps(duplicated), style="cinematic", genre="horror", duration=60)
    assert len(movie.characters) == 1
    assert movie.characters[0].appearance.hair == "short black"


def test_injects_missing_style_genre_duration() -> None:
    payload = json.loads(_movie_json())
    del payload["style"]
    del payload["genre"]
    payload["duration"] = 0  # falsy -> replaced
    movie = parse_movie(json.dumps(payload), style="anime", genre="drama", duration=90)
    assert movie.style == "anime"
    assert movie.genre == "drama"
    assert movie.duration == 90


def test_strips_markdown_fences() -> None:
    fenced = f"```json\n{_movie_json()}\n```"
    movie = parse_movie(fenced, style="cinematic", genre="horror", duration=60)
    assert movie.title == "The Midnight Delivery"


def test_invalid_json_raises() -> None:
    with pytest.raises(MovieBuildError, match="invalid JSON"):
        parse_movie("not json {", style="s", genre="g", duration=10)


def test_non_object_raises() -> None:
    with pytest.raises(MovieBuildError, match="JSON object"):
        parse_movie("[1, 2, 3]", style="s", genre="g", duration=10)


def test_schema_violation_raises() -> None:
    payload = json.loads(_movie_json())
    payload["scenes"][0]["duration"] = 0  # invalid (must be > 0)
    with pytest.raises(MovieBuildError, match="schema"):
        parse_movie(json.dumps(payload), style="s", genre="g", duration=10)
