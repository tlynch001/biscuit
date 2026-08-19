"""Custom exception hierarchy used across the pipeline.

Keeping these distinct lets the CLI and orchestrator decide whether a
failure should abort the whole run or be reported as a configuration
problem (exit code 2) versus a runtime failure (exit code 1).
"""

from __future__ import annotations


class BiscuitError(Exception):
    """Base class for all errors raised by this package."""


class ConfigurationError(BiscuitError):
    """Raised when the configuration file or environment is invalid."""


class StoryValidationError(BiscuitError):
    """Raised when a story YAML file fails schema or referential checks."""


class ProviderNotFoundError(BiscuitError):
    """Raised when a configured provider name has not been registered."""


class ProviderError(BiscuitError):
    """Raised when a generative provider fails in a way that should abort."""


class NarrationError(ProviderError):
    """Raised when narration audio could not be synthesized."""


class ImageGenerationError(ProviderError):
    """Raised when a scene image could not be generated."""


class VideoAssemblyError(BiscuitError):
    """Raised when the final MP4 could not be assembled."""


class ArtifactError(BiscuitError):
    """Raised when expected pipeline artifacts are missing or unreadable."""
