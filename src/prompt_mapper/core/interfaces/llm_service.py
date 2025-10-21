"""LLM service interface."""

from abc import ABC, abstractmethod
from typing import List, Optional, Tuple

from ..models import MovieCandidate


class ILLMService(ABC):
    """Interface for LLM services."""

    @abstractmethod
    async def select_movie_from_candidates(
        self,
        candidates: List[MovieCandidate],
        original_filename: str,
        movie_name: str,
        movie_year: Optional[int],
        user_prompt: str,
    ) -> Tuple[Optional[MovieCandidate], float]:
        """Select the best movie match from TMDB candidates using LLM.

        Args:
            candidates: List of movie candidates from TMDB search.
            original_filename: Original filename for context.
            movie_name: Cleaned movie name extracted from filename.
            movie_year: Extracted year from filename (if any).
            user_prompt: User-provided prompt for selection guidance.

        Returns:
            Tuple of (selected_candidate, confidence_score).
            Returns (None, 0.0) if no suitable match found.

        Raises:
            LLMServiceError: If LLM request fails.
        """
        pass
