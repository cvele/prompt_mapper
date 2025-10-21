"""Movie resolver interface."""

from abc import ABC, abstractmethod
from typing import List, Optional

from ..models import MovieCandidate, MovieMatch


class IMovieResolver(ABC):
    """Interface for movie resolution services."""

    @abstractmethod
    async def resolve_movie_from_filename(self, filename: str, user_prompt: str) -> MovieMatch:
        """Resolve movie from filename using the simplified flow.

        Flow: clean filename → search TMDB → LLM selects → manual fallback if low confidence

        Args:
            filename: Movie filename to resolve.
            user_prompt: User prompt for resolution guidance.

        Returns:
            Movie match result.

        Raises:
            MovieResolverError: If resolution fails.
        """
        pass

    @abstractmethod
    async def get_user_choice(
        self,
        original_filename: str,
        movie_name: str,
        movie_year: Optional[int],
        candidates: List[MovieCandidate],
    ) -> Optional[int]:
        """Get user choice from movie candidates.

        Args:
            original_filename: Original filename for display.
            movie_name: Cleaned movie name.
            movie_year: Extracted year.
            candidates: List of movie candidates.

        Returns:
            Selected candidate index or None if skipped.
        """
        pass
