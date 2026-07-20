"""Tests for the prompt builder — the single place an image prompt is written."""

from __future__ import annotations

from ai_video_factory.domain.value_objects.continuity import (
    CharacterBible,
    CharacterBibleEntry,
    WorldBible,
)
from ai_video_factory.infrastructure.continuity.prompt_composer import (
    ANTI_PORTRAIT_NEGATIVES,
    EMPTY_SUPERLATIVES,
    MAX_WORDS,
    SECTION_ORDER,
    PromptSource,
    build_prompt,
    find_violations,
    positive_part,
    primary_action,
    strip_framing,
    strip_superlatives,
    word_count,
)


def _bible() -> CharacterBible:
    return CharacterBible(
        characters=(
            CharacterBibleEntry(
                id="lin_tian",
                name="Lam Thien",
                appearance="long black hair",
                wardrobe="white robe",
                negative_prompt="blurry, low quality",
            ),
        )
    )


def _world(**overrides: str) -> WorldBible:
    defaults: dict[str, str] = {
        "title": "Tu Tien",
        "genre": "Fantasy",
        "style": "cinematic",
        "palette": "neon",
        "art_direction": "cinematic film still",
        "negative_prompt": "watermark, blurry",
    }
    defaults.update(overrides)
    return WorldBible(**defaults)


def _source(**overrides: object) -> PromptSource:
    defaults: dict[str, object] = {
        "character_id": "lin_tian",
        "action": "rides a motorcycle",
        "environment": "neon signs blurring past",
        "camera": "wide shot, far, eye level, 24mm",
        "lighting": "neon practical light",
        "composition": "leading lines",
        "allows_close_framing": False,
    }
    defaults.update(overrides)
    return PromptSource(**defaults)  # type: ignore[arg-type]


def _section(prompt: str, label: str) -> str:
    for line in prompt.splitlines():
        if line.startswith(f"{label}:"):
            return line.split(":", 1)[1].strip()
    return ""


# --- section order ---------------------------------------------------------


def test_the_prompt_carries_the_eight_sections_in_order() -> None:
    prompt = build_prompt(_source(), _bible(), _world())

    positions = [prompt.index(f"{label}:") for label in SECTION_ORDER]
    assert positions == sorted(positions)


def test_the_prompt_opens_on_the_character() -> None:
    """Order is what the model weights: open on a face and it draws a face."""
    prompt = build_prompt(_source(), _bible(), _world())

    assert prompt.startswith("Character:")


def test_action_comes_before_environment() -> None:
    prompt = build_prompt(_source(), _bible(), _world())

    assert prompt.index("Action:") < prompt.index("Environment:")


# --- provenance ------------------------------------------------------------


def test_the_character_comes_from_the_bible() -> None:
    prompt = build_prompt(_source(), _bible(), _world())

    character = _section(prompt, "Character")
    assert "Lam Thien" in character
    assert "long black hair" in character
    assert "white robe" in character


def test_an_unknown_character_falls_back_to_its_id_not_to_invention() -> None:
    prompt = build_prompt(_source(character_id="nobody_here"), CharacterBible(), _world())

    assert _section(prompt, "Character") == "nobody here"


def test_the_action_comes_from_the_shot() -> None:
    prompt = build_prompt(_source(action="draws a celestial sword"), _bible(), _world())

    assert _section(prompt, "Action") == "draws a celestial sword"


def test_the_camera_comes_from_the_shot() -> None:
    prompt = build_prompt(
        _source(camera="full body shot, far, low angle, 35mm"), _bible(), _world()
    )

    assert _section(prompt, "Camera") == "full body shot, far, low angle, 35mm"


def test_the_environment_carries_the_world_and_this_frames_own_detail() -> None:
    prompt = build_prompt(_source(environment="swirling fog"), _bible(), _world())

    environment = _section(prompt, "Environment")
    assert "swirling fog" in environment  # the shot's own
    assert "Tu Tien" in environment  # the world bible's


def test_the_character_section_never_takes_the_shots_own_words() -> None:
    """A character re-described per shot is a character that changes per shot."""
    prompt = build_prompt(_source(action="a grey-haired stranger rides past"), _bible(), _world())

    assert "grey-haired" not in _section(prompt, "Character")


# --- exactly one primary action -------------------------------------------


def test_only_the_first_beat_of_an_action_survives() -> None:
    assert primary_action("draws a sword and turns to face them") == "draws a sword"


def test_a_then_clause_is_dropped() -> None:
    assert primary_action("opens the door, then steps inside") == "opens the door"


def test_a_while_clause_is_dropped() -> None:
    assert primary_action("runs while the fog closes in") == "runs"


def test_a_single_action_is_left_alone() -> None:
    assert primary_action("kneels in the ash") == "kneels in the ash"


def test_an_empty_action_stays_empty() -> None:
    assert primary_action("   ") == ""


def test_the_prompt_states_one_action_only() -> None:
    prompt = build_prompt(_source(action="rides in and leaps from the bike"), _bible(), _world())

    assert _section(prompt, "Action") == "rides in"


# --- never portrait-only ---------------------------------------------------


def test_a_non_close_shot_refuses_portrait_framing_in_its_negatives() -> None:
    prompt = build_prompt(_source(allows_close_framing=False), _bible(), _world())

    negatives = _section(prompt, "Negative Prompt")
    assert "portrait" in negatives
    assert "headshot" in negatives


