"""Radarr service implementation."""

from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional

import httpx

if TYPE_CHECKING:
    pass

from ...config.models import Config
from ...infrastructure.logging import LoggerMixin
from ...utils import RadarrServiceError
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
        self._client: Optional["httpx.AsyncClient"] = None
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

            response = await self._get_client().get(url, headers=headers)
            response.raise_for_status()
            movies = response.json()

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

            response = await self._get_client().post(url, headers=headers, json=movie_data)
            if response.status_code == 400:
                error_text = response.text
                self.logger.error(f"Radarr 400 error details: {error_text}")
            response.raise_for_status()
            result = response.json()

            self.logger.info(f"Added movie to Radarr: {movie_info.title} ({movie_info.year})")
            return RadarrMovie(result)

        except Exception as e:
            error_msg = f"Failed to add movie to Radarr: {e}"
            self.logger.error(error_msg)
            raise RadarrServiceError(error_msg) from e

    async def import_movie_files(
        self, radarr_movie: RadarrMovie, source_paths: List[Path], import_mode: str = "hardlink"
    ) -> List[ImportResult]:
        """Import movie files into Radarr using Radarr's manual import API.

        Args:
            radarr_movie: Radarr movie object.
            source_paths: List of source file paths to import.
            import_mode: Import mode (unused - Radarr handles this based on its config).

        Returns:
            List of import results.

        Raises:
            RadarrServiceError: If import fails.
        """
        if not self._radarr_config.enabled:
            return []

        results = []

        try:
            # Step 1: Get manual import candidates from Radarr
            import_candidates = await self._get_manual_import_candidates(source_paths, radarr_movie)

            if not import_candidates:
                # No valid candidates found
                for source_path in source_paths:
                    results.append(
                        ImportResult(
                            file_path=source_path,
                            imported=False,
                            target_path=None,
                            error="No valid import candidates found by Radarr",
                            method=None,
                        )
                    )
                return results

            # Step 2: Execute the manual import via Radarr's API
            import_results = await self._execute_manual_import(import_candidates)

            # Step 3: Convert Radarr's response to our ImportResult format
            source_path_map = {str(path): path for path in source_paths}

            for radarr_result in import_results:
                source_path_str = radarr_result.get("path", "")
                source_path = source_path_map.get(source_path_str, Path(source_path_str))

                if radarr_result.get("importDecision", {}).get("approved", False):
                    # Import was successful
                    movie_file = radarr_result.get("movieFile", {})
                    target_path = Path(movie_file.get("path", "")) if movie_file else None

                    results.append(
                        ImportResult(
                            file_path=source_path,
                            imported=True,
                            target_path=target_path,
                            error=None,
                            method="radarr_api",
                        )
                    )
                    self.logger.info(
                        f"Successfully imported via Radarr: {source_path} -> {target_path}"
                    )
                else:
                    # Import failed or was rejected
                    rejection_reasons = []
                    for rejection in radarr_result.get("importDecision", {}).get("rejections", []):
                        rejection_reasons.append(rejection.get("reason", "Unknown reason"))

                    error_msg = (
                        "; ".join(rejection_reasons)
                        if rejection_reasons
                        else "Import rejected by Radarr"
                    )

                    results.append(
                        ImportResult(
                            file_path=source_path,
                            imported=False,
                            target_path=None,
                            error=error_msg,
                            method=None,
                        )
                    )
                    self.logger.warning(f"Import rejected by Radarr: {source_path} - {error_msg}")

            return results

        except Exception as e:
            error_msg = f"Failed to import movie files via Radarr API: {e}"
            self.logger.error(error_msg)

            # Return failure results for all files
            for source_path in source_paths:
                results.append(
                    ImportResult(
                        file_path=source_path,
                        imported=False,
                        target_path=None,
                        error=error_msg,
                        method=None,
                    )
                )

            return results

    async def _get_manual_import_candidates(
        self, source_paths: List[Path], radarr_movie: RadarrMovie
    ) -> List[Dict[str, Any]]:
        """Get manual import candidates from Radarr for the given files.

        Args:
            source_paths: List of source file paths.
            radarr_movie: Radarr movie object.

        Returns:
            List of import candidate objects from Radarr.

        Raises:
            RadarrServiceError: If request fails.
        """
        try:
            # Build query parameters for the manual import endpoint
            folder_path = str(source_paths[0].parent) if source_paths else ""

            url = f"{self._radarr_config.url}/api/v3/manualimport"
            headers = {"X-Api-Key": self._radarr_config.api_key}
            params = {
                "folder": folder_path,
                "downloadId": "",  # Empty for manual import
                "filterExistingFiles": True,
            }

            response = await self._get_client().get(url, headers=headers, params=params)
            response.raise_for_status()
            candidates = response.json()

            # Filter candidates to match our specific movie and source files
            source_path_strs = {str(path) for path in source_paths}
            movie_id = radarr_movie["id"]
            filtered_candidates = [
                candidate
                for candidate in candidates
                if candidate.get("path") in source_path_strs
                and candidate.get("movie", {}).get("id") == movie_id
            ]

            self.logger.info(
                f"Found {len(filtered_candidates)} import candidates for {len(source_paths)} files"
            )
            return filtered_candidates

        except Exception as e:
            error_msg = f"Failed to get manual import candidates: {e}"
            self.logger.error(error_msg)
            raise RadarrServiceError(error_msg) from e

    async def _execute_manual_import(
        self, import_candidates: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Execute manual import for the given candidates.

        Args:
            import_candidates: List of import candidate objects from Radarr.

        Returns:
            List of import result objects from Radarr.

        Raises:
            RadarrServiceError: If import fails.
        """
        try:
            # Prepare import data - we need to tell Radarr to import these files
            import_data = []
            for candidate in import_candidates:
                import_item = {
                    "path": candidate["path"],
                    "movieId": candidate.get("movie", {}).get("id"),
                    "quality": candidate.get("quality", {"quality": {"id": 1}}),
                    "languages": candidate.get("languages", [{"id": 1}]),
                    "releaseGroup": candidate.get("releaseGroup", ""),
                    "downloadId": "",
                    "customFormats": candidate.get("customFormats", []),
                }
                import_data.append(import_item)

            if not import_data:
                return []

            # Execute the import
            url = f"{self._radarr_config.url}/api/v3/manualimport"
            headers = {"X-Api-Key": self._radarr_config.api_key}

            response = await self._get_client().post(url, headers=headers, json=import_data)
            response.raise_for_status()
            results: List[Dict[str, Any]] = response.json()

            self.logger.info(f"Executed manual import for {len(import_data)} files")
            return results

        except Exception as e:
            error_msg = f"Failed to execute manual import: {e}"
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

            response = await self._get_client().post(url, headers=headers, json=command_data)
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

            response = await self._get_client().delete(url, headers=headers, params=params)
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

            response = await self._get_client().get(url, headers=headers)
            response.raise_for_status()
            result = response.json()
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

    def _get_client(self) -> "httpx.AsyncClient":
        """Get or create HTTP client.

        Returns:
            HTTP client.
        """
        if self._client is None:
            # Simple httpx client with SSL verification disabled
            self._client = httpx.AsyncClient(
                timeout=self._radarr_config.timeout,
                verify=False,
            )
        return self._client

    async def close(self) -> None:
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

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
        if self._client and not self._client.is_closed:
            import logging

            logging.getLogger(__name__).debug("RadarrService client not properly closed")
