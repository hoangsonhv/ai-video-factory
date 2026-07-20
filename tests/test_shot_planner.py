"""Tests for the shot planner: coverage rules, distribution, portrait prevention."""

from __future__ import annotations

from collections import Counter

import pytest

from ai_video_factory.domain.value_objects.continuity import (
    CharacterBible,
    CharacterBibleEntry,
    LocationEntry,
    WorldBible,
)
from ai_video_factory.domain.value_objects.director import DirectedMovie, DirectedScene
from ai_video_factory.domain.value_objects.movie import Scene
from ai_video_factory.domain.value_objects.shot_plan import (
    CLOSE_SHOTS,
    WIDE_SHOTS,
    CameraDistance,
    EnvironmentVisibility,
    Lens,
    LightingStyle,
    PlannedShot,
    SceneKind,
    ShotType,
    VisibleBody,
)
from ai_video_factory.domain.value_objects.storyboard import Storyboard, StoryboardShot
from ai_video_factory.infrastructure.planner.classifier import classify_scene
from ai_video_factory.infrastructure.planner.distribution import measure, rebalance
from ai_video_factory.infrastructure.planner.engine import ShotPlanningEngine
from ai_video_factory.infrastructure.planner.environment import build_environment
from ai_video_factory.infrastructure.planner.errors import PlannerError
from ai_video_factory.infrastructure.planner.framing import lens_for, lighting_for
from ai_video_factory.infrastructure.planner.planner import ShotPlanner
from ai_video_factory.infrastructure.planner.statistics import build_statistics

# --- fixtures --------------------------------------------------------------


def _shot(shot_id: int, scene_id: int, order: int, **overrides: str) -> StoryboardShot:
    return StoryboardShot(
        id=shot_id,
        scene_id=scene_id,
        order=order,
        duration=3,
        character=overrides.get("character", "lin_tian"),
        action=overrides.get("action", "ride a motorcycle"),
        expression=overrides.get("expression", "resolve"),
        environment=overrides.get("environment", "neon signs blurring past"),
        lighting=overrides.get("lighting", "cool blue neon"),
        camera_motion=overrides.get("camera_motion", "static"),
        camera="medium shot",
    )


def _storyboard(scenes: int = 10, per_scene: int = 3, **overrides: str) -> Storyboard:
    shots: list[StoryboardShot] = []
    for scene_id in range(1, scenes + 1):
        for order in range(1, per_scene + 1):
            shots.append(_shot(len(shots) + 1, scene_id, order, **overrides))
    return Storyboard(title="Tu Tien", style="cinematic", shots=tuple(shots))


def _bibles() -> tuple[CharacterBible, WorldBible]:
    return (
        CharacterBible(
            characters=(
                CharacterBibleEntry(
                    id="lin_tian",
                    name="Lam Thien",
                    appearance="long black hair",
                    wardrobe="white robe",
                    negative_prompt="blurry, low quality",
                ),
            )
        ),
        WorldBible(
            title="Tu Tien",
            genre="Fantasy",
            style="cinematic",
            palette="neon",
            art_direction="cinematic",
            negative_prompt="blurry, watermark",
            locations=(
                LocationEntry(
                    id="city",
                    name="City",
                    description="A neon metropolis at night, with wet asphalt",
                    weather="light rain",
                    props="street stalls",
                ),
            ),
        ),
    )


def _movie(scenes: int = 10, **scene_overrides: str) -> DirectedMovie:
    return DirectedMovie(
        title="Tu Tien",
        duration=90,
        scenes=tuple(
            DirectedScene(
                id=scene_id,
                duration=9,
                location=scene_overrides.get("location", "city"),
                characters=("lin_tian",),
                action=scene_overrides.get("action", "ride motorcycle"),
                emotion=scene_overrides.get("emotion", "determined"),
                dialogue=scene_overrides.get("dialogue", ""),
            )
            for scene_id in range(1, scenes + 1)
        ),
    )


def _planned(**overrides: object) -> PlannedShot:
    base: dict[str, object] = {
        "shot_id": 1,
        "scene_id": 1,
        "shot_type": ShotType.WIDE,
        "environment_visibility": EnvironmentVisibility(background="a street"),
    }
    base.update(overrides)
    return PlannedShot(**base)  # type: ignore[arg-type]


# --- scene classification --------------------------------------------------


def test_the_first_scene_of_the_film_is_always_an_opening() -> None:
    scene = Scene(id=1, duration=9, action="fight the guards")

    assert classify_scene(scene, (), is_first_scene=True) is SceneKind.OPENING


