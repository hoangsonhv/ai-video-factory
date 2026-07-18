"""Logging configuration (infrastructure layer).

Sets up Rich console logging plus rotating-file logging from
:class:`LoggingSettings`, per the approved logging strategy
(docs/ai-tool.md §9, ADR-010). Correlation context and secret redaction are
scheduled for a later sprint; this module provides the foundational setup.
"""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler

from rich.logging import RichHandler

from ai_video_factory.infrastructure.config.settings import LoggingSettings

_FILE_FORMAT = "%(asctime)s %(levelname)-8s %(name)s: %(message)s"


def configure_logging(settings: LoggingSettings) -> None:
    """Configure the root logger from settings.

    Idempotent: replaces any previously installed handlers so repeated calls
    (e.g. across CLI invocations or tests) do not accumulate handlers.

    Args:
        settings: The logging section of the settings tree.
    """
    handlers: list[logging.Handler] = []

    if settings.console:
        handlers.append(RichHandler(rich_tracebacks=True, show_path=False, show_time=True))

    if settings.file_enabled:
        settings.file_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            settings.file_path,
            maxBytes=settings.max_bytes,
            backupCount=settings.backup_count,
            encoding="utf-8",
        )
        file_handler.setFormatter(logging.Formatter(_FILE_FORMAT))
        handlers.append(file_handler)

    level = logging.getLevelNamesMapping()[settings.level]
    logging.basicConfig(level=level, handlers=handlers, format="%(message)s", force=True)
