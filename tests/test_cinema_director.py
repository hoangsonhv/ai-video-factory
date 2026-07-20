"""Tests for the cinematic director: scene intent, coverage, and the prompt."""

from __future__ import annotations

from collections import Counter

import pytest

from ai_video_factory.domain.value_objects.cinema import (
    CameraAngle,
    Composition,
    Lens,
    LightingSetup,
    ShotType,
    StoryBeat,
)
from ai_video_factory.domain.value_objects.continuity import (
    CharacterBible,
    CharacterBibleEntry,
    WorldBible,
)
from ai_video_factory.domain.value_objects.storyboard import Storyboard, StoryboardShot
from ai_video_factory.infrastructure.cinema.engine import CinematicDirector
from ai_video_factory.infrastructure.cinema.errors import CinemaError
from ai_video_factory.infrastructure.cinema.scene_director import (
    SceneDirector,
    infer_conflict,
    story_beat,
)
from ai_video_factory.infrastructure.cinema.shot_director import ShotDirector
from ai_video_factory.infrastructure.cinema.vocabulary import (
    ACTIVE_VERBS,
    activate,
    choose_lens,
    choose_lighting,
    is_static,
)


def _storyboard(scenes: int = 4, per_scene: int = 3, **overrides: str) -> Storyboard:
    shots: list[StoryboardShot] = []
    for scene_id in range(1, scenes + 1):
        for order in range(1, per_scene + 1):
            shots.append(
                StoryboardShot(
                    id=len(shots) + 1,
                    scene_id=scene_id,
                    order=order,
                    duration=3,
                    character="lin_tian",
                    action=overrides.get("action", f"ride a motorcycle {len(shots) + 1}"),
                    expression=overrides.get("expression", "resolve"),
                    environment=overrides.get("environment", "neon signs blurring past"),
                    lighting=overrides.get("lighting", "cool blue neon"),
                    camera="medium shot",
                    subtitle=f"line {len(shots) + 1}",
                )
            )
    return Storyboard(title="Tu Tiên", style="cinematic", shots=tuple(shots))


def _bibles() -> tuple[CharacterBible, WorldBible]:
    return (
        CharacterBible(
            characters=(
                CharacterBibleEntry(
                    id="lin_tian",
                    name="Lâm Thiên",
                    appearance="long black hair",
                    wardrobe="white robe",
                ),
            )
        ),
        WorldBible(
            title="Tu Tiên",
            style="cinematic",
            palette="neon",
            art_direction="cinematic",
            negative_prompt="inconsistent face, blurry",
        ),
    )


def _direct(storyboard: Storyboard | None = None):
    board = storyboard or _storyboard()
    scenes = SceneDirector().direct(board)
    return board, scenes, ShotDirector().direct(board, scenes)


# --- scene direction -------------------------------------------------------


def test_every_scene_gets_a_purpose_emotion_conflict_and_beat() -> None:
    _board, scenes, _shots = _direct()

    assert len(scenes) == 4
    for scene in scenes:
        assert scene.purpose
        assert scene.emotion
        assert scene.story_beat in set(StoryBeat)


def test_the_beat_follows_the_position_in_the_film() -> None:
    assert story_beat(1, 10) is StoryBeat.SETUP
    assert story_beat(10, 10) is StoryBeat.RESOLUTION
    assert story_beat(4, 10) is StoryBeat.RISING
    assert story_beat(5, 10) is StoryBeat.MIDPOINT


def test_the_purpose_is_grounded_in_what_the_scene_shows() -> None:
    _board, scenes, _shots = _direct()

    assert "ride a motorcycle" in scenes[0].purpose


def test_conflict_is_read_from_the_emotional_register() -> None:
    assert infer_conflict("fear", []) == "survival against a threat"
    assert infer_conflict("rage", []) == "open confrontation"


def test_conflict_falls_back_to_what_the_characters_do() -> None:
    assert infer_conflict("", ["draw sword", "strike"]) == "open confrontation"
    assert infer_conflict("", ["run from the guards"]) == "pursuit"


