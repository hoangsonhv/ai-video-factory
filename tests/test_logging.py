"""Tests for the logging configuration."""

from __future__ import annotations

import logging
from pathlib import Path

from ai_video_factory.infrastructure.config.settings import LoggingSettings
from ai_video_factory.infrastructure.logging.setup import configure_logging


def test_rotating_file_handler_writes_records(tmp_path: Path) -> None:
    log_file = tmp_path / "logs" / "app.log"
    configure_logging(LoggingSettings(file_path=log_file, console=False, level="DEBUG"))

    logging.getLogger("aivideo.test").debug("hello from test")
    for handler in logging.getLogger().handlers:
        handler.flush()

    assert log_file.exists()
    assert "hello from test" in log_file.read_text(encoding="utf-8")


def test_configure_logging_sets_root_level(tmp_path: Path) -> None:
    configure_logging(LoggingSettings(file_path=tmp_path / "a.log", console=False, level="WARNING"))
    assert logging.getLogger().level == logging.WARNING


def test_configure_logging_is_idempotent(tmp_path: Path) -> None:
    settings = LoggingSettings(file_path=tmp_path / "b.log", console=False, level="INFO")
    configure_logging(settings)
    configure_logging(settings)
    file_handlers = [
        handler
        for handler in logging.getLogger().handlers
        if isinstance(handler, logging.FileHandler)
    ]
    assert len(file_handlers) == 1
