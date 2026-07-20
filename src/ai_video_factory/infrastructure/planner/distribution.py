"""Validate and rebalance the film's coverage (pure, no I/O).

A shot is judged one at a time; a *film* is judged as a distribution. Every
individual close up in the current output is defensible, and the result is
still thirty portraits. These are the bounds that make that impossible, and the
deterministic rebalancing that brings a plan back inside them.

Rebalancing demotes the **least justified** shot first: a close up in a scene
whose kind does not call for one goes before a close up in a scene of grief.
That way the plan converges without destroying the coverage the content asked
for.
"""

from __future__ import annotations

from ai_video_factory.domain.value_objects.shot_plan import (
    CLOSE_SHOTS,
    MEDIUM_SHOTS,
    WIDE_SHOTS,
    DistributionReport,
    SceneKind,
    ShotType,
)
from ai_video_factory.infrastructure.planner.framing import COVERAGE, MANDATED

MAX_CLOSE_PCT = 20.0
MIN_MEDIUM_PCT = 20.0
MAX_MEDIUM_PCT = 35.0
MIN_WIDE_PCT = 40.0
MIN_ESTABLISHING_PCT = 5.0

REPLANS_PER_SHOT = 4
MIN_REPLANS = 12
"""Each pass changes exactly one shot, so the cap has to scale with the film.

A fixed cap silently stopped a badly-skewed 20-shot film half-way — it needed
21 changes and got 12, so an "automatically re-planned" film was still 40%
close ups. The bound is a runaway guard, not a budget.
"""


def _replan_limit(shot_count: int) -> int:
    return max(MIN_REPLANS, REPLANS_PER_SHOT * shot_count)


def _pct(count: int, total: int) -> float:
    return round(100.0 * count / total, 1) if total else 0.0


def measure(shot_types: list[ShotType]) -> DistributionReport:
    """Measure the coverage and name every bound it breaks."""
    total = len(shot_types)
    close = sum(1 for shot in shot_types if shot in CLOSE_SHOTS)
    medium = sum(1 for shot in shot_types if shot in MEDIUM_SHOTS)
    wide = sum(1 for shot in shot_types if shot in WIDE_SHOTS)
    establishing = sum(1 for shot in shot_types if shot is ShotType.ESTABLISHING)

    close_pct = _pct(close, total)
    medium_pct = _pct(medium, total)
    wide_pct = _pct(wide, total)
    establishing_pct = _pct(establishing, total)

    issues: list[str] = []
    if close_pct > MAX_CLOSE_PCT:
        issues.append(f"close shots {close_pct}% exceed the {MAX_CLOSE_PCT}% ceiling")
    if medium_pct < MIN_MEDIUM_PCT:
        issues.append(f"medium shots {medium_pct}% below the {MIN_MEDIUM_PCT}% floor")
    if medium_pct > MAX_MEDIUM_PCT:
        issues.append(f"medium shots {medium_pct}% exceed the {MAX_MEDIUM_PCT}% ceiling")
    if wide_pct < MIN_WIDE_PCT:
        issues.append(f"wide and full body {wide_pct}% below the {MIN_WIDE_PCT}% floor")
    if establishing_pct < MIN_ESTABLISHING_PCT:
        issues.append(f"establishing {establishing_pct}% below the {MIN_ESTABLISHING_PCT}% floor")

    return DistributionReport(
        total=total,
        close_pct=close_pct,
        medium_pct=medium_pct,
        wide_pct=wide_pct,
        establishing_pct=establishing_pct,
        issues=tuple(issues),
    )


def _justification(shot_type: ShotType, kind: SceneKind, is_opening: bool) -> int:
    """How strongly a scene's content justifies this size. Higher survives longer.

    A shot the sprint's rules *mandate* for its scene kind is never traded away
    — demoting it would break the rule the plan exists to enforce.
    """
    if is_opening and MANDATED[kind] is shot_type:
        return 3
    if MANDATED[kind] is shot_type:
        return 2
    if shot_type in COVERAGE[kind]:
        return 1
    return 0


