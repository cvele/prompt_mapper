"""TMDb service interface."""

from abc import ABC, abstractmethod
from typing import List, Optional

from ..models import LLMResponse, MovieCandidate, MovieInfo


class ITMDbService(ABC):
    """Interface for TMDb services."""

    @abstractmethod
    async def search_movies(
        self, llm_response: LLMResponse, max_results: int = 10
    ) -> List[MovieCandidate]:
        """Search for movies based on LLM response.

        Args:
            llm_response: LLM response with movie information.
            max_results: Maximum number of results to return.

        Returns:
            List of movie candidates with match scores.

        Raises:
            TMDbServiceError: If search fails.
        """
        pass

    @abstractmethod
    async def get_movie_details(self, tmdb_id: int) -> Optional[MovieInfo]:
        """Get detailed movie information by TMDb ID.

        Args:
            tmdb_id: TMDb movie ID.

        Returns:
            Detailed movie information or None if not found.

        Raises:
            TMDbServiceError: If request fails.
        """
        pass

    @abstractmethod
    async def get_movie_by_imdb_id(self, imdb_id: str) -> Optional[MovieInfo]:
        """Get movie information by IMDb ID.

        Args:
            imdb_id: IMDb movie ID.

        Returns:
            Movie information or None if not found.

        Raises:
            TMDbServiceError: If request fails.
        """
        pass

    @abstractmethod
    def calculate_match_score(self, movie: MovieInfo, llm_response: LLMResponse) -> float:
        """Calculate match score between movie and LLM response.

        Args:
            movie: Movie information from TMDb.
            llm_response: LLM response with expected movie info.

        Returns:
            Match score between 0.0 and 1.0.
        """
        pass
