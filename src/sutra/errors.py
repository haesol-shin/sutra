from __future__ import annotations


class SutraError(RuntimeError):
    """Base error for Sutra runtime failures."""


class ConfigError(SutraError):
    """Raised when a workspace configuration is invalid."""


class LlamaError(SutraError):
    """Raised when llama-server cannot produce a usable response."""


class WorkspaceResolutionError(SutraError):
    """Raised when a workspace configuration cannot be resolved."""


class ExtractionError(SutraError):
    """Raised when PDF extraction fails irrecoverably."""

