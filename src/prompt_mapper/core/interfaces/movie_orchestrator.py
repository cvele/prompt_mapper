"""Movie orchestrator interface."""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import List

from ..models import SessionSummary


class IMovieOrchestrator(ABC):
    """Interface for movie processing orchestration."""

    @abstractmethod
    async def process_directory(
        self,
        directory: Path,
        user_prompt: str,
        auto_add: bool = False,
    ) -> SessionSummary:
        """Process all movie files in a directory.

        Args:
            directory: Directory path to process.
            user_prompt: User prompt for resolution guidance.
            auto_add: Automatically add to Radarr without confirmation.

        Returns:
            Session summary with all results.

        Raises:
            OrchestratorError: If processing fails.
        """
        pass

    @abstractmethod
    async def validate_prerequisites(self) -> List[str]:
        """Validate that all prerequisites are met.

        Returns:
            List of validation errors (empty if all valid).
        """
        pass