def test_conflict_is_left_empty_when_nothing_says_it() -> None:
    """Naming a conflict nobody wrote would be invention, not direction."""
    assert infer_conflict("", ["sit"]) == ""


# --- shot coverage ---------------------------------------------------------


def test_every_shot_gets_the_six_required_decisions() -> None:
    _board, _scenes, shots = _direct()

    for shot in shots:
        assert shot.purpose
        assert shot.camera
        assert shot.composition
        assert shot.action
        assert shot.lighting
        assert shot.emotion


def test_a_scene_opens_on_something_that_establishes_it() -> None:
    _board, _scenes, shots = _direct()

    openings = [shot for shot in shots if shot.shot_id in (1, 4, 7, 10)]
    assert all(shot.shot_type is ShotType.ESTABLISHING for shot in openings)


def test_consecutive_scenes_are_not_filmed_identically() -> None:
    """Without a per-scene offset every scene of equal length repeats."""
    _board, _scenes, shots = _direct(_storyboard(scenes=4, per_scene=3))

    scene_one = tuple(s.shot_type for s in shots if s.scene_id == 1)
    scene_two = tuple(s.shot_type for s in shots if s.scene_id == 2)

    assert scene_one != scene_two


def test_the_coverage_uses_more_than_a_couple_of_shot_sizes() -> None:
    _board, _scenes, shots = _direct(_storyboard(scenes=6, per_scene=4))

    assert len({shot.shot_type for shot in shots}) >= 4


def test_the_angles_vary_across_the_film() -> None:
    _board, _scenes, shots = _direct(_storyboard(scenes=6, per_scene=4))

    assert len({shot.camera_angle for shot in shots}) >= 3


def test_an_establishing_shot_is_covered_from_the_air() -> None:
    _board, _scenes, shots = _direct()

    establishing = next(s for s in shots if s.shot_type is ShotType.ESTABLISHING)
    assert establishing.camera_angle is CameraAngle.DRONE


def test_emotion_pulls_the_camera_off_eye_level() -> None:
    board = _storyboard(expression="fear")
    _b, _scenes, shots = _direct(board)

    non_establishing = [s for s in shots if s.shot_type is not ShotType.ESTABLISHING]
    assert all(shot.camera_angle is CameraAngle.HIGH_ANGLE for shot in non_establishing)


# --- the 85mm rule ---------------------------------------------------------


def test_85mm_is_never_the_default_lens() -> None:
    """The whole point of the rule: it must not dominate the film."""
    _board, _scenes, shots = _direct(_storyboard(scenes=8, per_scene=4))

    counts = Counter(shot.lens for shot in shots)
    assert counts.most_common(1)[0][0] is not Lens.MM85


def test_85mm_is_only_reachable_on_a_close_shot() -> None:
    _board, _scenes, shots = _direct(_storyboard(scenes=8, per_scene=4))

    for shot in shots:
        if shot.lens is Lens.MM85:
            assert shot.shot_type in (ShotType.CLOSE_UP, ShotType.EXTREME_CLOSE_UP)


def test_a_wide_shot_never_gets_a_portrait_lens() -> None:
    assert choose_lens(ShotType.WIDE, 0) is not Lens.MM85
    assert choose_lens(ShotType.ESTABLISHING, 0) is Lens.MM24


def test_close_ups_alternate_between_the_two_long_lenses() -> None:
    """Alternation is what stops one lens quietly becoming the house default."""
    lenses = {choose_lens(ShotType.CLOSE_UP, index) for index in range(4)}

    assert lenses == {Lens.MM85, Lens.MM135}


def test_every_lens_in_the_vocabulary_is_reachable() -> None:
    _board, _scenes, shots = _direct(_storyboard(scenes=8, per_scene=4))

    assert len({shot.lens for shot in shots}) >= 4


# --- action ----------------------------------------------------------------


def test_a_static_description_is_replaced_with_an_active_one() -> None:
    assert is_static("standing")
    assert activate("standing", 0) in ACTIVE_VERBS
    assert activate("", 3) in ACTIVE_VERBS


