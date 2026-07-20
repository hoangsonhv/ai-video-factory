"""Tests for the video-clip manifest writer."""

from __future__ import annotations

import json
from pathlib import Path

from ai_video_factory.infrastructure.video.providers.base.models import (
    VideoGenerationResult,
    VideoJobStatus,
)
from ai_video_factory.infrastructure.video.providers.base.writer import (
    to_manifest_entry,
    write_video_manifest,
)


def _result(scene_id: int = 1, **overrides: object) -> VideoGenerationResult:
    defaults: dict[str, object] = {
        "scene_id": scene_id,
        "provider": "kling",
        "model": "kling-v1",
        "status": VideoJobStatus.COMPLETED,
        "remote_job_id": f"task-{scene_id}",
        "video_path": Path(f"output/video_clips/scene_{scene_id:03d}.mp4"),
        "duration": 5.0,
        "metadata": {"cost": 1.4},
    }
    defaults.update(overrides)
    return VideoGenerationResult.model_validate(defaults)


def test_entry_carries_every_required_field() -> None:
    entry = to_manifest_entry(_result(), estimated_cost=1.2)

    assert entry.scene_id == 1
    assert entry.provider == "kling"
    assert entry.model == "kling-v1"
    assert entry.status == "completed"
    assert entry.duration == 5.0
    assert entry.estimated_cost == 1.2
    assert entry.actual_cost == 1.4
    assert entry.remote_job_id == "task-1"
    assert entry.filename == "scene_001.mp4"


def test_actual_cost_defaults_to_zero_when_the_provider_reports_none() -> None:
    assert to_manifest_entry(_result(metadata={})).actual_cost == 0.0


def test_estimated_cost_defaults_to_zero_when_no_plan_is_supplied() -> None:
    assert to_manifest_entry(_result()).estimated_cost == 0.0


def test_a_failed_result_is_recorded_without_a_file() -> None:
    entry = to_manifest_entry(
        _result(status=VideoJobStatus.FAILED, video_path=None, remote_job_id=None, duration=0.0)
    )

    assert entry.status == "failed"
    assert entry.filename is None
    assert entry.remote_job_id is None


def test_manifest_is_written_as_utf8_json(tmp_path: Path) -> None:
    path = tmp_path / "manifest.json"

    write_video_manifest(path, [_result(1), _result(2)], estimates={1: 1.0, 2: 1.0})

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["count"] == 2
    assert payload["total_estimated_cost"] == 2.0
    assert payload["total_actual_cost"] == 2.8
    assert [clip["scene_id"] for clip in payload["clips"]] == [1, 2]
    assert set(payload["clips"][0]) == {
        "scene_id",
        "clip_id",
        "shot_ids",
        "provider",
        "model",
        "status",
        "duration",
        "estimated_cost",
        "actual_cost",
        "remote_job_id",
        "filename",
    }


def test_a_scene_absent_from_the_estimates_records_zero(tmp_path: Path) -> None:
    path = tmp_path / "manifest.json"

    write_video_manifest(path, [_result(1), _result(2)], estimates={1: 1.0})

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["clips"][1]["estimated_cost"] == 0.0


def test_manifest_creates_the_parent_directory(tmp_path: Path) -> None:
    path = tmp_path / "clips" / "manifest.json"

    write_video_manifest(path, [_result()])

    assert path.is_file()


def test_an_empty_manifest_is_valid(tmp_path: Path) -> None:
    path = tmp_path / "manifest.json"

    write_video_manifest(path, [])

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload == {
        "count": 0,
        "total_estimated_cost": 0,
        "total_actual_cost": 0,
        "clips": [],
    }