def test_a_fight_is_recognised_as_combat() -> None:
    scene = Scene(id=2, duration=9, action="draw sword and strike the demon")

    assert classify_scene(scene, ()) is SceneKind.COMBAT


def test_combat_outranks_movement() -> None:
    """A fight covered as generic movement loses the geography that reads it."""
    scene = Scene(id=2, duration=9, action="run in and strike")

    assert classify_scene(scene, ()) is SceneKind.COMBAT


def test_two_people_talking_is_a_conversation() -> None:
    scene = Scene(
        id=2,
        duration=9,
        characters=("a", "b"),
        dialogue="Where have you been?",
        action="hand over item",
    )

    assert classify_scene(scene, ()) is SceneKind.CONVERSATION


def test_a_line_shouted_mid_chase_is_not_a_conversation() -> None:
    scene = Scene(
        id=2,
        duration=9,
        characters=("a", "b"),
        dialogue="Go!",
        action="run from the guards",
    )

    assert classify_scene(scene, ()) is SceneKind.ACTION


def test_a_scene_with_nothing_distinguishing_it_defaults_to_action() -> None:
    """The default keeps the character in a visible world, not in a portrait."""
    scene = Scene(id=2, duration=9)

    assert classify_scene(scene, ()) is SceneKind.ACTION


# --- the sprint's shot-type rules ------------------------------------------


def test_the_opening_scene_opens_on_an_establishing_shot() -> None:
    plan = ShotPlanner().plan(_storyboard(), _movie(), _bibles()[1])

    assert plan.shots[0].shot_type is ShotType.ESTABLISHING


def test_a_combat_scene_opens_full_body() -> None:
    board = _storyboard(scenes=3, per_scene=3)
    movie = _movie(scenes=3, action="draw sword and strike")
    plan = ShotPlanner().plan(board, movie, _bibles()[1])

    combat = [s for s in plan.shots if plan.scene_kinds[s.scene_id] is SceneKind.COMBAT]
    openings = [s for s in combat if s.shot_id % 3 == 1]
    assert openings
    assert all(shot.shot_type is ShotType.FULL_BODY for shot in openings)


def test_an_emotional_scene_reaches_a_close_up() -> None:
    board = _storyboard(scenes=3, per_scene=3, expression="grief")
    movie = _movie(scenes=3, action="weep", emotion="grief")
    plan = ShotPlanner().plan(board, movie, _bibles()[1])

    assert any(shot.shot_type in CLOSE_SHOTS for shot in plan.shots)


def test_a_conversation_scene_is_covered_in_mediums() -> None:
    board = _storyboard(scenes=3, per_scene=3, action="hand over the item")
    movie = _movie(scenes=3, action="talk", dialogue="Where have you been?")
    movie = movie.model_copy(
        update={
            "scenes": tuple(
                scene.model_copy(update={"characters": ("lin_tian", "other")})
                for scene in movie.scenes
            )
        }
    )
    plan = ShotPlanner().plan(board, movie, _bibles()[1])

    conversation = [s for s in plan.shots if plan.scene_kinds[s.scene_id] is SceneKind.CONVERSATION]
    assert conversation
    assert any(shot.shot_type is ShotType.MEDIUM for shot in conversation)


# --- the lens rules --------------------------------------------------------


def test_85mm_is_never_the_dominant_lens() -> None:
    plan = ShotPlanner().plan(_storyboard(), _movie(), _bibles()[1])

    counts = Counter(shot.lens for shot in plan.shots)
    assert counts.most_common(1)[0][0] is not Lens.MM85


def test_85mm_is_only_reachable_on_a_close_or_medium_close_shot() -> None:
    plan = ShotPlanner().plan(_storyboard(), _movie(), _bibles()[1])

    for shot in plan.shots:
        if shot.lens is Lens.MM85:
            assert shot.shot_type in (
                ShotType.CLOSE_UP,
                ShotType.EXTREME_CLOSE,
                ShotType.MEDIUM_CLOSE,
            )


def test_a_wide_shot_never_gets_a_portrait_lens() -> None:
    assert lens_for(ShotType.WIDE, 0) is not Lens.MM85
    assert lens_for(ShotType.EXTREME_WIDE, 0) is Lens.MM18


def test_close_shots_alternate_between_the_two_long_lenses() -> None:
    lenses = {lens_for(ShotType.CLOSE_UP, index) for index in range(4)}

    assert lenses == {Lens.MM85, Lens.MM135}


# --- distribution validation ----------------------------------------------


