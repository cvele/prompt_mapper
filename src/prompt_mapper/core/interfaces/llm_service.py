"""LLM service interface."""

from abc import ABC, abstractmethod
from typing import Any, Dict, List

from ..models import LLMResponse


class ILLMService(ABC):
    """Interface for LLM services."""

    @abstractmethod
    async def resolve_movies_batch(
        self, movies_data: List[Dict[str, Any]], user_prompt: str
    ) -> List[LLMResponse]:
        """Resolve movie information for multiple movies in a single LLM request.

        Args:
            movies_data: List of movie data dictionaries, each containing:
                - file_info: List[FileInfo] - File information objects
                - context: str - Additional context information
            user_prompt: User-provided prompt for resolution guidance.

        Returns:
            List of LLM responses with movie resolutions, one per input movie.

        Raises:
            LLMServiceError: If LLM request fails.
        """
        pass

    @abstractmethod
    def validate_response(self, response: str) -> bool:
        """Validate LLM response format.

        Args:
            response: Raw LLM response.

        Returns:
            True if response is valid, False otherwise.
        """
        pass
