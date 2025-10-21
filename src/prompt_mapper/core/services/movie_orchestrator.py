"""Movie orchestrator service implementation."""

import time
from pathlib import Path
from typing import Any, List, Optional, Tuple

import click

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
from ..models.processing_result import ProcessingStatus, RadarrAction


class MovieOrchestrator(IMovieOrchestrator, LoggerMixin):
    """Movie orchestrator service implementation.

    Implements the simplified flow:
    - List all movie files recursively in a directory
    - For each file:
        - Check if it's a movie file
        - Clean filename to extract movie name and year
        - Search TMDB for candidates
        - LLM selects best match from candidates
        - If confidence < threshold, request manual selection
        - Add movie to Radarr (if not already present)
    """

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

    async def process_directory(
        self,
        directory: Path,
        user_prompt: str,
        auto_add: bool = False,
    ) -> SessionSummary:
        """Process all movie files in a directory.

        Implements the simplified pseudocode flow:
            files = list all files recursively in a directory
            for each file:
                is_movie_file(file)
                if not is_movie_file(file):
                    continue
                movie_name, movie_year = clean(file)
                search_results = search_tmdb(movie_name, movie_year)
                selected_movie, confidence = select_movie_using_llm(search_results, ...)
                if confidence < 0.95:
                    selected_movie = offer_to_manual_selection(search_results, ...)
                    confidence = 1.0
                add_movie_to_radarr(selected_movie)

        Args:
            directory: Directory path to process.
            user_prompt: User prompt for resolution guidance.
            auto_add: Automatically add to Radarr without confirmation.

        Returns:
            Session summary with all results.

        Raises:
            OrchestratorError: If processing fails.
        """
        session_start_time = time.time()
        summary = SessionSummary()

        try:
            self.logger.info(f"Processing directory: {directory}")

            # List all movie files recursively
            movie_files = await self._file_scanner.list_movie_files(directory)

            if not movie_files:
                self.logger.info("No movie files found")
                summary.total_processing_time_seconds = time.time() - session_start_time
                return summary

            click.echo(f"\nFound {len(movie_files)} movie file(s) to process")
            click.echo("=" * 70)

            # Process each file
            for i, movie_file in enumerate(movie_files, 1):
                click.echo(f"\n[{i}/{len(movie_files)}] Processing: {movie_file.name}")
                click.echo("-" * 70)

                result = await self._process_single_file(
                    movie_file=movie_file,
                    user_prompt=user_prompt,
                    auto_add=auto_add,
                )

                summary.add_result(result)

                # Display result
                self._display_result(result)

            summary.total_processing_time_seconds = time.time() - session_start_time

            # Display final summary
            click.echo("\n" + "=" * 70)
            click.echo("SESSION SUMMARY")
            click.echo("=" * 70)
            self._display_summary(summary)

            return summary

        except KeyboardInterrupt:
            click.echo("\n\nOperation cancelled by user.")
            summary.total_processing_time_seconds = time.time() - session_start_time
            return summary
        except Exception as e:
            error_msg = f"Processing failed: {e}"
            self.logger.error(error_msg)
            raise OrchestratorError(error_msg) from e

    async def _process_single_file(
        self,
        movie_file: Path,
        user_prompt: str,
        auto_add: bool,
    ) -> ProcessingResult:
        """Process a single movie file.

        Args:
            movie_file: Path to movie file.
            user_prompt: User prompt for resolution guidance.
            auto_add: Automatically add to Radarr.

        Returns:
            Processing result.
        """
        start_time = time.time()
        result = ProcessingResult(
            source_path=movie_file,
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
            # Step 1: Resolve movie from filename
            # This does: clean → search TMDB → LLM select → manual fallback
            movie_match = await self._movie_resolver.resolve_movie_from_filename(
                filename=movie_file.name,
                user_prompt=user_prompt,
            )

            result.movie_match = movie_match

            if not movie_match.movie_info.tmdb_id:
                result.error_message = "No TMDb ID found for movie"
                result.status = ProcessingStatus.FAILED
                return result

            # Step 2: Get full movie details from TMDb (if needed for Radarr)
            if self._config.radarr.enabled:
                full_movie_info = await self._tmdb_service.get_movie_details(
                    movie_match.movie_info.tmdb_id
                )
                if full_movie_info:
                    movie_match.movie_info = full_movie_info

            # Step 3: Add movie to Radarr
            if self._config.radarr.enabled:
                radarr_action, radarr_movie = await self._handle_radarr_integration(
                    movie_match, auto_add
                )
                result.radarr_action = radarr_action

                # Generate Radarr URL if movie was added or exists
                if radarr_movie:
                    result.radarr_url = f"{self._config.radarr.url}/movie/{radarr_movie['id']}"

            # Generate TMDb URL
            if movie_match.movie_info.tmdb_id:
                result.tmdb_url = (
                    f"https://www.themoviedb.org/movie/{movie_match.movie_info.tmdb_id}"
                )

            result.status = ProcessingStatus.SUCCESS
            self.logger.info(f"Successfully processed: {movie_match.movie_info.title}")

        except KeyboardInterrupt:
            result.status = ProcessingStatus.USER_CANCELLED
            result.error_message = "Cancelled by user"
            raise  # Re-raise to stop processing other files
        except Exception as e:
            result.status = ProcessingStatus.FAILED
            result.error_message = str(e)
            self.logger.error(f"Failed to process {movie_file.name}: {e}")

        finally:
            result.processing_time_seconds = time.time() - start_time

        return result

    async def _handle_radarr_integration(
        self, movie_match: Any, auto_add: bool
    ) -> Tuple[RadarrAction, Optional[RadarrMovie]]:
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
            if auto_add or self._config.matching.auto_add_to_radarr:
                new_movie = await self._radarr_service.add_movie(movie_match.movie_info)
                self.logger.info(f"Added to Radarr: {movie_match.movie_info.title}")
                return RadarrAction.ADDED, new_movie
            else:
                # Ask user for confirmation
                try:
                    if click.confirm(
                        f"\nAdd '{movie_match.movie_info.title}' to Radarr?", default=True
                    ):
                        new_movie = await self._radarr_service.add_movie(movie_match.movie_info)
                        self.logger.info(f"Added to Radarr: {movie_match.movie_info.title}")
                        return RadarrAction.ADDED, new_movie
                    else:
                        self.logger.info("User skipped adding to Radarr")
                        return RadarrAction.SKIPPED, None
                except (EOFError, KeyboardInterrupt):
                    return RadarrAction.SKIPPED, None

        except Exception as e:
            self.logger.error(f"Radarr integration failed: {e}")
            return RadarrAction.FAILED, None

    async def validate_prerequisites(self) -> List[str]:
        """Validate that all prerequisites are met.

        Returns:
            List of validation errors (empty if all valid).
        """
        errors = []

        try:
            # Check LLM service
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

    def _display_result(self, result: ProcessingResult) -> None:
        """Display processing result.

        Args:
            result: Processing result to display.
        """
        if result.status == ProcessingStatus.SUCCESS:
            click.echo("✓ Status: SUCCESS")
            if result.movie_match:
                movie = result.movie_match.movie_info
                click.echo(f"  Movie: {movie.title} ({movie.year})")
                click.echo(f"  TMDb ID: {movie.tmdb_id}")
                click.echo(f"  Confidence: {result.movie_match.confidence:.2f}")
                if result.tmdb_url:
                    click.echo(f"  TMDb: {result.tmdb_url}")

            if result.radarr_action:
                action_display = {
                    RadarrAction.ADDED: "✓ Added to Radarr",
                    RadarrAction.EXISTS: "= Already in Radarr",
                    RadarrAction.SKIPPED: "⊘ Skipped",
                    RadarrAction.FAILED: "✗ Failed",
                }
                click.echo(
                    f"  Radarr: {action_display.get(result.radarr_action, result.radarr_action.value)}"
                )
                if result.radarr_url:
                    click.echo(f"  Radarr URL: {result.radarr_url}")

        elif result.status == ProcessingStatus.FAILED:
            click.echo("✗ Status: FAILED")
            if result.error_message:
                click.echo(f"  Error: {result.error_message}")

        elif result.status == ProcessingStatus.SKIPPED:
            click.echo("⊘ Status: SKIPPED")
            if result.error_message:
                click.echo(f"  Reason: {result.error_message}")

    def _display_summary(self, summary: SessionSummary) -> None:
        """Display session summary.

        Args:
            summary: Session summary to display.
        """
        click.echo(f"Total Processed: {summary.total_processed}")
        click.echo(f"Successful: {summary.successful}")
        click.echo(f"Failed: {summary.failed}")
        click.echo(f"Skipped: {summary.skipped}")

        if summary.total_processed > 0:
            click.echo(f"Success Rate: {summary.success_rate:.1%}")

        click.echo(f"Movies Added to Radarr: {summary.movies_added_to_radarr}")
        click.echo(f"Total Time: {summary.total_processing_time_seconds:.1f}s")

        if summary.successful > 0:
            avg_time = summary.total_processing_time_seconds / summary.successful
            click.echo(f"Average Time per Movie: {avg_time:.1f}s")