def test_a_film_of_nothing_but_close_ups_is_invalid() -> None:
    report = measure([ShotType.CLOSE_UP] * 10)

    assert not report.valid
    assert any("close" in issue for issue in report.issues)


def test_the_distribution_bounds_are_all_reported_by_name() -> None:
    report = measure([ShotType.CLOSE_UP] * 10)

    joined = " ".join(report.issues)
    assert "close" in joined
    assert "medium" in joined
    assert "wide" in joined
    assert "establishing" in joined


def test_an_invalid_film_is_rebalanced_until_it_is_valid() -> None:
    sizes = [ShotType.CLOSE_UP] * 20
    kinds = [SceneKind.ACTION] * 20
    openings = [index % 4 == 0 for index in range(20)]

    result = rebalance(sizes, kinds, openings)

    assert measure(result.sizes).valid
    assert result.notes


def test_rebalancing_never_trades_away_a_mandated_shot() -> None:
    """Demoting the size a scene kind requires would break the rule itself."""
    sizes = [ShotType.CLOSE_UP] * 12
    kinds = [SceneKind.EMOTION] * 6 + [SceneKind.ACTION] * 6
    openings = [index % 3 == 0 for index in range(12)]

    result = rebalance(sizes, kinds, openings)

    emotional_openings = [
        result.sizes[index]
        for index in range(6)
        if openings[index] and kinds[index] is SceneKind.EMOTION
    ]
    assert all(size is ShotType.CLOSE_UP for size in emotional_openings)


def test_the_real_shaped_film_lands_inside_every_bound() -> None:
    plan = ShotPlanner().plan(_storyboard(), _movie(), _bibles()[1])

    assert plan.distribution.valid, plan.distribution.issues
    assert plan.distribution.close_pct <= 20.0
    assert 20.0 <= plan.distribution.medium_pct <= 35.0
    assert plan.distribution.wide_pct >= 40.0
    assert plan.distribution.establishing_pct >= 5.0


def test_a_rebalanced_shot_says_so_in_its_reason() -> None:
    plan = ShotPlanner().plan(_storyboard(), _movie(), _bibles()[1])

    if plan.replans:
        adjusted = [shot for shot in plan.shots if "adjusted" in shot.reason]
        assert adjusted


# --- environment visibility ------------------------------------------------


def test_every_shot_states_something_at_some_depth() -> None:
    plan = ShotPlanner().plan(_storyboard(), _movie(), _bibles()[1])

    for shot in plan.shots:
        assert not shot.environment_visibility.is_empty


def test_the_three_depths_are_derived_from_the_story_not_invented() -> None:
    _bible, world = _bibles()
    shot = _shot(1, 1, 1, environment="fog drifting across the ground")
    scene = Scene(id=1, duration=9, location="city")

    visibility = build_environment(shot, scene, world, ShotType.WIDE)

    assert "metropolis" in visibility.background
    assert "fog" in visibility.midground
    assert visibility.foreground


def test_a_shot_stating_nothing_anywhere_is_rejected() -> None:
    """That shot is exactly the one that returns as a portrait on a backdrop."""
    board = Storyboard(
        title="empty",
        shots=(StoryboardShot(id=1, scene_id=1, order=1, duration=3, action="stand", lighting=""),),
    )

    with pytest.raises(PlannerError, match="foreground, midground or background"):
        ShotPlanner().plan(board, None, WorldBible())


def test_a_close_shot_still_keeps_something_behind_the_subject() -> None:
    _bible, world = _bibles()
    shot = _shot(1, 1, 1, environment="swirling fog")
    scene = Scene(id=1, duration=9, location="city")

    visibility = build_environment(shot, scene, world, ShotType.CLOSE_UP)

    assert visibility.background


# --- portrait prevention ---------------------------------------------------


def test_a_colour_is_not_mistaken_for_a_time_of_day() -> None:
    """ "golden" alone made a midnight cemetery read as golden hour."""
    assert lighting_for("a bright golden glow from a phone screen") is not LightingStyle.GOLDEN_HOUR


def test_golden_hour_is_still_recognised_when_it_is_meant() -> None:
    assert lighting_for("warm sunset over the rooftops") is LightingStyle.GOLDEN_HOUR


def test_the_environment_can_supply_the_lighting_the_shot_did_not() -> None:
    assert lighting_for("a phone glow swirling fog") is LightingStyle.VOLUMETRIC


# --- statistics ------------------------------------------------------------


