"""Utility functions and classes."""

from .exceptions import (
    ConfigurationError,
    FileScannerError,
    LLMServiceError,
    MovieResolverError,
    OrchestratorError,
    PromptMapperError,
    RadarrServiceError,
    TMDbServiceError,
)
from .file_utils import (
    create_hardlink,
    get_directory_size,
    get_file_size,
    is_hidden_file,
    safe_copy_file,
    safe_move_file,
)
from .radarr_cleaner import clean_movie_filename, extract_edition_info
from .text_utils import (
    calculate_similarity,
    clean_filename,
    extract_language_hints,
    extract_year_from_filename,
    normalize_title,
)

__all__ = [
    "PromptMapperError",
    "ConfigurationError",
    "LLMServiceError",
    "TMDbServiceError",
    "RadarrServiceError",
    "FileScannerError",
    "MovieResolverError",
    "OrchestratorError",
    "normalize_title",
    "calculate_similarity",
    "extract_year_from_filename",
    "clean_filename",
    "extract_language_hints",
    "get_file_size",
    "is_hidden_file",
    "get_directory_size",
    "create_hardlink",
    "safe_copy_file",
    "safe_move_file",
    "clean_movie_filename",
    "extract_edition_info",
]
