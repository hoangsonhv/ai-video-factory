"""Application exception hierarchy.

The single, layered hierarchy defined by the approved architecture
(docs/ai-tool.md §7). Every failure the system raises deliberately descends
from :class:`AppError`, so the CLI boundary can catch one root type.

The root lives at the package top level because it is cross-cutting: the
domain, application and infrastructure layers all raise descendants of it,
and this module imports nothing but the standard library, so importing it
never violates the inward-only dependency rule.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


class AppError(Exception):
    """Root of every deliberate application error.

    Args:
        message: Human-readable description of the failure.
        context: Optional structured context (stage, ids, provider, ...)
            attached for logging and diagnostics, never for control flow.
    """

    def __init__(self, message: str, *, context: Mapping[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.context: Mapping[str, Any] = context or {}

    def __str__(self) -> str:
        return self.message


class DomainError(AppError):
    """Violation of a business rule in the domain layer."""


class ApplicationError(AppError):
    """Failure while orchestrating a use case or the workflow."""


class InfrastructureError(AppError):
    """Failure originating in an adapter (DB, provider, media, ...)."""


class ProviderError(InfrastructureError):
    """Failure of an external AI provider adapter.

    Args:
        message: Human-readable description of the failure.
        retryable: Whether the failure is transient (rate limit, 5xx) and
            eligible for the retry policy, as opposed to terminal.
        context: Optional structured context.
    """

    def __init__(
        self,
        message: str,
        *,
        retryable: bool = False,
        context: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message, context=context)
        self.retryable = retryable


class PersistenceError(InfrastructureError):
    """Failure while reading from or writing to persistent storage."""


class MediaError(InfrastructureError):
    """Failure while producing media (e.g. an ffmpeg subprocess)."""


class ConfigurationError(AppError):
    """Invalid or missing configuration, detected at load time (fail fast)."""
