"""Movie resolver interface."""

from abc import ABC, abstractmethod
from typing import Optional

from ..models import LLMResponse, MovieMatch, ScanResult


class IMovieResolver(ABC):
    """Interface for movie resolution services."""

    @abstractmethod
    async def resolve_movie_from_llm_response(
        self, scan_result: ScanResult, llm_response: LLMResponse, confidence_threshold: float = 0.8
    ) -> MovieMatch:
        """Resolve movie from LLM response and scan result.

        Args:
            scan_result: File scan result.
            llm_response: LLM response with movie information.
            confidence_threshold: Minimum confidence for auto-selection.

        Returns:
            Movie match result.

        Raises:
            MovieResolverError: If resolution fails.
        """
        pass

    @abstractmethod
    async def get_user_choice(
        self, scan_result: ScanResult, candidates: list, llm_response: Optional[LLMResponse] = None
    ) -> Optional[int]:
        """Get user choice from movie candidates.

        Args:
            scan_result: Original scan result.
            candidates: List of movie candidates.
            llm_response: Original LLM response.

        Returns:
            Selected candidate index or None if skipped.
        """
        pass
