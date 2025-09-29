"""Custom exceptions for the application."""


class PromptMapperError(Exception):
    """Base exception for all application errors."""

    pass


class ConfigurationError(PromptMapperError):
    """Configuration-related errors."""

    pass


class LLMServiceError(PromptMapperError):
    """LLM service errors."""

    pass


class TMDbServiceError(PromptMapperError):
    """TMDb service errors."""

    pass


class RadarrServiceError(PromptMapperError):
    """Radarr service errors."""

    pass


class FileScannerError(PromptMapperError):
    """File scanner errors."""

    pass


class MovieResolverError(PromptMapperError):
    """Movie resolver errors."""

    pass


class OrchestratorError(PromptMapperError):
    """Orchestrator errors."""

    pass
