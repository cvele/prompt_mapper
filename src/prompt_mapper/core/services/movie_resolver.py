"""Movie resolver service implementation."""

from typing import List, Optional

import click

from ...config.models import Config
from ...infrastructure.logging import LoggerMixin
from ...utils import MovieResolverError
from ..interfaces import ILLMService, IMovieResolver, ITMDbService
from ..models import LLMResponse, MovieCandidate, MovieMatch, ScanResult


class MovieResolver(IMovieResolver, LoggerMixin):
    """Movie resolver service implementation."""

    def __init__(self, config: Config, llm_service: ILLMService, tmdb_service: ITMDbService):
        """Initialize movie resolver.

        Args:
            config: Application configuration.
            llm_service: LLM service for movie resolution.
            tmdb_service: TMDb service for movie search.
        """
        self._config = config
        self._llm_service = llm_service
        self._tmdb_service = tmdb_service
        self._interactive = config.app.interactive

    async def resolve_movie_from_llm_response(
        self, scan_result: ScanResult, llm_response: LLMResponse, confidence_threshold: float = 0.8
    ) -> MovieMatch:
        """Resolve movie from LLM response and scan result.

        Args:
            scan_result: File scan result.
            llm_response: LLM response with movie information.
            confidence_threshold: Minimum confidence for auto-selection.

        Returns:
            Movie match result.

        Raises:
            MovieResolverError: If resolution fails.
        """
        try:
            # Step 1: Search TMDb for candidates
            candidates = await self._tmdb_service.search_movies(
                llm_response, max_results=self._config.matching.max_search_results
            )

            if not candidates:
                raise MovieResolverError("No movie candidates found")

            # Step 2: Determine if we can auto-select
            top_candidate = candidates[0]
            combined_confidence = self._calculate_combined_confidence(
                llm_response.confidence, top_candidate.match_score
            )

            auto_select = (
                combined_confidence >= confidence_threshold
                and top_candidate.match_score >= confidence_threshold
            )

            selected_candidate = None
            user_confirmed = False

            if auto_select:
                selected_candidate = top_candidate
                self.logger.info(f"Auto-selected movie: {selected_candidate.movie_info.title}")
            else:
                # Step 3: Get user choice
                choice_index = await self.get_user_choice(scan_result, candidates, llm_response)
                if choice_index is not None:
                    selected_candidate = candidates[choice_index]
                    user_confirmed = True
                    self.logger.info(f"User selected movie: {selected_candidate.movie_info.title}")

            if selected_candidate is None:
                raise MovieResolverError("No movie selected")

            # Create movie match
            movie_match = MovieMatch(
                movie_info=selected_candidate.movie_info,
                confidence=combined_confidence,
                llm_response=llm_response,
                candidates=candidates,
                selected_automatically=auto_select,
                user_confirmed=user_confirmed,
                rationale=f"LLM: {llm_response.rationale}; Match score: {selected_candidate.match_score:.3f}",
            )

            return movie_match

        except Exception as e:
            error_msg = f"Movie resolution failed: {e}"
            self.logger.error(error_msg)
            raise MovieResolverError(error_msg) from e

    async def get_user_choice(
        self,
        scan_result: ScanResult,
        candidates: List[MovieCandidate],
        llm_response: Optional[LLMResponse] = None,
    ) -> Optional[int]:
        """Get user choice from movie candidates.

        Args:
            scan_result: Original scan result.
            candidates: List of movie candidates.
            llm_response: Original LLM response.

        Returns:
            Selected candidate index or None if skipped.
        """
        if not candidates:
            return None

        # Display information
        click.echo(f"\nAnalyzing: {scan_result.root_path.name}")
        if llm_response:
            click.echo(f"LLM suggests: {llm_response.canonical_title}")
            if llm_response.year:
                click.echo(f"Year: {llm_response.year}")
            click.echo(f"LLM confidence: {llm_response.confidence:.2f}")
            if llm_response.rationale:
                click.echo(f"Reasoning: {llm_response.rationale}")

        click.echo(f"\nFound {len(candidates)} candidate(s):")

        # Show candidates
        for i, candidate in enumerate(candidates):
            movie = candidate.movie_info
            click.echo(f"  {i + 1}. {movie.title} ({movie.year or 'Unknown'})")
            click.echo(f"     TMDb ID: {movie.tmdb_id}, Score: {candidate.match_score:.3f}")
            if movie.overview:
                overview = (
                    movie.overview[:100] + "..." if len(movie.overview) > 100 else movie.overview
                )
                click.echo(f"     {overview}")

        # Get user choice

        # Check if we're in a non-interactive environment
        if not self._interactive:
            # Non-interactive mode - auto-select first candidate
            click.echo("Non-interactive mode: auto-selecting first candidate")
            return 0

        # Interactive mode - use click.prompt for proper input handling
        while True:
            try:
                choice = click.prompt(
                    f"\nSelect movie (1-{len(candidates)}) or 's' to skip",
                    type=str,
                    default="1",
                    show_default=True,
                ).strip()

                if choice.lower() == "s":
                    return None

                try:
                    choice_num = int(choice)
                    if 1 <= choice_num <= len(candidates):
                        return choice_num - 1
                    else:
                        click.echo(
                            f"Please enter a number between 1 and {len(candidates)}, or 's' to skip"
                        )
                        continue
                except ValueError:
                    click.echo("Invalid input. Please enter a number or 's' to skip.")
                    continue

            except (click.Abort, KeyboardInterrupt):
                click.echo("\nOperation cancelled.")
                return None
            except Exception as e:
                click.echo(f"Input error: {e}")
                # Fallback to auto-select after error
                click.echo("Falling back to auto-selection.")
                return 0

    def _calculate_combined_confidence(self, llm_confidence: float, match_score: float) -> float:
        """Calculate combined confidence from LLM and match scores.

        Args:
            llm_confidence: LLM confidence score.
            match_score: TMDb match score.

        Returns:
            Combined confidence score.
        """
        # Weight LLM confidence slightly higher since it has context
        return (llm_confidence * 0.6) + (match_score * 0.4)