def test_a_close_shot_does_not_refuse_the_framing_it_was_planned_for() -> None:
    prompt = build_prompt(_source(allows_close_framing=True), _bible(), _world())

    assert ANTI_PORTRAIT_NEGATIVES.split(",")[0] not in _section(prompt, "Negative Prompt")


def test_close_up_language_is_stripped_from_a_wide_shot() -> None:
    prompt = build_prompt(_source(action="a close-up of the rider"), _bible(), _world())

    assert "close-up" not in positive_part(prompt).lower()


def test_close_up_language_survives_when_the_shot_is_close() -> None:
    assert strip_framing("a close-up of the rider", allowed=True) == "a close-up of the rider"


def test_the_guard_finds_leaked_framing() -> None:
    assert find_violations("a close-up of his face", allowed=False)


def test_the_guard_ignores_the_negative_section() -> None:
    """The negatives name the banned words on purpose, to refuse them."""
    prompt = build_prompt(_source(), _bible(), _world())

    assert find_violations(prompt, allowed=False) == ()


def test_no_built_prompt_ever_violates_its_own_guard() -> None:
    for action in ("a close-up of his face", "headshot of the rider", "rides on"):
        prompt = build_prompt(_source(action=action), _bible(), _world())
        assert find_violations(prompt, allowed=False) == ()


# --- no duplicated fragments ----------------------------------------------


def test_a_term_repeated_across_sources_appears_once() -> None:
    bible = CharacterBible(
        characters=(
            CharacterBibleEntry(id="a", negative_prompt="blurry, low quality"),
            CharacterBibleEntry(id="b", negative_prompt="blurry, low quality"),
        )
    )
    prompt = build_prompt(_source(character_id="a"), bible, _world(negative_prompt="blurry"))

    assert _section(prompt, "Negative Prompt").count("blurry") == 1


def test_a_term_repeated_across_sections_appears_once() -> None:
    """ "cinematic" arrives as both the style and the art direction."""
    prompt = build_prompt(_source(), _bible(), _world(art_direction="cinematic", style="cinematic"))

    assert prompt.lower().count("cinematic") == 1


# --- no empty superlatives -------------------------------------------------


def test_empty_superlatives_are_removed_by_default() -> None:
    world = _world(art_direction="masterpiece, best quality, 8k, gritty realism")

    prompt = build_prompt(_source(), _bible(), world)

    lowered = prompt.lower()
    for word in ("masterpiece", "best quality", "8k"):
        assert word not in lowered
    assert "gritty realism" in prompt  # the real description survives


def test_superlatives_are_kept_when_explicitly_configured() -> None:
    world = _world(art_direction="masterpiece, gritty realism")

    prompt = build_prompt(_source(), _bible(), world, allow_superlatives=True)

    assert "masterpiece" in prompt


def test_configured_style_words_reach_the_style_section() -> None:
    prompt = build_prompt(
        _source(), _bible(), _world(), style_words=("35mm film grain",), allow_superlatives=True
    )

    assert "35mm film grain" in _section(prompt, "Style")


def test_stripping_superlatives_leaves_everything_else() -> None:
    assert strip_superlatives("8k, moody fog", allowed=False) == "moody fog"


# --- length ----------------------------------------------------------------


def test_a_prompt_stays_under_the_word_limit() -> None:
    world = _world(
        art_direction=", ".join(f"detail {n}" for n in range(200)),
        negative_prompt=", ".join(f"avoid {n}" for n in range(200)),
    )

    prompt = build_prompt(_source(), _bible(), world)

    assert word_count(prompt) <= MAX_WORDS


def test_trimming_never_drops_a_section_label() -> None:
    """A shorter prompt is still a complete prompt."""
    world = _world(negative_prompt=", ".join(f"avoid {n}" for n in range(300)))

    prompt = build_prompt(_source(), _bible(), world)

    for label in SECTION_ORDER:
        assert f"{label}:" in prompt


def test_a_short_prompt_is_left_untrimmed() -> None:
    prompt = build_prompt(_source(), _bible(), _world())

    assert word_count(prompt) < MAX_WORDS
    assert "neon signs blurring past" in prompt


# --- completeness ----------------------------------------------------------


def test_every_section_carries_something_for_a_complete_shot() -> None:
    prompt = build_prompt(_source(), _bible(), _world())

    for label in SECTION_ORDER:
        assert _section(prompt, label), label


def test_an_empty_section_is_omitted_rather_than_left_blank() -> None:
    prompt = build_prompt(_source(composition=""), _bible(), _world())

    assert "Composition:" not in prompt


def test_the_same_input_always_gives_the_same_prompt() -> None:
    first = build_prompt(_source(), _bible(), _world())
    second = build_prompt(_source(), _bible(), _world())

    assert first == second


def test_the_superlative_list_is_the_one_the_sprint_named() -> None:
    for word in ("masterpiece", "best quality", "high quality", "8k", "ultra detailed"):
        assert word in EMPTY_SUPERLATIVES
    assert "award winning" in EMPTY_SUPERLATIVES


def test_a_shared_word_does_not_empty_the_style_section() -> None:
    """Environment is the catch-all; letting it claim first emptied Style.

    Both the art direction and the style say "cinematic", and de-duplication
    is global — so claim order decides which section keeps the word.
    """
    world = _world(style="cinematic", art_direction="cinematic")

    prompt = build_prompt(_source(), _bible(), world)

    assert _section(prompt, "Style")
    assert _section(prompt, "Environment")
