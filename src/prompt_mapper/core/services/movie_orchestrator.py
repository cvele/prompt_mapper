"""Movie orchestrator service implementation."""

import asyncio
import time
from pathlib import Path
from typing import List, Optional

from ...config.models import Config
from ...infrastructure.logging import LoggerMixin
from ...utils import OrchestratorError
from ..interfaces import (
    IFileScanner,
    IMovieOrchestrator,
    IMovieResolver,
    IRadarrService,
    ITMDbService,
)
from ..interfaces.radarr_service import RadarrMovie
from ..models import ProcessingResult, SessionSummary
from ..models.file_info import ScanResult
from ..models.movie import MovieMatch
from ..models.processing_result import ProcessingStatus, RadarrAction


class MovieOrchestrator(IMovieOrchestrator, LoggerMixin):
    """Movie orchestrator service implementation."""

    def __init__(
        self,
        config: Config,
        file_scanner: IFileScanner,
        movie_resolver: IMovieResolver,
        radarr_service: IRadarrService,
        tmdb_service: ITMDbService,
    ):
        """Initialize movie orchestrator.

        Args:
            config: Application configuration.
            file_scanner: File scanner service.
            movie_resolver: Movie resolver service.
            radarr_service: Radarr service.
            tmdb_service: TMDb service.
        """
        self._config = config
        self._file_scanner = file_scanner
        self._movie_resolver = movie_resolver
        self._radarr_service = radarr_service
        self._tmdb_service = tmdb_service
        self._interactive = config.app.interactive

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
        start_time = time.time()
        result = ProcessingResult(
            source_path=path,
            status=ProcessingStatus.FAILED,
            scan_result=None,
            movie_match=None,
            radarr_action=None,
            error_message=None,
            processing_time_seconds=None,
            tmdb_url=None,
            radarr_url=None,
        )

        try:
            self.logger.info(f"Processing movie: {path}")

            # Step 1: Scan directory
            scan_result = await self._file_scanner.scan_directory(path)
            result.scan_result = scan_result

            if not scan_result.video_files:
                result.error_message = "No video files found"
                result.status = ProcessingStatus.SKIPPED
                return result

            # Check if this is a flat directory with multiple movies
            if len(scan_result.video_files) > 1 and not self._is_single_movie_directory(
                scan_result
            ):
                # This is a flat directory with multiple movies - process as batch
                self.logger.info(
                    f"Detected flat directory with {len(scan_result.video_files)} movies, switching to batch mode"
                )
                individual_paths = self._create_individual_movie_paths(scan_result)
                summary = await self.process_batch(
                    paths=individual_paths,
                    user_prompt=user_prompt,
                    dry_run=dry_run,
                    auto_add=auto_add,
                    auto_import=auto_import,
                    max_parallel=self._config.app.parallel_workers,
                )
                # Convert summary to single result for API compatibility
                result.status = (
                    ProcessingStatus.SUCCESS if summary.successful > 0 else ProcessingStatus.FAILED
                )
                result.error_message = f"Batch processed {summary.total_processed} movies: {summary.successful} successful, {summary.failed} failed"
                return result

            # Step 2: Resolve movie (single movie case)
            movie_match = await self._movie_resolver.resolve_movie(
                scan_result=scan_result,
                user_prompt=user_prompt,
                confidence_threshold=self._config.matching.confidence_threshold,
            )
            result.movie_match = movie_match

            if not movie_match.movie_info.tmdb_id:
                result.error_message = "No TMDb ID found for movie"
                result.status = ProcessingStatus.FAILED
                return result

            # Step 3: Get full movie details for Radarr
            if movie_match.movie_info.tmdb_id and self._config.radarr.enabled:
                # Get complete movie details from TMDb
                full_movie_info = await self._tmdb_service.get_movie_details(
                    movie_match.movie_info.tmdb_id
                )
                if full_movie_info:
                    movie_match.movie_info = full_movie_info

            # Step 4: Handle Radarr integration
            if self._config.radarr.enabled and not dry_run:
                radarr_action, radarr_movie = await self._handle_radarr_integration(
                    movie_match, auto_add
                )
                result.radarr_action = radarr_action

                # Step 5: Import files if requested
                if radarr_movie and (auto_import or self._config.matching.auto_import):
                    import_mode = self._config.radarr.import_config.mode
                    video_paths = [f.path for f in scan_result.video_files]

                    import_results = await self._radarr_service.import_movie_files(
                        radarr_movie=radarr_movie, source_paths=video_paths, import_mode=import_mode
                    )
                    result.import_results = import_results

            # Generate URLs for reference
            if movie_match.movie_info.tmdb_id:
                result.tmdb_url = (
                    f"https://www.themoviedb.org/movie/{movie_match.movie_info.tmdb_id}"
                )

            result.status = ProcessingStatus.SUCCESS
            self.logger.info(f"Successfully processed: {movie_match.movie_info.title}")

        except KeyboardInterrupt:
            result.status = ProcessingStatus.USER_CANCELLED
            result.error_message = "Cancelled by user"
        except Exception as e:
            result.status = ProcessingStatus.FAILED
            result.error_message = str(e)
            self.logger.error(f"Failed to process {path}: {e}")

        finally:
            result.processing_time_seconds = time.time() - start_time

        return result

    async def process_batch(
        self,
        paths: List[Path],
        user_prompt: str,
        dry_run: bool = False,
        auto_add: bool = False,
        auto_import: bool = False,
        max_parallel: int = 3,
    ) -> SessionSummary:
        """Process multiple movie directories in batch.

        Args:
            paths: List of paths to movie directories.
            user_prompt: User prompt for resolution guidance.
            dry_run: If True, don't make actual changes.
            auto_add: Automatically add to Radarr without confirmation.
            auto_import: Automatically import files without confirmation.
            max_parallel: Maximum number of parallel operations.

        Returns:
            Session summary with all results.

        Raises:
            OrchestratorError: If batch processing fails.
        """
        session_start_time = time.time()
        summary = SessionSummary()

        try:
            self.logger.info(f"Starting batch processing of {len(paths)} directories")

            # Process in batches to limit parallel operations
            semaphore = asyncio.Semaphore(max_parallel)

            async def process_with_semaphore(path: Path) -> ProcessingResult:
                async with semaphore:
                    return await self.process_single_movie(
                        path=path,
                        user_prompt=user_prompt,
                        dry_run=dry_run,
                        auto_add=auto_add,
                        auto_import=auto_import,
                    )

            # Execute all processing tasks
            tasks = [process_with_semaphore(path) for path in paths]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Process results
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    # Create error result
                    error_result = ProcessingResult(
                        source_path=paths[i],
                        status=ProcessingStatus.FAILED,
                        scan_result=None,
                        movie_match=None,
                        radarr_action=None,
                        error_message=str(result),
                        processing_time_seconds=None,
                        tmdb_url=None,
                        radarr_url=None,
                    )
                    summary.add_result(error_result)
                else:
                    # result is guaranteed to be ProcessingResult here
                    assert isinstance(result, ProcessingResult)
                    summary.add_result(result)

            summary.total_processing_time_seconds = time.time() - session_start_time

            self.logger.info(
                f"Batch processing completed: {summary.successful}/{summary.total_processed} successful"
            )

            return summary

        except Exception as e:
            error_msg = f"Batch processing failed: {e}"
            self.logger.error(error_msg)
            raise OrchestratorError(error_msg) from e

    async def validate_prerequisites(self) -> List[str]:
        """Validate that all prerequisites are met.

        Returns:
            List of validation errors (empty if all valid).
        """
        errors = []

        try:
            # Check LLM service (basic validation)
            if not self._config.llm.api_key:
                errors.append("LLM API key not configured")

            # Check TMDb service
            if not self._config.tmdb.api_key:
                errors.append("TMDb API key not configured")

            # Check Radarr service if enabled
            if self._config.radarr.enabled:
                if not self._config.radarr.api_key:
                    errors.append("Radarr API key not configured")
                elif not self._radarr_service.is_available():
                    errors.append("Radarr service is not available")

            return errors

        except Exception as e:
            errors.append(f"Validation error: {e}")
            return errors

    def set_interactive_mode(self, interactive: bool) -> None:
        """Set interactive mode for user confirmations.

        Args:
            interactive: Whether to prompt user for confirmations.
        """
        self._interactive = interactive

    async def _handle_radarr_integration(
        self, movie_match: MovieMatch, auto_add: bool
    ) -> tuple[RadarrAction, Optional[RadarrMovie]]:
        """Handle Radarr integration for a movie match.

        Args:
            movie_match: Movie match result.
            auto_add: Whether to automatically add movies.

        Returns:
            Tuple of (RadarrAction, radarr_movie_object).
        """
        try:
            # Check if movie already exists in Radarr
            tmdb_id = movie_match.movie_info.tmdb_id
            if tmdb_id is None:
                raise ValueError("Movie TMDb ID is required for Radarr integration")

            existing_movie = await self._radarr_service.get_movie_by_tmdb_id(tmdb_id)

            if existing_movie:
                self.logger.info(f"Movie already exists in Radarr: {movie_match.movie_info.title}")
                return RadarrAction.EXISTS, existing_movie

            # Add movie to Radarr
            if auto_add or self._config.matching.auto_add_to_radarr or not self._interactive:
                new_movie = await self._radarr_service.add_movie(movie_match.movie_info)
                return RadarrAction.ADDED, new_movie
            else:
                # Ask user for confirmation
                import click

                try:
                    if click.confirm(f"Add '{movie_match.movie_info.title}' to Radarr?"):
                        new_movie = await self._radarr_service.add_movie(movie_match.movie_info)
                        return RadarrAction.ADDED, new_movie
                    else:
                        return RadarrAction.SKIPPED, None
                except (EOFError, KeyboardInterrupt):
                    return RadarrAction.SKIPPED, None

        except Exception as e:
            self.logger.error(f"Radarr integration failed: {e}")
            return RadarrAction.FAILED, None

    def _is_single_movie_directory(self, scan_result: ScanResult) -> bool:
        """Check if directory contains files for a single movie.

        Args:
            scan_result: Scan result to analyze.

        Returns:
            True if this appears to be a single movie directory.
        """
        # If there's only one video file, it's definitely single movie
        if len(scan_result.video_files) <= 1:
            return True

        # Check if all video files have very similar names (might be multiple parts)
        if len(scan_result.video_files) <= 3:
            main_file = scan_result.main_video_file
            if main_file:
                main_name = main_file.name.lower()
                # Remove common part indicators
                base_name = (
                    main_name.replace("cd1", "")
                    .replace("cd2", "")
                    .replace("part1", "")
                    .replace("part2", "")
                )
                base_name = base_name.replace("disc1", "").replace("disc2", "")

                similar_count = 0
                for file in scan_result.video_files:
                    file_name = file.name.lower()
                    file_base = (
                        file_name.replace("cd1", "")
                        .replace("cd2", "")
                        .replace("part1", "")
                        .replace("part2", "")
                    )
                    file_base = file_base.replace("disc1", "").replace("disc2", "")

                    # If names are very similar (after removing part indicators), consider it single movie
                    if self._calculate_name_similarity(base_name, file_base) > 0.8:
                        similar_count += 1

                if similar_count == len(scan_result.video_files):
                    return True

        # Otherwise, assume it's multiple movies
        return False

    def _calculate_name_similarity(self, name1: str, name2: str) -> float:
        """Calculate similarity between two names.

        Args:
            name1: First name.
            name2: Second name.

        Returns:
            Similarity score between 0.0 and 1.0.
        """
        from difflib import SequenceMatcher

        return SequenceMatcher(None, name1, name2).ratio()

    def _create_individual_movie_paths(self, scan_result: ScanResult) -> List[Path]:
        """Create individual movie paths for batch processing.

        Args:
            scan_result: Scan result with multiple movies.

        Returns:
            List of paths to process individually.
        """
        import shutil
        import tempfile

        individual_paths = []
        temp_dir = Path(tempfile.mkdtemp(prefix="prompt_mapper_batch_"))

        try:
            for video_file in scan_result.video_files:
                # Create individual directory for each movie
                movie_name = (
                    video_file.name.replace(".mkv", "").replace(".mp4", "").replace(".avi", "")
                )
                movie_dir = temp_dir / movie_name
                movie_dir.mkdir(exist_ok=True)

                # Copy video file
                shutil.copy2(video_file.path, movie_dir / video_file.name)

                # Copy matching subtitle if exists
                subtitle_name = (
                    video_file.name.replace(".mkv", ".srt")
                    .replace(".mp4", ".srt")
                    .replace(".avi", ".srt")
                )
                for subtitle_file in scan_result.subtitle_files:
                    if subtitle_file.name == subtitle_name:
                        shutil.copy2(subtitle_file.path, movie_dir / subtitle_file.name)
                        break

                individual_paths.append(movie_dir)

            return individual_paths

        except Exception as e:
            self.logger.error(f"Failed to create individual movie paths: {e}")
            return []
