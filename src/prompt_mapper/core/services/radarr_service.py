"""Radarr service implementation."""

from pathlib import Path
from typing import Any, Dict, List, Optional

import aiohttp

from ...config.models import Config
from ...infrastructure.logging import LoggerMixin
from ...utils import RadarrServiceError, create_hardlink, safe_copy_file, safe_move_file
from ..interfaces import IRadarrService
from ..interfaces.radarr_service import RadarrMovie
from ..models import ImportResult, MovieInfo


class RadarrService(IRadarrService, LoggerMixin):
    """Radarr service implementation."""

    def __init__(self, config: Config) -> None:
        """Initialize Radarr service.

        Args:
            config: Application configuration.
        """
        self._config = config
        self._radarr_config = config.radarr
        self._session: Optional[aiohttp.ClientSession] = None
        # Using manual HTTP requests for better control

    async def get_movie_by_tmdb_id(self, tmdb_id: int) -> Optional[RadarrMovie]:
        """Get movie from Radarr by TMDb ID.

        Args:
            tmdb_id: TMDb movie ID.

        Returns:
            Radarr movie object or None if not found.

        Raises:
            RadarrServiceError: If request fails.
        """
        if not self._radarr_config.enabled:
            return None

        try:
            url = f"{self._radarr_config.url}/api/v3/movie"
            headers = {"X-Api-Key": self._radarr_config.api_key}

            async with self._get_session().get(url, headers=headers) as response:
                response.raise_for_status()
                movies = await response.json()

                for movie in movies:
                    if movie.get("tmdbId") == tmdb_id:
                        return RadarrMovie(movie)

                return None

        except Exception as e:
            error_msg = f"Failed to get movie from Radarr by TMDb ID {tmdb_id}: {e}"
            self.logger.error(error_msg)
            raise RadarrServiceError(error_msg) from e

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
        if not self._radarr_config.enabled:
            raise RadarrServiceError("Radarr is not enabled")

        try:
            # Use defaults from config
            profile = self._radarr_config.default_profile
            root_path = root_folder_path or profile.root_folder_path
            quality_id = quality_profile_id or profile.quality_profile_id
            min_availability = minimum_availability or profile.minimum_availability
            movie_tags = tags or profile.tags

            # Prepare movie data for Radarr API v3
            movie_data: Dict[str, Any] = {
                "title": movie_info.title,
                "originalTitle": movie_info.original_title or movie_info.title,
                "year": movie_info.year,
                "tmdbId": movie_info.tmdb_id,
                "titleSlug": self._generate_title_slug(movie_info.title, movie_info.year),
                "overview": movie_info.overview or "",
                "runtime": movie_info.runtime or 0,
                "genres": movie_info.genres or [],
                "rootFolderPath": root_path,
                "qualityProfileId": quality_id,
                "minimumAvailability": min_availability,
                "tags": movie_tags or [],
                "monitored": True,
                "status": "announced",
                "addOptions": {"searchForMovie": False, "monitor": "movieOnly"},
            }

            # Add IMDb ID if available
            if movie_info.imdb_id:
                movie_data["imdbId"] = movie_info.imdb_id

            # Add images if available
            images = []
            if movie_info.poster_path:
                images.append(
                    {
                        "coverType": "poster",
                        "url": f"https://image.tmdb.org/t/p/original{movie_info.poster_path}",
                    }
                )
            if movie_info.backdrop_path:
                images.append(
                    {
                        "coverType": "fanart",
                        "url": f"https://image.tmdb.org/t/p/original{movie_info.backdrop_path}",
                    }
                )
            if images:
                movie_data["images"] = images

            # Make request
            url = f"{self._radarr_config.url}/api/v3/movie"
            headers = {"X-Api-Key": self._radarr_config.api_key}

            async with self._get_session().post(url, headers=headers, json=movie_data) as response:
                if response.status == 400:
                    error_text = await response.text()
                    self.logger.error(f"Radarr 400 error details: {error_text}")
                response.raise_for_status()
                result = await response.json()

                self.logger.info(f"Added movie to Radarr: {movie_info.title} ({movie_info.year})")
                return RadarrMovie(result)

        except Exception as e:
            error_msg = f"Failed to add movie to Radarr: {e}"
            self.logger.error(error_msg)
            raise RadarrServiceError(error_msg) from e

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
        if not self._radarr_config.enabled:
            return []

        results = []

        try:
            # Get movie folder path
            movie_path = Path(radarr_movie.get("path", ""))
            if not movie_path:
                raise RadarrServiceError("Movie path not found in Radarr")

            movie_path.mkdir(parents=True, exist_ok=True)

            for source_path in source_paths:
                if not source_path.exists():
                    results.append(
                        ImportResult(
                            file_path=source_path,
                            imported=False,
                            target_path=None,
                            error="Source file does not exist",
                            method=None,
                        )
                    )
                    continue

                # Determine target path
                target_path = movie_path / source_path.name

                # Import file based on mode
                success = False
                method = import_mode

                if import_mode == "hardlink":
                    success = create_hardlink(source_path, target_path)
                    if not success:
                        # Fall back to copy if hardlink fails
                        success = safe_copy_file(source_path, target_path)
                        method = "copy"
                elif import_mode == "copy":
                    success = safe_copy_file(source_path, target_path)
                elif import_mode == "move":
                    success = safe_move_file(source_path, target_path)
                else:
                    raise RadarrServiceError(f"Unsupported import mode: {import_mode}")

                if success:
                    results.append(
                        ImportResult(
                            file_path=source_path,
                            imported=True,
                            target_path=target_path,
                            error=None,
                            method=method,
                        )
                    )
                    self.logger.info(f"Imported file: {source_path} -> {target_path} ({method})")
                else:
                    results.append(
                        ImportResult(
                            file_path=source_path,
                            imported=False,
                            target_path=None,
                            error=f"Failed to {method} file",
                            method=None,
                        )
                    )

            # Trigger Radarr rescan
            await self._trigger_rescan(radarr_movie)

            return results

        except Exception as e:
            error_msg = f"Failed to import movie files: {e}"
            self.logger.error(error_msg)
            raise RadarrServiceError(error_msg) from e

    async def trigger_movie_search(self, radarr_movie: RadarrMovie) -> bool:
        """Trigger automatic search for movie.

        Args:
            radarr_movie: Radarr movie object.

        Returns:
            True if search was triggered successfully.

        Raises:
            RadarrServiceError: If request fails.
        """
        if not self._radarr_config.enabled:
            return False

        try:
            url = f"{self._radarr_config.url}/api/v3/command"
            headers = {"X-Api-Key": self._radarr_config.api_key}

            command_data = {"name": "MoviesSearch", "movieIds": [radarr_movie["id"]]}

            async with self._get_session().post(
                url, headers=headers, json=command_data
            ) as response:
                response.raise_for_status()
                return True

        except Exception as e:
            error_msg = f"Failed to trigger movie search: {e}"
            self.logger.error(error_msg)
            raise RadarrServiceError(error_msg) from e

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
        if not self._radarr_config.enabled:
            return False

        try:
            movie_id = radarr_movie["id"]
            url = f"{self._radarr_config.url}/api/v3/movie/{movie_id}"
            headers = {"X-Api-Key": self._radarr_config.api_key}
            params = {"deleteFiles": str(delete_files).lower()}

            async with self._get_session().delete(url, headers=headers, params=params) as response:
                response.raise_for_status()
                return True

        except Exception as e:
            error_msg = f"Failed to remove movie from Radarr: {e}"
            self.logger.error(error_msg)
            raise RadarrServiceError(error_msg) from e

    async def get_system_status(self) -> Dict[str, Any]:
        """Get Radarr system status.

        Returns:
            System status information.

        Raises:
            RadarrServiceError: If request fails.
        """
        if not self._radarr_config.enabled:
            return {"enabled": False}

        try:
            url = f"{self._radarr_config.url}/api/v3/system/status"
            headers = {"X-Api-Key": self._radarr_config.api_key}

            async with self._get_session().get(url, headers=headers) as response:
                response.raise_for_status()
                result = await response.json()
                if not isinstance(result, dict):
                    return {"error": "Invalid response format"}
                return result

        except Exception as e:
            error_msg = f"Failed to get Radarr system status: {e}"
            self.logger.error(error_msg)
            raise RadarrServiceError(error_msg) from e

    def is_available(self) -> bool:
        """Check if Radarr service is available.

        Returns:
            True if service is available.
        """
        if not self._radarr_config.enabled:
            return False

        try:
            # This would need to be implemented as a sync check
            # For now, just return True if enabled
            return True
        except Exception:
            return False

    async def _trigger_rescan(self, radarr_movie: RadarrMovie) -> None:
        """Trigger rescan of movie folder.

        Args:
            radarr_movie: Radarr movie object.
        """
        try:
            url = f"{self._radarr_config.url}/api/v3/command"
            headers = {"X-Api-Key": self._radarr_config.api_key}

            command_data = {"name": "RefreshMovie", "movieIds": [radarr_movie["id"]]}

            async with self._get_session().post(
                url, headers=headers, json=command_data
            ) as response:
                response.raise_for_status()

        except Exception as e:
            self.logger.warning(f"Failed to trigger movie rescan: {e}")

    def _get_session(self) -> aiohttp.ClientSession:
        """Get or create HTTP session.

        Returns:
            HTTP session.
        """
        if self._session is None:
            timeout = aiohttp.ClientTimeout(total=self._radarr_config.timeout)
            # Disable SSL verification for PyInstaller compatibility
            import ssl

            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            connector = aiohttp.TCPConnector(ssl=ssl_context)
            self._session = aiohttp.ClientSession(timeout=timeout, connector=connector)
        return self._session

    async def close(self) -> None:
        """Close HTTP session."""
        if self._session:
            await self._session.close()
            self._session = None

    async def __aenter__(self) -> "RadarrService":
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit."""
        await self.close()

    def _generate_title_slug(self, title: str, year: Optional[int]) -> str:
        """Generate title slug for Radarr.

        Args:
            title: Movie title.
            year: Movie year.

        Returns:
            Generated title slug.
        """
        import re

        # Clean title
        slug = title.lower()
        # Remove special characters
        slug = re.sub(r"[^\w\s-]", "", slug)
        # Replace spaces with hyphens
        slug = re.sub(r"\s+", "-", slug)
        # Remove multiple hyphens
        slug = re.sub(r"-+", "-", slug)
        # Remove leading/trailing hyphens
        slug = slug.strip("-")

        # Add year if available
        if year:
            slug = f"{slug}-{year}"

        return slug

    def __del__(self) -> None:
        """Cleanup on deletion."""
        # Just log that cleanup is needed, don't try to clean up here
        if self._session and not self._session.closed:
            import logging

            logging.getLogger(__name__).debug("RadarrService session not properly closed")
