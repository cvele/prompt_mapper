"""Movie orchestrator service implementation."""

import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from ...config.models import Config
from ...infrastructure.logging import LoggerMixin
from ...utils import OrchestratorError
from ..interfaces import (
    IFileScanner,
    ILLMService,
    IMovieOrchestrator,
    IMovieResolver,
    IRadarrService,
    ITMDbService,
)
from ..interfaces.radarr_service import RadarrMovie
from ..models import ProcessingResult, SessionSummary
from ..models.file_info import ScanResult
from ..models.llm_response import LLMResponse
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
        llm_service: ILLMService,
    ):
        """Initialize movie orchestrator.

        Args:
            config: Application configuration.
            file_scanner: File scanner service.
            movie_resolver: Movie resolver service.
            radarr_service: Radarr service.
            tmdb_service: TMDb service.
            llm_service: LLM service.
        """
        self._config = config
        self._file_scanner = file_scanner
        self._movie_resolver = movie_resolver
        self._radarr_service = radarr_service
        self._tmdb_service = tmdb_service
        self._llm_service = llm_service
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

            # If multiple video files, process each one individually
            if len(scan_result.video_files) > 1:
                movie_count = len(scan_result.video_files)
                self.logger.info(f"Found {movie_count} video files, processing each individually")

                # Process each video file as a separate movie
                summary = SessionSummary()
                for i, video_file in enumerate(scan_result.video_files):
                    self.logger.info(
                        f"Processing {i+1}/{len(scan_result.video_files)}: {video_file.name}"
                    )

                    # Create single-file scan result
                    single_scan = ScanResult(
                        root_path=scan_result.root_path,
                        video_files=[video_file],
                        subtitle_files=[],  # Keep it simple
                        ignored_files=[],
                        total_size_bytes=video_file.size_bytes,
                        scan_depth=1,
                    )

                    # Process this single video using LLM batch (with single item)
                    try:
                        if dry_run:
                            # In dry-run mode, create a mock movie match
                            from ..models.movie import MovieInfo, MovieMatch

                            mock_llm_response = LLMResponse(
                                canonical_title=f"Mock Movie ({video_file.name})",
                                year=2023,
                                confidence=0.8,
                                rationale="Dry-run mode - mock response",
                                director=None,
                                edition_notes=None,
                            )

                            mock_movie_info = MovieInfo(
                                title=f"Mock Movie ({video_file.name})",
                                year=2023,
                                tmdb_id=12345,
                                imdb_id=None,
                                overview=None,
                                poster_path=None,
                                backdrop_path=None,
                                original_title=None,
                                original_language=None,
                                release_date=None,
                                runtime=None,
                                popularity=None,
                                vote_average=None,
                                vote_count=None,
                            )

                            movie_match = MovieMatch(
                                movie_info=mock_movie_info,
                                confidence=0.8,
                                llm_response=mock_llm_response,
                                candidates=[],
                                selected_automatically=True,
                                user_confirmed=False,
                                rationale="Dry-run mode - mock match",
                            )
                        else:
                            # Create context from scan result
                            context = f"Directory: {single_scan.root_path.name}"

                            # Use LLM batch processing with single movie
                            movies_data = [
                                {"file_info": single_scan.video_files, "context": context}
                            ]

                            llm_responses = await self._llm_service.resolve_movies_batch(
                                movies_data, user_prompt
                            )

                            if not llm_responses:
                                raise Exception("No LLM response received")

                            llm_response = llm_responses[0]

                            # Resolve movie from LLM response
                            movie_match = (
                                await self._movie_resolver.resolve_movie_from_llm_response(
                                    scan_result=single_scan,
                                    llm_response=llm_response,
                                    confidence_threshold=self._config.matching.confidence_threshold,
                                )
                            )

                        single_result = ProcessingResult(
                            source_path=video_file.path,
                            status=ProcessingStatus.SUCCESS,
                            scan_result=single_scan,
                            movie_match=movie_match,
                            radarr_action=None,
                            error_message=None,
                            processing_time_seconds=1.0,  # Placeholder
                            tmdb_url=None,
                            radarr_url=None,
                        )
                    except Exception as e:
                        single_result = ProcessingResult(
                            source_path=video_file.path,
                            status=ProcessingStatus.FAILED,
                            scan_result=single_scan,
                            movie_match=None,
                            radarr_action=None,
                            error_message=str(e),
                            processing_time_seconds=1.0,
                            tmdb_url=None,
                            radarr_url=None,
                        )
                    summary.add_result(single_result)

                # Convert summary to single result
                result.status = (
                    ProcessingStatus.SUCCESS if summary.successful > 0 else ProcessingStatus.FAILED
                )
                result.error_message = f"Processed {summary.total_processed} movies: {summary.successful} successful, {summary.failed} failed"
                return result

            # Single video file - process using LLM batch (with single item)
            if dry_run:
                # In dry-run mode, create a mock movie match
                from ..models.movie import MovieInfo, MovieMatch

                mock_llm_response = LLMResponse(
                    canonical_title=f"Mock Movie ({scan_result.root_path.name})",
                    year=2023,
                    confidence=0.8,
                    rationale="Dry-run mode - mock response",
                    director=None,
                    edition_notes=None,
                )

                mock_movie_info = MovieInfo(
                    title=f"Mock Movie ({scan_result.root_path.name})",
                    year=2023,
                    tmdb_id=12345,
                    imdb_id=None,
                    overview=None,
                    poster_path=None,
                    backdrop_path=None,
                    original_title=None,
                    original_language=None,
                    release_date=None,
                    runtime=None,
                    popularity=None,
                    vote_average=None,
                    vote_count=None,
                )

                movie_match = MovieMatch(
                    movie_info=mock_movie_info,
                    confidence=0.8,
                    llm_response=mock_llm_response,
                    candidates=[],
                    selected_automatically=True,
                    user_confirmed=False,
                    rationale="Dry-run mode - mock match",
                )
            else:
                # Create context from scan result
                context = f"Directory: {scan_result.root_path.name}"
                if scan_result.has_multiple_videos:
                    context += f"; Multiple videos: {len(scan_result.video_files)} files"

                # Use LLM batch processing with single movie
                movies_data = [{"file_info": scan_result.video_files, "context": context}]

                llm_responses = await self._llm_service.resolve_movies_batch(
                    movies_data, user_prompt
                )

                if not llm_responses:
                    result.error_message = "No LLM response received"
                    result.status = ProcessingStatus.FAILED
                    return result

                llm_response = llm_responses[0]

                # Resolve movie from LLM response
                movie_match = await self._movie_resolver.resolve_movie_from_llm_response(
                    scan_result=scan_result,
                    llm_response=llm_response,
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

                    await self._radarr_service.import_movie_files(
                        radarr_movie=radarr_movie, source_paths=video_paths, import_mode=import_mode
                    )

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
        session_start_time = time.time()
        summary = SessionSummary()

        try:
            self.logger.info(f"Starting batch processing of {len(paths)} directories")

            # Scan all directories first
            scan_results = []
            for path in paths:
                try:
                    scan_result = await self._file_scanner.scan_directory(path)
                    if scan_result.video_files:
                        scan_results.append((path, scan_result))
                    else:
                        # Create skipped result for directories with no video files
                        skipped_result = ProcessingResult(
                            source_path=path,
                            status=ProcessingStatus.SKIPPED,
                            scan_result=scan_result,
                            movie_match=None,
                            radarr_action=None,
                            error_message="No video files found",
                            processing_time_seconds=0.0,
                            tmdb_url=None,
                            radarr_url=None,
                        )
                        summary.add_result(skipped_result)
                except Exception as e:
                    # Create error result for scan failures
                    error_result = ProcessingResult(
                        source_path=path,
                        status=ProcessingStatus.FAILED,
                        scan_result=None,
                        movie_match=None,
                        radarr_action=None,
                        error_message=f"Scan failed: {e}",
                        processing_time_seconds=0.0,
                        tmdb_url=None,
                        radarr_url=None,
                    )
                    summary.add_result(error_result)

            # Process movies in batches using LLM batching
            batch_size = self._config.app.batch_size
            for i in range(0, len(scan_results), batch_size):
                batch_scan_results = scan_results[i : i + batch_size]
                batch_results = await self._process_movie_batch(
                    batch_scan_results, user_prompt, dry_run, auto_add, auto_import
                )
                for result in batch_results:
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

    async def _process_movie_batch(
        self,
        batch_scan_results: List[tuple[Path, ScanResult]],
        user_prompt: str,
        dry_run: bool,
        auto_add: bool,
        auto_import: bool,
    ) -> List[ProcessingResult]:
        """Process a batch of movies using LLM batching.

        Args:
            batch_scan_results: List of (path, scan_result) tuples.
            user_prompt: User prompt for resolution guidance.
            dry_run: If True, don't make actual changes.
            auto_add: Automatically add to Radarr without confirmation.
            auto_import: Automatically import files without confirmation.

        Returns:
            List of processing results.
        """
        if not batch_scan_results:
            return []

        batch_start_time = time.time()
        results = []

        try:
            # Prepare movies data for LLM batch processing
            movies_data: List[Optional[Dict[str, Any]]] = []
            for path, scan_result in batch_scan_results:
                # Handle multiple video files by processing the main one
                main_video = scan_result.main_video_file
                if main_video:
                    # Create context from scan result
                    context = f"Directory: {scan_result.root_path.name}"
                    if scan_result.has_multiple_videos:
                        context += f"; Multiple videos: {len(scan_result.video_files)} files"

                    movies_data.append({"file_info": scan_result.video_files, "context": context})
                else:
                    # Skip if no main video file
                    movies_data.append(None)

            # Filter out None entries and keep track of indices
            valid_movies_data = []
            valid_indices = []
            for i, movie_data in enumerate(movies_data):
                if movie_data is not None:
                    valid_movies_data.append(movie_data)
                    valid_indices.append(i)

            # Process valid movies with LLM batch
            llm_responses: List[LLMResponse] = []
            if valid_movies_data:
                if dry_run:
                    # In dry-run mode, create mock responses

                    llm_responses = []
                    for i, movie_data in enumerate(valid_movies_data):
                        mock_response = LLMResponse(
                            canonical_title=f"Mock Movie {i+1}",
                            year=2023,
                            confidence=0.8,
                            rationale="Dry-run mode - mock response",
                            director=None,
                            edition_notes=None,
                        )
                        llm_responses.append(mock_response)
                else:
                    try:
                        llm_responses = await self._llm_service.resolve_movies_batch(
                            valid_movies_data, user_prompt
                        )
                    except Exception as e:
                        self.logger.error(f"LLM batch processing failed: {e}")
                        # Create error results for all movies in this batch
                        for path, scan_result in batch_scan_results:
                            error_result = ProcessingResult(
                                source_path=path,
                                status=ProcessingStatus.FAILED,
                                scan_result=scan_result,
                                movie_match=None,
                                radarr_action=None,
                                error_message=f"LLM batch processing failed: {e}",
                                processing_time_seconds=time.time() - batch_start_time,
                                tmdb_url=None,
                                radarr_url=None,
                            )
                            results.append(error_result)
                        return results

            # Process each movie result
            llm_response_index = 0
            for i, (path, scan_result) in enumerate(batch_scan_results):
                movie_start_time = time.time()

                if i not in valid_indices:
                    # Create skipped result for movies without valid video files
                    result = ProcessingResult(
                        source_path=path,
                        status=ProcessingStatus.SKIPPED,
                        scan_result=scan_result,
                        movie_match=None,
                        radarr_action=None,
                        error_message="No valid video files found",
                        processing_time_seconds=time.time() - movie_start_time,
                        tmdb_url=None,
                        radarr_url=None,
                    )
                    results.append(result)
                    continue

                # Get the LLM response for this movie
                llm_response = llm_responses[llm_response_index]
                llm_response_index += 1

                try:
                    if dry_run:
                        # In dry-run mode, create a mock movie match
                        from ..models.movie import MovieInfo, MovieMatch

                        mock_movie_info = MovieInfo(
                            title=llm_response.canonical_title,
                            year=llm_response.year,
                            tmdb_id=12345,
                            imdb_id=None,
                            overview=None,
                            poster_path=None,
                            backdrop_path=None,
                            original_title=None,
                            original_language=None,
                            release_date=None,
                            runtime=None,
                            popularity=None,
                            vote_average=None,
                            vote_count=None,
                        )

                        movie_match = MovieMatch(
                            movie_info=mock_movie_info,
                            confidence=llm_response.confidence,
                            llm_response=llm_response,
                            candidates=[],
                            selected_automatically=True,
                            user_confirmed=False,
                            rationale="Dry-run mode - mock match",
                        )
                    else:
                        # Resolve movie from LLM response using movie resolver
                        movie_match = await self._movie_resolver.resolve_movie_from_llm_response(
                            scan_result=scan_result,
                            llm_response=llm_response,
                            confidence_threshold=self._config.matching.confidence_threshold,
                        )

                    # Handle Radarr integration and file import
                    radarr_action = None
                    if (
                        self._config.radarr.enabled
                        and not dry_run
                        and movie_match.movie_info.tmdb_id
                    ):
                        # Get full movie details from TMDb
                        full_movie_info = await self._tmdb_service.get_movie_details(
                            movie_match.movie_info.tmdb_id
                        )
                        if full_movie_info:
                            movie_match.movie_info = full_movie_info

                        radarr_action, radarr_movie = await self._handle_radarr_integration(
                            movie_match, auto_add
                        )

                        # Import files if requested
                        if radarr_movie and (auto_import or self._config.matching.auto_import):
                            import_mode = self._config.radarr.import_config.mode
                            video_paths = [f.path for f in scan_result.video_files]

                            await self._radarr_service.import_movie_files(
                                radarr_movie=radarr_movie,
                                source_paths=video_paths,
                                import_mode=import_mode,
                            )

                    # Generate URLs for reference
                    tmdb_url = None
                    if movie_match.movie_info.tmdb_id:
                        tmdb_url = (
                            f"https://www.themoviedb.org/movie/{movie_match.movie_info.tmdb_id}"
                        )

                    result = ProcessingResult(
                        source_path=path,
                        status=ProcessingStatus.SUCCESS,
                        scan_result=scan_result,
                        movie_match=movie_match,
                        radarr_action=radarr_action,
                        error_message=None,
                        processing_time_seconds=time.time() - movie_start_time,
                        tmdb_url=tmdb_url,
                        radarr_url=None,
                    )
                    results.append(result)

                except Exception as e:
                    error_result = ProcessingResult(
                        source_path=path,
                        status=ProcessingStatus.FAILED,
                        scan_result=scan_result,
                        movie_match=None,
                        radarr_action=None,
                        error_message=str(e),
                        processing_time_seconds=time.time() - movie_start_time,
                        tmdb_url=None,
                        radarr_url=None,
                    )
                    results.append(error_result)

            return results

        except Exception as e:
            self.logger.error(f"Batch processing failed: {e}")
            # Create error results for all movies in this batch
            for path, scan_result in batch_scan_results:
                error_result = ProcessingResult(
                    source_path=path,
                    status=ProcessingStatus.FAILED,
                    scan_result=scan_result,
                    movie_match=None,
                    radarr_action=None,
                    error_message=f"Batch processing failed: {e}",
                    processing_time_seconds=time.time() - batch_start_time,
                    tmdb_url=None,
                    radarr_url=None,
                )
                results.append(error_result)
            return results
