"""LLM service interface."""

from abc import ABC, abstractmethod
from typing import List

from ..models import FileInfo, LLMResponse


class ILLMService(ABC):
    """Interface for LLM services."""

    @abstractmethod
    async def resolve_movie(
        self, file_info: List[FileInfo], user_prompt: str, context: str = ""
    ) -> LLMResponse:
        """Resolve movie information from file information using LLM.

        Args:
            file_info: List of file information objects.
            user_prompt: User-provided prompt for resolution guidance.
            context: Additional context information.

        Returns:
            LLM response with movie resolution.

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