def _candidates(
    shot_types: list[ShotType],
    kinds: list[SceneKind],
    openings: list[bool],
    members: frozenset[ShotType],
) -> list[int]:
    """Indices of shots in ``members``, least justified first, then last first.

    Working from the end of the film backwards among equals keeps the opening
    of each scene — which sets up its geography — intact for longer.
    """
    indices = [index for index, shot in enumerate(shot_types) if shot in members]
    return sorted(
        indices,
        key=lambda index: (
            _justification(shot_types[index], kinds[index], openings[index]),
            -index,
        ),
    )


def _demotion_target(kind: SceneKind) -> ShotType:
    """The wide size that best serves this kind of scene."""
    if kind in (SceneKind.COMBAT, SceneKind.ACTION):
        return ShotType.FULL_BODY
    if kind is SceneKind.LANDSCAPE:
        return ShotType.EXTREME_WIDE
    return ShotType.WIDE


class Rebalance:
    """The adjusted coverage, and exactly which shots had to move."""

    def __init__(self, sizes: list[ShotType], notes: list[str], changed: set[int]) -> None:
        self.sizes = sizes
        self.notes = notes
        self.changed = changed


def rebalance(
    shot_types: list[ShotType],
    kinds: list[SceneKind],
    openings: list[bool],
) -> Rebalance:
    """Bring the coverage inside its bounds, recording every change made.

    Returns the adjusted sizes, one note per change and the indices that moved,
    so a plan can always explain why a shot is not the size its scene alone
    would have chosen.
    """
    current = list(shot_types)
    notes: list[str] = []
    changed: set[int] = set()

    for _ in range(_replan_limit(len(current))):
        report = measure(current)
        if report.valid:
            break

        if report.close_pct > MAX_CLOSE_PCT:
            index = _pick(_candidates(current, kinds, openings, CLOSE_SHOTS))
            if index is None:
                break
            target = _demotion_target(kinds[index])
            notes.append(_note(index, current[index], target, "close coverage over 20%"))
            current[index] = target
            changed.add(index)
            continue

        if report.wide_pct < MIN_WIDE_PCT:
            index = _pick(_candidates(current, kinds, openings, MEDIUM_SHOTS | CLOSE_SHOTS))
            if index is None:
                break
            target = _demotion_target(kinds[index])
            notes.append(_note(index, current[index], target, "wide coverage under 40%"))
            current[index] = target
            changed.add(index)
            continue

        if report.medium_pct > MAX_MEDIUM_PCT:
            index = _pick(_candidates(current, kinds, openings, MEDIUM_SHOTS))
            if index is None:
                break
            target = _demotion_target(kinds[index])
            notes.append(_note(index, current[index], target, "medium coverage over 35%"))
            current[index] = target
            changed.add(index)
            continue

        if report.establishing_pct < MIN_ESTABLISHING_PCT:
            index = _pick_for_establishing(current, openings)
            if index is None:
                break
            notes.append(
                _note(index, current[index], ShotType.ESTABLISHING, "establishing under 5%")
            )
            current[index] = ShotType.ESTABLISHING
            changed.add(index)
            continue

        if report.medium_pct < MIN_MEDIUM_PCT:
            index = _pick(_candidates(current, kinds, openings, WIDE_SHOTS))
            if index is None:
                break
            notes.append(_note(index, current[index], ShotType.MEDIUM, "medium coverage under 20%"))
            current[index] = ShotType.MEDIUM
            changed.add(index)
            continue

        break

    return Rebalance(current, notes, changed)


def _pick(candidates: list[int]) -> int | None:
    return candidates[0] if candidates else None


def _pick_for_establishing(shot_types: list[ShotType], openings: list[bool]) -> int | None:
    """The best shot to turn into an establishing one: a scene's opening wide.

    A scene already opening on a wide size loses the least by becoming an
    establishing shot; converting a close up mid-scene would break the
    storytelling instead of serving it.
    """
    for index, shot in enumerate(shot_types):
        if openings[index] and shot in WIDE_SHOTS and shot is not ShotType.ESTABLISHING:
            return index
    for index, shot in enumerate(shot_types):
        if openings[index] and shot is not ShotType.ESTABLISHING:
            return index
    return None


def _note(index: int, before: ShotType, after: ShotType, cause: str) -> str:
    return f"shot {index + 1}: {before.value} -> {after.value} ({cause})"
