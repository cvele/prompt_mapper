"""Movie resolver service implementation."""

from typing import List, Optional

import click

from ...config.models import Config
from ...infrastructure.logging import LoggerMixin
from ...utils import MovieResolverError, clean_movie_filename
from ..interfaces import ILLMService, IMovieResolver, ITMDbService
from ..models import MovieCandidate, MovieMatch


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

    async def resolve_movie_from_filename(self, filename: str, user_prompt: str) -> MovieMatch:
        """Resolve movie from filename using the simplified flow.

        Flow: clean filename → search TMDB → LLM selects → manual fallback if low confidence

        Args:
            filename: Movie filename to resolve.
            user_prompt: User prompt for resolution guidance.

        Returns:
            Movie match result.

        Raises:
            MovieResolverError: If resolution fails.
        """
        try:
            self.logger.info(f"Resolving movie from filename: {filename}")

            # Step 1: Clean filename to extract movie name and year
            movie_name, movie_year = clean_movie_filename(filename)
            self.logger.debug(f"Cleaned: name='{movie_name}', year={movie_year}")

            if not movie_name:
                raise MovieResolverError("Could not extract movie name from filename")

            # Step 2: Search TMDB
            candidates = await self._search_tmdb(movie_name, movie_year)

            if not candidates:
                raise MovieResolverError(f"No TMDB candidates found for '{movie_name}'")

            # Step 3: LLM selects best match from candidates
            selected_candidate, confidence = await self._llm_service.select_movie_from_candidates(
                candidates=candidates,
                original_filename=filename,
                movie_name=movie_name,
                movie_year=movie_year,
                user_prompt=user_prompt,
            )

            # Get confidence threshold
            confidence_threshold = self._config.matching.confidence_threshold

            # Step 4: Check if confidence is high enough
            if selected_candidate and confidence >= confidence_threshold:
                # Auto-select with high confidence
                self.logger.info(
                    f"Auto-selected: {selected_candidate.movie_info.title} "
                    f"({selected_candidate.movie_info.year}) - confidence: {confidence:.2f}"
                )

                movie_match = MovieMatch(
                    movie_info=selected_candidate.movie_info,
                    confidence=confidence,
                    llm_response=None,  # No longer using LLMResponse model
                    candidates=candidates,
                    selected_automatically=True,
                    user_confirmed=False,
                    rationale=f"LLM selection with {confidence:.2f} confidence",
                )

                return movie_match

            # Step 5: Manual selection (low confidence or no LLM selection)
            self.logger.info(f"Low confidence ({confidence:.2f}), requesting manual selection")
            selected_index = await self.get_user_choice(
                filename, movie_name, movie_year, candidates
            )

            if selected_index is None:
                raise MovieResolverError("User skipped selection")

            selected_candidate = candidates[selected_index]
            self.logger.info(f"User selected: {selected_candidate.movie_info.title}")

            movie_match = MovieMatch(
                movie_info=selected_candidate.movie_info,
                confidence=1.0,  # Manual selections have 100% confidence
                llm_response=None,
                candidates=candidates,
                selected_automatically=False,
                user_confirmed=True,
                rationale="User manual selection",
            )

            return movie_match

        except Exception as e:
            error_msg = f"Movie resolution failed for '{filename}': {e}"
            self.logger.error(error_msg)
            raise MovieResolverError(error_msg) from e

    async def _search_tmdb(
        self, movie_name: str, movie_year: Optional[int]
    ) -> List[MovieCandidate]:
        """Search TMDB for movie candidates.

        Args:
            movie_name: Movie name to search.
            movie_year: Optional year filter.

        Returns:
            List of movie candidates.
        """
        # Use TMDb service's search directly
        # We'll create a simple query object
        from ..models import LLMResponse

        # Create a minimal LLMResponse for TMDb search compatibility
        search_query = LLMResponse(
            canonical_title=movie_name,
            year=movie_year,
            aka_titles=[],
            language_hints=[],
            confidence=1.0,
            rationale="Direct filename search",
            director=None,
            genre_hints=[],
            edition_notes=None,
        )

        candidates = await self._tmdb_service.search_movies(
            search_query, max_results=self._config.matching.max_search_results
        )

        return candidates

    async def get_user_choice(
        self,
        original_filename: str,
        movie_name: str,
        movie_year: Optional[int],
        candidates: List[MovieCandidate],
    ) -> Optional[int]:
        """Get user choice from movie candidates.

        Args:
            original_filename: Original filename for display.
            movie_name: Cleaned movie name.
            movie_year: Extracted year.
            candidates: List of movie candidates.

        Returns:
            Selected candidate index or None if skipped.
        """
        if not candidates:
            return None

        # Display information
        click.echo("\n" + "=" * 70)
        click.echo("Manual Selection Required")
        click.echo("=" * 70)
        click.echo(f"\nOriginal filename: {original_filename}")
        click.echo(f"Cleaned name: {movie_name}")
        if movie_year:
            click.echo(f"Extracted year: {movie_year}")

        click.echo(f"\nFound {len(candidates)} candidate(s) from TMDb:")

        # Show candidates
        for i, candidate in enumerate(candidates, 1):
            movie = candidate.movie_info
            click.echo(f"\n  {i}. {movie.title} ({movie.year or 'Unknown'})")
            click.echo(f"     TMDb ID: {movie.tmdb_id} | Score: {candidate.match_score:.3f}")
            if movie.original_title and movie.original_title != movie.title:
                click.echo(f"     Original Title: {movie.original_title}")
            if movie.overview:
                overview = (
                    movie.overview[:100] + "..." if len(movie.overview) > 100 else movie.overview
                )
                click.echo(f"     {overview}")

        click.echo("\n" + "=" * 70)

        # Check if we're in a non-interactive environment
        if not self._interactive:
            click.echo("Non-interactive mode: auto-selecting first candidate")
            return 0

        # Interactive mode - get user input
        while True:
            try:
                choice = click.prompt(
                    f"Select movie (1-{len(candidates)}) or 's' to skip",
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
