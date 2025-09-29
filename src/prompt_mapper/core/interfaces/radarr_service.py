"""Radarr service interface."""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..models import ImportResult, MovieInfo


class RadarrMovie(dict):
    """Radarr movie representation."""

    pass


class IRadarrService(ABC):
    """Interface for Radarr services."""

    @abstractmethod
    async def get_movie_by_tmdb_id(self, tmdb_id: int) -> Optional[RadarrMovie]:
        """Get movie from Radarr by TMDb ID.

        Args:
            tmdb_id: TMDb movie ID.

        Returns:
            Radarr movie object or None if not found.

        Raises:
            RadarrServiceError: If request fails.
        """
        pass

    @abstractmethod
    async def add_movie(
        self,
        movie_info: MovieInfo,
        root_folder_path: Optional[str] = None,
        quality_profile_id: Optional[int] = None,
        minimum_availability: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> RadarrMovie:
        """Add movie to Radarr.

        Args:
            movie_info: Movie information to add.
            root_folder_path: Root folder path (uses default if None).
            quality_profile_id: Quality profile ID (uses default if None).
            minimum_availability: Minimum availability (uses default if None).
            tags: Tags to apply (uses default if None).

        Returns:
            Added Radarr movie object.

        Raises:
            RadarrServiceError: If add fails.
        """
        pass

    @abstractmethod
    async def import_movie_files(
        self, radarr_movie: RadarrMovie, source_paths: List[Path], import_mode: str = "hardlink"
    ) -> List[ImportResult]:
        """Import movie files into Radarr.

        Args:
            radarr_movie: Radarr movie object.
            source_paths: List of source file paths to import.
            import_mode: Import mode (hardlink, copy, move).

        Returns:
            List of import results.

        Raises:
            RadarrServiceError: If import fails.
        """
        pass

    @abstractmethod
    async def trigger_movie_search(self, radarr_movie: RadarrMovie) -> bool:
        """Trigger automatic search for movie.

        Args:
            radarr_movie: Radarr movie object.

        Returns:
            True if search was triggered successfully.

        Raises:
            RadarrServiceError: If request fails.
        """
        pass

    @abstractmethod
    async def remove_movie(self, radarr_movie: RadarrMovie, delete_files: bool = False) -> bool:
        """Remove movie from Radarr.

        Args:
            radarr_movie: Radarr movie object to remove.
            delete_files: Whether to delete associated files.

        Returns:
            True if removal was successful.

        Raises:
            RadarrServiceError: If removal fails.
        """
        pass

    @abstractmethod
    async def get_system_status(self) -> Dict[str, Any]:
        """Get Radarr system status.

        Returns:
            System status information.

        Raises:
            RadarrServiceError: If request fails.
        """
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Check if Radarr service is available.

        Returns:
            True if service is available.
        """
        pass
