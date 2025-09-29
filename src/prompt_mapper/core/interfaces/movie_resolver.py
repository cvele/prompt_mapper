"""Movie resolver interface."""

from abc import ABC, abstractmethod
from typing import Optional

from ..models import LLMResponse, MovieMatch, ScanResult


class IMovieResolver(ABC):
    """Interface for movie resolution services."""

    @abstractmethod
    async def resolve_movie(
        self, scan_result: ScanResult, user_prompt: str, confidence_threshold: float = 0.8
    ) -> MovieMatch:
        """Resolve movie from scan result.

        Args:
            scan_result: File scan result.
            user_prompt: User prompt for resolution guidance.
            confidence_threshold: Minimum confidence for auto-selection.

        Returns:
            Movie match result.

        Raises:
            MovieResolverError: If resolution fails.
        """
        pass

    @abstractmethod
    async def resolve_with_llm(self, scan_result: ScanResult, user_prompt: str) -> LLMResponse:
        """Get LLM resolution for scan result.

        Args:
            scan_result: File scan result.
            user_prompt: User prompt for resolution guidance.

        Returns:
            LLM response with movie information.

        Raises:
            MovieResolverError: If LLM resolution fails.
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
