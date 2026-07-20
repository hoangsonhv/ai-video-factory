"""Tests for the visual continuity engine: bibles, context, prompts, scoring."""

from __future__ import annotations

import pytest

from ai_video_factory.domain.value_objects.character_library import (
    CharacterLibrary,
    CharacterProfile,
    NormalizedAppearance,
    NormalizedOutfit,
)
from ai_video_factory.domain.value_objects.continuity import (
    CharacterBible,
    CharacterBibleEntry,
    PromptScore,
    WorldBible,
)
from ai_video_factory.domain.value_objects.movie import Location, Movie
from ai_video_factory.domain.value_objects.storyboard import Storyboard, StoryboardShot
from ai_video_factory.infrastructure.continuity.bibles import (
    build_character_bible,
    build_world_bible,
)
from ai_video_factory.infrastructure.continuity.context import build_visual_context
from ai_video_factory.infrastructure.continuity.engine import VisualContinuityEngine
from ai_video_factory.infrastructure.continuity.errors import ContinuityError
from ai_video_factory.infrastructure.continuity.scorer import score_prompt


def _library() -> CharacterLibrary:
    return CharacterLibrary(
        characters=(
            CharacterProfile(
                id="lin_tian",
                master_prompt="Lâm Thiên, long black hair",
                negative_prompt="inconsistent face",
                appearance=NormalizedAppearance(
                    hair="long black hair", eyes="golden eyes", face="sharp jaw", body="lean"
                ),
                outfit=NormalizedOutfit(clothes="white silk robe", accessories="jade pendant"),
            ),
        )
    )


def _movie() -> Movie:
    return Movie(
        title="Tu Tiên",
        genre="cultivation",
        style="cinematic",
        duration=60,
        locations=(Location(id="cliff", name="Cliff", description="sunrise over a stormy sea"),),
    )


def _storyboard(shots: int = 4, scenes: int = 2) -> Storyboard:
    entries: list[StoryboardShot] = []
    elapsed = 0.0
    per_scene = shots // scenes
    for scene_id in range(1, scenes + 1):
        for order in range(1, per_scene + 1):
            entries.append(
                StoryboardShot(
                    id=len(entries) + 1,
                    scene_id=scene_id,
                    order=order,
                    duration=3,
                    camera="medium shot",
                    character="lin_tian",
                    action=f"action {len(entries) + 1}",
                    expression="resolve",
                    environment="embers drifting",
                    lighting="hard key from the left",
                    subtitle=f"line {len(entries) + 1}",
                    speech_start=elapsed,
                    speech_end=elapsed + 3,
                )
            )
            elapsed += 3
    return Storyboard(
        title="Tu Tiên", style="cinematic", total_duration=elapsed, shots=tuple(entries)
    )


def _bibles() -> tuple[CharacterBible, WorldBible]:
    return build_character_bible(_library(), _movie()), build_world_bible(_movie())


# --- bibles ----------------------------------------------------------------


def test_the_character_bible_splits_identity_from_wardrobe() -> None:
    bible = build_character_bible(_library(), _movie())
    entry = bible.characters[0]

    assert entry.id == "lin_tian"
    assert "long black hair" in entry.appearance
    assert entry.wardrobe == "white silk robe"
    assert entry.signature_props == "jade pendant"
    assert "inconsistent face" in entry.negative_prompt


def test_the_character_bible_takes_the_name_from_the_movie() -> None:
    movie = Movie.model_validate(
        {**_movie().model_dump(), "characters": [{"id": "lin_tian", "name": "Lâm Thiên"}]}
    )

    bible = build_character_bible(_library(), movie)

    assert bible.characters[0].name == "Lâm Thiên"


def test_the_world_bible_reads_the_locations() -> None:
    world = build_world_bible(_movie())

    assert world.title == "Tu Tiên"
    assert world.style == "cinematic"
    assert world.locations[0].id == "cliff"
    assert world.locations[0].description == "sunrise over a stormy sea"


def test_a_location_description_is_not_mistaken_for_a_palette() -> None:
    """Concatenating every location into `palette` put five places, four of
    them wrong, into every prompt the bible fed."""
    world = build_world_bible(_movie())

    assert world.palette == ""
    assert world.lighting == ""


def test_the_world_bible_invents_nothing_it_was_not_given() -> None:
    """A thin bible is an honest signal that the upstream data was thin."""
    world = build_world_bible(Movie(title="t", duration=10))

    assert world.palette == ""
    assert world.era == ""
    assert world.weather == ""
    assert world.negative_prompt  # only the film-wide negatives are constant


def test_a_bible_lookup_is_case_insensitive() -> None:
    bible, world = _bibles()

    assert bible.get("LIN_TIAN") is not None
    assert world.location("CLIFF") is not None


# --- visual context --------------------------------------------------------


def test_every_shot_gets_a_context() -> None:
    bible, world = _bibles()

    document = build_visual_context(_storyboard(), bible, world)

    assert len(document.shots) == 4
    assert [c.shot_id for c in document.shots] == [1, 2, 3, 4]


def test_a_context_knows_the_shots_either_side() -> None:
    bible, world = _bibles()

    contexts = build_visual_context(_storyboard(), bible, world).shots

    assert contexts[1].previous_shot.shot_id == 1
    assert contexts[1].current_shot.shot_id == 2
    assert contexts[1].next_shot.shot_id == 3


