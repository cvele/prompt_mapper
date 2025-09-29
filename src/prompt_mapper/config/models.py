"""Configuration data models."""

import os
from typing import Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator


class LLMConfig(BaseModel):
    """LLM provider configuration."""

    provider: str = Field(..., description="LLM provider name")
    model: str = Field(..., description="Model identifier")
    api_key: str = Field(..., description="API key for the provider")
    max_tokens: int = Field(default=1000, description="Maximum tokens for completion")
    temperature: float = Field(default=0.1, ge=0.0, le=2.0, description="Sampling temperature")
    timeout: int = Field(default=30, gt=0, description="Request timeout in seconds")

    @field_validator("provider")
    @classmethod
    def validate_provider(cls, v: str) -> str:
        """Validate LLM provider."""
        allowed = {"openai", "anthropic"}
        if v.lower() not in allowed:
            raise ValueError(f"Provider must be one of: {allowed}")
        return v.lower()

    @field_validator("api_key")
    @classmethod
    def validate_api_key(cls, v: str) -> str:
        """Expand environment variables in API key."""
        return os.path.expandvars(v)


class TMDbConfig(BaseModel):
    """TMDb API configuration."""

    api_key: str = Field(..., description="TMDb API key")
    base_url: str = Field(default="https://api.themoviedb.org/3", description="TMDb API base URL")
    language: str = Field(default="en-US", description="Default language for requests")
    timeout: int = Field(default=10, gt=0, description="Request timeout in seconds")
    rate_limit: Dict[str, int] = Field(
        default_factory=lambda: {"requests_per_second": 4, "burst_limit": 10},
        description="Rate limiting configuration",
    )

    @field_validator("api_key")
    @classmethod
    def validate_api_key(cls, v: str) -> str:
        """Expand environment variables in API key."""
        return os.path.expandvars(v)


class RadarrProfileConfig(BaseModel):
    """Radarr default profile configuration."""

    quality_profile_id: int = Field(..., description="Default quality profile ID")
    root_folder_path: str = Field(..., description="Default root folder path")
    minimum_availability: str = Field(default="announced", description="Minimum availability")
    tags: List[str] = Field(default_factory=list, description="Default tags")

    @field_validator("minimum_availability")
    @classmethod
    def validate_availability(cls, v: str) -> str:
        """Validate minimum availability option."""
        allowed = {"announced", "inCinemas", "released", "preDB"}
        if v not in allowed:
            raise ValueError(f"Minimum availability must be one of: {allowed}")
        return v


class RadarrImportConfig(BaseModel):
    """Radarr import configuration."""

    mode: str = Field(default="hardlink", description="Import mode")
    delete_empty_folders: bool = Field(
        default=False, description="Delete empty folders after import"
    )

    @field_validator("mode")
    @classmethod
    def validate_mode(cls, v: str) -> str:
        """Validate import mode."""
        allowed = {"hardlink", "copy", "move"}
        if v not in allowed:
            raise ValueError(f"Import mode must be one of: {allowed}")
        return v


class RadarrConfig(BaseModel):
    """Radarr integration configuration."""

    enabled: bool = Field(default=True, description="Enable Radarr integration")
    url: str = Field(..., description="Radarr base URL")
    api_key: str = Field(..., description="Radarr API key")
    timeout: int = Field(default=30, gt=0, description="Request timeout in seconds")
    default_profile: RadarrProfileConfig = Field(..., description="Default profile settings")
    import_config: RadarrImportConfig = Field(
        default_factory=RadarrImportConfig, alias="import", description="Import configuration"
    )

    @field_validator("api_key")
    @classmethod
    def validate_api_key(cls, v: str) -> str:
        """Expand environment variables in API key."""
        return os.path.expandvars(v)


class MatchingScoringConfig(BaseModel):
    """Matching scoring weights configuration."""

    title_similarity: float = Field(default=0.4, ge=0.0, le=1.0)
    year_proximity: float = Field(default=0.3, ge=0.0, le=1.0)
    popularity: float = Field(default=0.2, ge=0.0, le=1.0)
    language_match: float = Field(default=0.1, ge=0.0, le=1.0)

    @field_validator("title_similarity", "year_proximity", "popularity", "language_match")
    @classmethod
    def validate_weights_sum(cls, v: float, info: ValidationInfo) -> float:
        """Validate that all weights sum to approximately 1.0."""
        # This is called for each field, so we check the sum when we have all values
        if info.data and len(info.data) == 3:  # All previous fields are set
            total = sum(info.data.values()) + v
            if not (0.99 <= total <= 1.01):  # Allow small floating point errors
                raise ValueError(f"Scoring weights must sum to 1.0, got {total}")
        return v


