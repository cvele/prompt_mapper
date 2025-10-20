"""Core data models."""

from .file_info import FileInfo, ScanResult
from .llm_response import LLMResponse
from .movie import MovieCandidate, MovieInfo, MovieMatch
from .processing_result import ImportResult, ProcessingResult, SessionSummary

# Rebuild models to resolve forward references
MovieMatch.model_rebuild()
ProcessingResult.model_rebuild()
SessionSummary.model_rebuild()

__all__ = [
    "MovieInfo",
    "MovieCandidate",
    "MovieMatch",
    "FileInfo",
    "ScanResult",
    "LLMResponse",
    "ProcessingResult",
    "SessionSummary",
    "ImportResult",
]