def test_the_first_shot_has_no_previous_and_the_last_no_next() -> None:
    bible, world = _bibles()

    contexts = build_visual_context(_storyboard(), bible, world).shots

    assert not contexts[0].previous_shot.exists
    assert not contexts[-1].next_shot.exists


def test_a_scene_opening_is_recognised() -> None:
    """Continuity must not be asserted across a scene cut."""
    bible, world = _bibles()

    contexts = build_visual_context(_storyboard(), bible, world).shots

    assert contexts[0].is_scene_opening  # first shot of scene 1
    assert contexts[2].is_scene_opening  # first shot of scene 2
    assert not contexts[1].is_scene_opening


def test_continuity_is_carried_within_a_scene() -> None:
    bible, world = _bibles()

    contexts = build_visual_context(_storyboard(), bible, world).shots

    assert "unchanged from the previous shot" in contexts[1].lighting_continuity
    assert "unchanged since the previous shot" in contexts[1].character_state


def test_continuity_is_not_asserted_across_a_scene_cut() -> None:
    bible, world = _bibles()

    contexts = build_visual_context(_storyboard(), bible, world).shots

    assert "unchanged" not in contexts[2].lighting_continuity


def test_the_scene_goal_is_read_from_the_scenes_own_shots() -> None:
    bible, world = _bibles()

    contexts = build_visual_context(_storyboard(), bible, world).shots

    assert "action 1" in contexts[0].scene_goal
    assert "line 1" in contexts[0].scene_goal


# --- prompt composition ----------------------------------------------------


def test_the_score_is_not_tautological() -> None:
    """Scoring the empty string must fail; otherwise it measures nothing."""
    bible, world = _bibles()
    context = build_visual_context(_storyboard(), bible, world).shots[1]

    score = score_prompt("", context, bible, world)

    assert score.total == 0
    assert score.issues


def test_the_total_is_the_mean_of_the_dimensions() -> None:
    score = PromptScore(
        shot_id=1,
        character_consistency=100,
        environment_consistency=50,
        style_consistency=100,
        story_continuity=100,
        camera_continuity=100,
    )

    assert score.total == 90
    assert score.passed(90)
    assert not score.passed(91)


# --- the engine ------------------------------------------------------------


def test_the_engine_produces_one_prompt_per_shot() -> None:
    bible, world = _bibles()

    result = VisualContinuityEngine().run(_storyboard(), bible, world)

    assert len(result.prompts) == 4
    assert [prompt.scene_number for prompt in result.prompts] == [1, 2, 3, 4]


def test_the_engine_scores_every_prompt() -> None:
    bible, world = _bibles()

    result = VisualContinuityEngine().run(_storyboard(), bible, world)

    assert len(result.scores.scores) == 4
    assert result.scores.threshold == 90


def test_a_failing_prompt_is_reported_rather_than_looped_over() -> None:
    """The prompt is written once; a shortfall is named, not re-rolled.

    Escalation was removed with the prompt-builder rewrite: restating a
    section more insistently is exactly the duplicated fragment the builder
    now refuses to emit.
    """
    bible, world = _bibles()

    result = VisualContinuityEngine(threshold=100).run(_storyboard(), bible, world)

    assert all(score.attempts == 1 for score in result.scores.scores)
    unreachable = [score for score in result.scores.scores if score.total < 100]
    assert unreachable
    assert result.scores.failing  # honestly reported
    assert all(score.issues for score in unreachable)  # and the cause is named


def test_a_passing_prompt_is_not_recomposed() -> None:
    bible, world = _bibles()

    result = VisualContinuityEngine(threshold=0).run(_storyboard(), bible, world)

    assert all(score.attempts == 1 for score in result.scores.scores)


def test_the_prompts_keep_the_existing_image_prompt_shape() -> None:
    """Schema-compatible with image_prompts.json so a later sprint can wire it."""
    bible, world = _bibles()

    prompt = VisualContinuityEngine().run(_storyboard(), bible, world).prompts[0]

    assert prompt.aspect_ratio == "9:16"
    assert prompt.negative_prompt
    assert prompt.camera
    assert prompt.character_reference


def test_an_empty_storyboard_is_rejected_with_guidance() -> None:
    bible, world = _bibles()

    with pytest.raises(ContinuityError, match="run `storyboard`"):
        VisualContinuityEngine().run(Storyboard(title="t"), bible, world)


def test_the_engine_is_deterministic() -> None:
    bible, world = _bibles()
    storyboard = _storyboard()

    first = VisualContinuityEngine().run(storyboard, bible, world)
    second = VisualContinuityEngine().run(storyboard, bible, world)

    assert [p.prompt for p in first.prompts] == [p.prompt for p in second.prompts]


def test_a_hand_edited_bible_reaches_the_prompt() -> None:
    """Editing character_bible.json must actually change the output."""
    _, world = _bibles()
    edited = CharacterBible(
        characters=(
            CharacterBibleEntry(
                id="lin_tian",
                name="Lâm Thiên",
                appearance="silver hair, violet eyes",
                wardrobe="obsidian battle robe",
            ),
        )
    )

    result = VisualContinuityEngine().run(_storyboard(), edited, world)

    assert "obsidian battle robe" in result.prompts[0].prompt
    assert "silver hair" in result.prompts[0].prompt