class MatchingConfig(BaseModel):
    """Movie matching configuration."""

    confidence_threshold: float = Field(
        default=0.8, ge=0.0, le=1.0, description="Minimum confidence for auto-match"
    )
    year_tolerance: int = Field(default=1, ge=0, description="Year tolerance for matching")
    max_search_results: int = Field(
        default=10, gt=0, description="Maximum search results to consider"
    )
    auto_add_to_radarr: bool = Field(
        default=False, description="Automatically add movies to Radarr"
    )
    auto_import: bool = Field(default=False, description="Automatically import matched files")
    skip_existing: bool = Field(default=True, description="Skip files already in Radarr")
    scoring: MatchingScoringConfig = Field(
        default_factory=MatchingScoringConfig, description="Scoring weights"
    )


class FilesConfig(BaseModel):
    """File processing configuration."""

    extensions: Dict[str, List[str]] = Field(
        default_factory=lambda: {
            "video": [".mkv", ".mp4", ".avi", ".mov", ".wmv", ".flv", ".webm", ".m4v"],
            "subtitle": [".srt", ".sub", ".idx", ".ass", ".ssa", ".vtt"],
        },
        description="File extensions by type",
    )
    ignore_patterns: List[str] = Field(
        default_factory=lambda: ["sample", "trailer", "extras", "behind.the.scenes"],
        description="Patterns to ignore in filenames",
    )
    min_file_size_mb: int = Field(default=100, ge=0, description="Minimum file size in MB")
    scan_depth: int = Field(default=2, ge=1, description="Maximum directory scan depth")


class PromptsConfig(BaseModel):
    """Prompts configuration."""

    default: str = Field(..., description="Default prompt for movie resolution")
    profiles: Dict[str, str] = Field(default_factory=dict, description="Named prompt profiles")


class LoggingConfig(BaseModel):
    """Logging configuration."""

    level: str = Field(default="INFO", description="Logging level")
    format: str = Field(
        default="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        description="Log format string",
    )
    file: Optional[str] = Field(default=None, description="Log file path")
    max_size_mb: int = Field(default=10, gt=0, description="Maximum log file size in MB")
    backup_count: int = Field(default=5, ge=0, description="Number of backup log files")

    @field_validator("level")
    @classmethod
    def validate_level(cls, v: str) -> str:
        """Validate logging level."""
        allowed = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if v.upper() not in allowed:
            raise ValueError(f"Logging level must be one of: {allowed}")
        return v.upper()


class AppConfig(BaseModel):
    """Application behavior configuration."""

    dry_run: bool = Field(default=False, description="Run in dry-run mode")
    interactive: bool = Field(default=True, description="Enable interactive mode")
    batch_size: int = Field(default=10, gt=0, description="Batch processing size")
    parallel_workers: int = Field(default=3, gt=0, description="Number of parallel workers")
    retry_attempts: int = Field(default=3, ge=0, description="Number of retry attempts")
    cache_enabled: bool = Field(default=True, description="Enable result caching")
    cache_ttl_hours: int = Field(default=24, gt=0, description="Cache TTL in hours")


class Config(BaseModel):
    """Main configuration model."""

    llm: LLMConfig = Field(..., description="LLM configuration")
    tmdb: TMDbConfig = Field(..., description="TMDb configuration")
    radarr: RadarrConfig = Field(..., description="Radarr configuration")
    matching: MatchingConfig = Field(
        default_factory=MatchingConfig, description="Matching configuration"
    )
    files: FilesConfig = Field(
        default_factory=FilesConfig, description="File processing configuration"
    )
    prompts: PromptsConfig = Field(..., description="Prompts configuration")
    logging: LoggingConfig = Field(
        default_factory=LoggingConfig, description="Logging configuration"
    )
    app: AppConfig = Field(default_factory=AppConfig, description="Application configuration")

    model_config = ConfigDict(
        validate_assignment=True,
        populate_by_name=True,
    )