def test_an_action_that_already_has_a_verb_is_kept() -> None:
    """The director's own words beat a generic substitute."""
    assert activate("drawing a celestial sword", 0) == "drawing a celestial sword"


def test_no_directed_shot_is_left_static() -> None:
    board = _storyboard(action="standing")
    _b, _scenes, shots = _direct(board)

    assert all(not is_static(shot.action) for shot in shots)


# --- lighting and blocking -------------------------------------------------


def test_the_lighting_setup_is_read_from_the_description() -> None:
    assert choose_lighting("golden hour over the sea") is LightingSetup.SUNSET
    assert choose_lighting("neon at midnight") is LightingSetup.NIGHT
    assert choose_lighting("embers drifting") is LightingSetup.FIRE
    assert choose_lighting("moonlit rooftop") is LightingSetup.MOONLIGHT
    assert choose_lighting("light shafts through fog") is LightingSetup.VOLUMETRIC


def test_lighting_falls_back_to_a_key_light() -> None:
    assert choose_lighting("") is LightingSetup.KEY


def test_every_shot_is_blocked() -> None:
    _board, _scenes, shots = _direct()

    for shot in shots:
        assert shot.blocking.character_position
        assert shot.blocking.movement_path
        assert shot.blocking.summary


def test_a_travelling_action_gets_a_travelling_path() -> None:
    _board, _scenes, shots = _direct(_storyboard(action="running through the market"))

    assert any("crossing frame" in shot.blocking.movement_path for shot in shots)


def test_a_close_up_holds_still_unless_the_action_travels() -> None:
    _board, _scenes, shots = _direct(_storyboard(action="whispering", scenes=8, per_scene=4))

    close_ups = [s for s in shots if s.shot_type is ShotType.CLOSE_UP]
    assert close_ups
    assert all("held in place" in shot.blocking.movement_path for shot in close_ups)


# --- the composed prompt ---------------------------------------------------


def test_the_prompt_carries_every_part_of_the_formula() -> None:
    board = _storyboard()
    bible, world = _bibles()
    result = CinematicDirector().run(board, bible, world)

    prompt = result.prompts[4].prompt
    for section in (
        "Character",
        "Action",
        "Environment",
        "Camera",
        "Lighting",
        "Composition",
        "Style",
        "Negative Prompt",
    ):
        assert f"{section}:" in prompt, section


def test_one_prompt_and_one_direction_per_shot() -> None:
    board = _storyboard()
    bible, world = _bibles()

    result = CinematicDirector().run(board, bible, world)

    assert len(result.prompts) == len(board.shots)
    assert len(result.direction.shots) == len(board.shots)


def test_the_prompts_keep_the_existing_image_prompt_shape() -> None:
    board = _storyboard()
    bible, world = _bibles()

    prompt = CinematicDirector().run(board, bible, world).prompts[0]

    assert prompt.aspect_ratio == "9:16"
    assert prompt.camera
    assert prompt.negative_prompt


def test_the_director_is_deterministic() -> None:
    board = _storyboard()
    bible, world = _bibles()

    first = CinematicDirector().run(board, bible, world)
    second = CinematicDirector().run(board, bible, world)

    assert [p.prompt for p in first.prompts] == [p.prompt for p in second.prompts]


def test_an_empty_storyboard_is_rejected_with_guidance() -> None:
    with pytest.raises(CinemaError, match="run `storyboard`"):
        CinematicDirector().direct(Storyboard(title="t"))


def test_a_direction_can_be_looked_up_by_id() -> None:
    board = _storyboard()
    direction = CinematicDirector().direct(board)

    assert direction.shot(1) is not None
    assert direction.scene(1) is not None
    assert direction.shot(999) is None


def test_the_composition_vocabulary_is_used() -> None:
    _board, _scenes, shots = _direct(_storyboard(scenes=8, per_scene=4))

    used = {shot.composition for shot in shots}
    assert len(used) >= 3
    assert used <= set(Composition)
