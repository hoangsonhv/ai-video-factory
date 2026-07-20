"""``ai-video-factory video`` CLI command group (interface layer).

Thin commands over the video provider abstraction: list the registered
providers, health-check them, and render a movie's scenes with the configured
provider. All logic lives in ``infrastructure/video/providers``.

Only the development ``mock`` provider ships today — no commercial video
provider is integrated. The existing ``compose`` slideshow pipeline is
untouched and keeps working unchanged.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.progress import BarColumn, Progress, TaskID, TextColumn

from ai_video_factory.domain.value_objects.storyboard import Storyboard
from ai_video_factory.errors import AppError
from ai_video_factory.infrastructure.config.settings import Settings, load_settings
from ai_video_factory.infrastructure.storyboard.reader import read_optional_library
from ai_video_factory.infrastructure.video.providers.base.models import (
    ClipReferences,
    VideoGenerationRequest,
    VideoGenerationResult,
    VideoJobStatus,
    VideoProviderStatus,
)
from ai_video_factory.infrastructure.video.providers.base.provider import VideoProvider
from ai_video_factory.infrastructure.video.providers.base.writer import (
    MANIFEST_FILENAME,
    write_video_manifest,
)
from ai_video_factory.infrastructure.video.providers.clip_planner import (
    MIN_CLIP_SECONDS,
    ClipPlan,
)
from ai_video_factory.infrastructure.video.providers.cost import GenerationPlan, build_plan
from ai_video_factory.infrastructure.video.providers.mock.provider import clip_filename
from ai_video_factory.infrastructure.video.providers.registry import build_default_registry
from ai_video_factory.infrastructure.video.providers.scene_reader import (
    build_requests,
    read_scene_movie,
)
from ai_video_factory.infrastructure.video.providers.storyboard_source import (
    build_references,
    read_storyboard,
    shot_character,
)
from ai_video_factory.infrastructure.video.providers.storyboard_source import (
    build_requests as build_clip_requests,
)
from ai_video_factory.interface.presenters.video_provider_presenter import (
    count_by_status,
    render_generation_plan,
    render_generation_summary,
    render_provider_health,
    render_provider_list,
)
from ai_video_factory.shared.console import ensure_utf8_stdout
from ai_video_factory.shared.health import HealthStatus

video_app = typer.Typer(
    no_args_is_help=True,
    help="Inspect and run the AI video-generation providers.",
)
_console = Console()

CLIPS_DIRNAME = "video_clips"
IMAGES_DIRNAME = "images"
LIBRARY_FILENAME = "character_library.json"


def _clips_dir(settings: Settings) -> Path:
    return settings.app.output_dir / CLIPS_DIRNAME


def _provider_statuses(settings: Settings) -> list[VideoProviderStatus]:
    registry = build_default_registry()
    return asyncio.run(registry.health_check(settings, _clips_dir(settings)))


@video_app.command("providers")
def video_providers_command() -> None:
    """List the registered video providers and the configured default."""
    ensure_utf8_stdout()
    settings = load_settings()
    try:
        statuses = _provider_statuses(settings)
    except AppError as exc:
        _console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    render_provider_list(statuses)
    configured = settings.video_provider.provider
    if not any(status.is_default for status in statuses):
        _console.print(
            f"[red]Error:[/red] configured video provider {configured!r} is not registered"
        )
        raise typer.Exit(code=1)
    _console.print(f"[green]Default[/green] {configured} (model={settings.video_provider.model})")


@video_app.command("doctor")
def video_doctor_command() -> None:
    """Health-check every registered video provider.

    Only the **configured** provider decides the exit code: an unconfigured
    alternative driver (e.g. Kling with no API key while ``mock`` is selected)
    is reported for information without failing the command.
    """
    ensure_utf8_stdout()
    settings = load_settings()
    try:
        statuses = _provider_statuses(settings)
    except AppError as exc:
        _console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    render_provider_health(statuses)
    default = next((status for status in statuses if status.is_default), None)
    if default is None:
        _console.print(
            f"[red]Error:[/red] configured video provider "
            f"{settings.video_provider.provider!r} is not registered"
        )
        raise typer.Exit(code=1)
    if default.health.status is HealthStatus.FAIL:
        raise typer.Exit(code=1)


class PhaseReporter:
    """Bridges a provider's phase callbacks to a live Rich progress bar.

    Providers report ``submitting`` / ``waiting`` / ``downloading`` /
    ``completed`` as a generation advances; each callback rewrites the task
    description so a long remote render shows what it is doing.
    """

    def __init__(self) -> None:
        self._progress: Progress | None = None
        self._task: TaskID | None = None
        self._total = 0

    def bind(self, progress: Progress, task: TaskID, total: int) -> None:
        """Attach the bar this reporter drives."""
        self._progress = progress
        self._task = task
        self._total = total

    def __call__(self, scene_id: int, phase: str) -> None:
        self.show(scene_id, phase)

    def show(self, scene_id: int, phase: str) -> None:
        """Render ``phase`` for ``scene_id`` on the bound bar."""
        if self._progress is None or self._task is None:
            return
        label = f" [{phase}]" if phase else ""
        self._progress.update(self._task, description=f"Scene {scene_id}/{self._total}{label}")


def _generate_all(
    provider: VideoProvider,
    requests: list[VideoGenerationRequest],
    model: str,
    reporter: PhaseReporter,
    *,
    references: dict[int, ClipReferences] | None = None,
    clips_dir: Path | None = None,
    resume: bool = False,
) -> list[VideoGenerationResult]:
    """Render every clip, continuing past a failed one.

    With ``resume`` a clip whose file already exists is reused untouched,
    so an interrupted run costs nothing to finish.
    """
    results: list[VideoGenerationResult] = []
    offered = references or {}
    total = len(requests)
    with Progress(
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("{task.completed}/{task.total}"),
        console=_console,
    ) as progress:
        task = progress.add_task("Generating clips", total=total)
        reporter.bind(progress, task, total)
        for request in requests:
            reporter.show(request.clip_id, "")
            existing = _existing_clip(clips_dir, request.clip_id) if resume else None
            if existing is not None:
                reporter.show(request.clip_id, "skipped")
                results.append(_reused(request, provider.name, model, existing))
                progress.advance(task)
                continue
            try:
                results.append(
                    asyncio.run(provider.generate(request, offered.get(request.clip_id)))
                )
            except AppError as exc:
                _console.print(f"[red]Clip {request.clip_id} failed:[/red] {exc}")
                results.append(
                    VideoGenerationResult(
                        scene_id=request.scene_id,
                        clip_id=request.clip_id,
                        shot_ids=request.shot_ids,
                        provider=provider.name,
                        model=model,
                        status=VideoJobStatus.FAILED,
                        duration=0.0,
                        metadata={"error": str(exc)},
                    )
                )
            progress.advance(task)
    return results


def _existing_clip(clips_dir: Path | None, clip_id: int) -> Path | None:
    """A previously rendered clip file, if one is already on disk."""
    if clips_dir is None:
        return None
    candidate = clips_dir / clip_filename(clip_id)
    return candidate if candidate.is_file() else None


def _reused(
    request: VideoGenerationRequest, provider: str, model: str, path: Path
) -> VideoGenerationResult:
    """Record an already-rendered clip without re-spending on it."""
    return VideoGenerationResult(
        scene_id=request.scene_id,
        clip_id=request.clip_id,
        shot_ids=request.shot_ids,
        provider=provider,
        model=model,
        status=VideoJobStatus.COMPLETED,
        video_path=path,
        duration=request.duration,
        metadata={"reused": True},
    )


def _confirm_spend(plan: GenerationPlan) -> bool:
    """Ask before submitting paid jobs; a non-interactive stream declines."""
    cost = f"{plan.estimated_cost:.2f}" if plan.cost_is_known else "unknown"
    _console.print(
        f"[yellow]This operation will submit {plan.jobs} paid AI video job(s)[/yellow] "
        f"via {plan.provider} ({plan.model})."
    )
    _console.print(f"Estimated duration: {plan.total_duration:.1f}s | Estimated cost: {cost}")
    try:
        return typer.confirm("Continue?", default=False)
    except (typer.Abort, EOFError):
        # No TTY (CI, piped input): decline rather than spend money unattended.
        return False


def _resolve_references(
    planned: list[tuple[ClipPlan, VideoGenerationRequest]],
    storyboard: Storyboard,
    settings: Settings,
    images_dir: Path,
    clips_dir: Path,
) -> dict[int, ClipReferences]:
    """Pin each clip to the stills that keep it consistent with its neighbours.

    The previous clip is offered as a reference so a provider that supports
    continuation can carry the look forward; providers that do not simply
    ignore it.
    """
    library = read_optional_library(settings.app.output_dir / LIBRARY_FILENAME)
    profiles = (
        {profile.id.strip().lower(): profile for profile in library.characters} if library else {}
    )
    references: dict[int, ClipReferences] = {}
    previous: Path | None = None
    for clip, _request in planned:
        references[clip.clip_id] = build_references(
            clip,
            character=shot_character(storyboard, clip.shot_ids),
            profiles=profiles,
            images_dir=images_dir if images_dir.is_dir() else None,
            previous_clip=previous,
        )
        previous = clips_dir / clip_filename(clip.clip_id)
    return references


def _warn_if_clips_are_short(clips: list[ClipPlan]) -> None:
    """Say when a clip could not reach the provider-friendly minimum.

    It happens when a scene's shots cannot be grouped into runs of at least
    ``MIN_CLIP_SECONDS`` without crossing a scene cut — a 9s scene of 3s shots
    can only split 6+3. Worth reporting: some providers reject very short
    requests, and the fix lives upstream in the shot lengths.
    """
    short = [clip for clip in clips if clip.is_short]
    if not short:
        return
    ids = ", ".join(str(clip.clip_id) for clip in short[:8])
    more = f" (+{len(short) - 8} more)" if len(short) > 8 else ""
    _console.print(
        f"[yellow]Note:[/yellow] {len(short)} of {len(clips)} clips are under "
        f"{MIN_CLIP_SECONDS}s because their scene could not be split evenly: "
        f"clip {ids}{more}. Longer shots from `director` would remove this."
    )


@video_app.command("generate")
def video_generate_command(
    storyboard_path: Annotated[
        Path | None,
        typer.Option("--storyboard", help="Path to a storyboard JSON file (shots to render)."),
    ] = None,
    movie_path: Annotated[
        Path,
        typer.Option(
            "--movie",
            "--scene",
            help="Path to a movie JSON file (scene-per-clip, pre-storyboard).",
        ),
    ] = Path("output/movie_consistent.json"),
    images: Annotated[
        Path | None,
        typer.Option("--images", help="Directory of scene images for image-to-video."),
    ] = None,
    limit: Annotated[
        int | None,
        typer.Option("--limit", help="Only submit the first N clips.", min=1),
    ] = None,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Show what would be submitted, then stop."),
    ] = False,
    resume: Annotated[
        bool,
        typer.Option("--resume", help="Keep clips already rendered; only generate the rest."),
    ] = False,
    yes: Annotated[
        bool,
        typer.Option("--yes", "-y", help="Skip the confirmation prompt for paid providers."),
    ] = False,
) -> None:
    """Render AI video clips from a storyboard (or, legacy, one per movie scene).

    With ``--storyboard`` the shots are grouped into 4-8 second clips, each
    carrying the character, scene and previous-clip references a provider may
    condition on to hold consistency.
    """
    ensure_utf8_stdout()
    settings = load_settings()
    clips_dir = _clips_dir(settings)
    images_dir = images if images is not None else settings.app.output_dir / IMAGES_DIRNAME
    reporter = PhaseReporter()
    references: dict[int, ClipReferences] = {}

    try:
        if storyboard_path is not None:
            storyboard = read_storyboard(storyboard_path)
            planned = build_clip_requests(storyboard, settings.video)
            all_requests = [request for _clip, request in planned]
            _warn_if_clips_are_short([clip for clip, _request in planned])
            references = _resolve_references(planned, storyboard, settings, images_dir, clips_dir)
        else:
            movie = read_scene_movie(movie_path)
            all_requests = build_requests(movie, settings.video, images_dir=images_dir)
    except AppError as exc:
        _console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    requests = all_requests[:limit] if limit is not None else all_requests
    plan = build_plan(requests, settings.video_provider, scene_count=len(all_requests))

    # A dry run must never need credentials, so no provider is built.
    if dry_run:
        render_generation_plan(plan)
        _console.print("[green]Dry run:[/green] nothing was submitted.")
        return

    if plan.is_paid and not yes and not _confirm_spend(plan):
        _console.print("[yellow]Aborted:[/yellow] nothing was submitted.")
        return

    try:
        registry = build_default_registry(on_progress=reporter)
        provider = registry.create_default(settings, clips_dir)
        health = asyncio.run(provider.health_check())
    except AppError as exc:
        _console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    if health.status is HealthStatus.FAIL:
        _console.print(
            f"[red]Error:[/red] video provider {settings.video_provider.provider!r} "
            f"is not ready: {health.detail}"
        )
        raise typer.Exit(code=1)

    results = _generate_all(
        provider,
        requests,
        settings.video_provider.model,
        reporter,
        references=references,
        clips_dir=clips_dir,
        resume=resume,
    )
    write_video_manifest(clips_dir / MANIFEST_FILENAME, results, estimates=plan.per_scene)
    render_generation_summary(results, clips_dir)

    completed = count_by_status(results, VideoJobStatus.COMPLETED)
    failed = count_by_status(results, VideoJobStatus.FAILED)
    _console.print(f"[green]Generated[/green] {completed} clip(s), {failed} failed, in {clips_dir}")
    if failed:
        raise typer.Exit(code=1)