def test_the_statistics_carry_all_four_histograms() -> None:
    plan = ShotPlanner().plan(_storyboard(), _movie(), _bibles()[1])

    statistics = build_statistics(plan)

    assert statistics.total == len(plan.shots)
    assert statistics.shot_types
    assert statistics.lenses
    assert statistics.cameras
    assert statistics.body_visibility
    assert sum(statistics.shot_types.values()) == statistics.total


def test_the_statistics_agree_with_the_plans_own_distribution() -> None:
    plan = ShotPlanner().plan(_storyboard(), _movie(), _bibles()[1])

    assert build_statistics(plan).distribution.valid == plan.distribution.valid


# --- the acceptance criterion ----------------------------------------------


def test_a_thirty_shot_movie_does_not_come_back_as_mostly_portraits() -> None:
    """The sprint's acceptance criterion, stated as a test."""
    plan = ShotPlanner().plan(_storyboard(scenes=10, per_scene=3), _movie(), _bibles()[1])

    assert len(plan.shots) == 30
    close = sum(1 for shot in plan.shots if shot.shot_type in CLOSE_SHOTS)
    wide = sum(1 for shot in plan.shots if shot.shot_type in WIDE_SHOTS)
    assert close <= 6
    assert wide >= 12
    assert wide > close


def test_wide_and_full_body_dominate_an_action_film() -> None:
    board = _storyboard(scenes=10, per_scene=3)
    movie = _movie(scenes=10, action="ride and chase through traffic")

    plan = ShotPlanner().plan(board, movie, _bibles()[1])

    wide = sum(1 for shot in plan.shots if shot.shot_type in WIDE_SHOTS)
    assert wide >= len(plan.shots) * 0.4


def test_most_shots_show_more_than_a_head() -> None:
    plan = ShotPlanner().plan(_storyboard(), _movie(), _bibles()[1])

    heads = sum(1 for shot in plan.shots if shot.visible_body is VisibleBody.HEAD_AND_SHOULDERS)
    assert heads < len(plan.shots) / 2


# --- determinism and the whole stage ---------------------------------------


def test_planning_the_same_film_twice_gives_the_same_plan() -> None:
    first = ShotPlanner().plan(_storyboard(), _movie(), _bibles()[1])
    second = ShotPlanner().plan(_storyboard(), _movie(), _bibles()[1])

    assert first.model_dump() == second.model_dump()


def test_the_engine_produces_one_prompt_per_shot() -> None:
    bible, world = _bibles()
    board = _storyboard()

    result = ShotPlanningEngine().run(board, bible, world, _movie())

    assert len(result.prompts) == len(board.shots)
    assert all(prompt.prompt for prompt in result.prompts)


def test_the_prompts_keep_the_existing_image_prompt_shape() -> None:
    bible, world = _bibles()

    prompt = ShotPlanningEngine().run(_storyboard(), bible, world, _movie()).prompts[0]

    assert prompt.scene_number == 1
    assert prompt.aspect_ratio == "9:16"
    assert prompt.camera
    assert prompt.negative_prompt
    assert prompt.environment


def test_source_text_overruled_by_the_plan_is_reported() -> None:
    """Silently rewriting a writer's words would hide the conflict."""
    bible, world = _bibles()
    board = _storyboard(action="close-up on the rider")

    result = ShotPlanningEngine().run(board, bible, world, _movie())

    assert result.sanitized


def test_a_storyboard_with_no_shots_is_refused() -> None:
    with pytest.raises(PlannerError, match="no shots"):
        ShotPlanner().plan(Storyboard(title="empty"), None, WorldBible())


def test_a_plan_can_be_built_without_the_directed_movie() -> None:
    """Losing conversation detection beats refusing to run."""
    plan = ShotPlanner().plan(_storyboard(), None, _bibles()[1])

    assert len(plan.shots) == 30
    assert SceneKind.CONVERSATION not in plan.scene_kinds.values()


def test_every_shot_carries_all_sixteen_decisions() -> None:
    plan = ShotPlanner().plan(_storyboard(), _movie(), _bibles()[1])

    for shot in plan.shots:
        assert shot.shot_id and shot.scene_id
        assert shot.purpose
        assert shot.shot_type in set(ShotType)
        assert shot.camera_distance in set(CameraDistance)
        assert shot.camera_angle
        assert shot.lens in set(Lens)
        assert shot.composition
        assert shot.visible_body
        assert shot.camera_motion
        assert shot.focus_subject
        assert not shot.environment_visibility.is_empty
        assert shot.lighting_style
        assert shot.emotion
        assert shot.movement_priority
        assert shot.reason
