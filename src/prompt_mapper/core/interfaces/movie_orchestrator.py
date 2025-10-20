"""Movie orchestrator interface."""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import List

from ..models import ProcessingResult, SessionSummary


class IMovieOrchestrator(ABC):
    """Interface for movie processing orchestration."""

    @abstractmethod
    async def process_single_movie(
        self,
        path: Path,
        user_prompt: str,
        dry_run: bool = False,
        auto_add: bool = False,
        auto_import: bool = False,
    ) -> ProcessingResult:
        """Process a single movie directory.

        Args:
            path: Path to movie directory.
            user_prompt: User prompt for resolution guidance.
            dry_run: If True, don't make actual changes.
            auto_add: Automatically add to Radarr without confirmation.
            auto_import: Automatically import files without confirmation.

        Returns:
            Processing result.

        Raises:
            OrchestratorError: If processing fails.
        """
        pass

    @abstractmethod
    async def process_batch(
        self,
        paths: List[Path],
        user_prompt: str,
        dry_run: bool = False,
        auto_add: bool = False,
        auto_import: bool = False,
    ) -> SessionSummary:
        """Process multiple movie directories in batch using LLM batching.

        Args:
            paths: List of paths to movie directories.
            user_prompt: User prompt for resolution guidance.
            dry_run: If True, don't make actual changes.
            auto_add: Automatically add to Radarr without confirmation.
            auto_import: Automatically import files without confirmation.

        Returns:
            Session summary with all results.

        Raises:
            OrchestratorError: If batch processing fails.
        """
        pass

    @abstractmethod
    async def validate_prerequisites(self) -> List[str]:
        """Validate that all prerequisites are met.

        Returns:
            List of validation errors (empty if all valid).
        """
        pass

    @abstractmethod
    def set_interactive_mode(self, interactive: bool) -> None:
        """Set interactive mode for user confirmations.

        Args:
            interactive: Whether to prompt user for confirmations.
        """
        pass
