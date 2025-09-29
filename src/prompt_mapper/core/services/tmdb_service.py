"""TMDb service implementation."""

from typing import Any, List, Optional

import aiohttp

from ...config.models import Config
from ...infrastructure.logging import LoggerMixin
from ...utils import TMDbServiceError, calculate_similarity
from ..interfaces import ITMDbService
from ..models import LLMResponse, MovieCandidate, MovieInfo


class TMDbService(ITMDbService, LoggerMixin):
    """TMDb service implementation."""

    def __init__(self, config: Config) -> None:
        """Initialize TMDb service.

        Args:
            config: Application configuration.
        """
        self._config = config
        self._tmdb_config = config.tmdb
        self._session: Optional[aiohttp.ClientSession] = None

    async def search_movies(
        self, llm_response: LLMResponse, max_results: int = 10
    ) -> List[MovieCandidate]:
        """Search for movies based on LLM response.

        Args:
            llm_response: LLM response with movie information.
            max_results: Maximum number of results to return.

        Returns:
            List of movie candidates with match scores.

        Raises:
            TMDbServiceError: If search fails.
        """
        candidates = []

        try:
            # Search with canonical title
            primary_results = await self._search_by_title(
                llm_response.canonical_title, llm_response.year
            )

            for result in primary_results[:max_results]:
                movie_info = self._parse_movie_result(result)
                score = self.calculate_match_score(movie_info, llm_response)

                candidate = MovieCandidate(
                    movie_info=movie_info,
                    match_score=score,
                    score_breakdown=self._get_score_breakdown(movie_info, llm_response),
                    search_query=llm_response.canonical_title,
                )
                candidates.append(candidate)

            # Search with alternative titles if we don't have enough results
            if len(candidates) < max_results and llm_response.aka_titles:
                for aka_title in llm_response.aka_titles:
                    if len(candidates) >= max_results:
                        break

                    aka_results = await self._search_by_title(aka_title, llm_response.year)
                    for result in aka_results:
                        if len(candidates) >= max_results:
                            break

                        movie_info = self._parse_movie_result(result)

                        # Skip if we already have this movie
                        if any(c.movie_info.tmdb_id == movie_info.tmdb_id for c in candidates):
                            continue

                        score = self.calculate_match_score(movie_info, llm_response)
                        candidate = MovieCandidate(
                            movie_info=movie_info,
                            match_score=score,
                            score_breakdown=self._get_score_breakdown(movie_info, llm_response),
                            search_query=aka_title,
                        )
                        candidates.append(candidate)

            # Sort by match score
            candidates.sort(key=lambda c: c.match_score, reverse=True)

            self.logger.info(f"Found {len(candidates)} movie candidates")
            return candidates[:max_results]

        except Exception as e:
            error_msg = f"TMDb search failed: {e}"
            self.logger.error(error_msg)
            raise TMDbServiceError(error_msg) from e

    async def get_movie_details(self, tmdb_id: int) -> Optional[MovieInfo]:
        """Get detailed movie information by TMDb ID.

        Args:
            tmdb_id: TMDb movie ID.

        Returns:
            Detailed movie information or None if not found.

        Raises:
            TMDbServiceError: If request fails.
        """
        try:
            url = f"{self._tmdb_config.base_url}/movie/{tmdb_id}"
            params = {"api_key": self._tmdb_config.api_key, "language": self._tmdb_config.language}

            async with self._get_session().get(url, params=params) as response:
                if response.status == 404:
                    return None
                response.raise_for_status()
                data = await response.json()
                return self._parse_movie_result(data)

        except Exception as e:
            error_msg = f"Failed to get movie details for TMDb ID {tmdb_id}: {e}"
            self.logger.error(error_msg)
            raise TMDbServiceError(error_msg) from e

    async def get_movie_by_imdb_id(self, imdb_id: str) -> Optional[MovieInfo]:
        """Get movie information by IMDb ID.

        Args:
            imdb_id: IMDb movie ID.

        Returns:
            Movie information or None if not found.

        Raises:
            TMDbServiceError: If request fails.
        """
        try:
            url = f"{self._tmdb_config.base_url}/find/{imdb_id}"
            params = {"api_key": self._tmdb_config.api_key, "external_source": "imdb_id"}

            async with self._get_session().get(url, params=params) as response:
                response.raise_for_status()
                data = await response.json()

                if data.get("movie_results"):
                    return self._parse_movie_result(data["movie_results"][0])

                return None

        except Exception as e:
            error_msg = f"Failed to get movie by IMDb ID {imdb_id}: {e}"
            self.logger.error(error_msg)
            raise TMDbServiceError(error_msg) from e

    def calculate_match_score(self, movie: MovieInfo, llm_response: LLMResponse) -> float:
        """Calculate match score between movie and LLM response.

        Args:
            movie: Movie information from TMDb.
            llm_response: LLM response with expected movie info.

        Returns:
            Match score between 0.0 and 1.0.
        """
        scoring_config = self._config.matching.scoring
        score = 0.0

        # Title similarity (highest weight)
        title_scores = []
        for title in llm_response.all_titles:
            title_scores.append(calculate_similarity(movie.title, title))
            if movie.original_title:
                title_scores.append(calculate_similarity(movie.original_title, title))

        title_score = max(title_scores) if title_scores else 0.0
        score += title_score * scoring_config.title_similarity

        # Year proximity
        if movie.year and llm_response.year:
            year_diff = abs(movie.year - llm_response.year)
            year_tolerance = self._config.matching.year_tolerance
            if year_diff <= year_tolerance:
                year_score = 1.0 - (year_diff / max(year_tolerance, 1))
            else:
                year_score = 0.0
            score += year_score * scoring_config.year_proximity
        elif movie.year and not llm_response.year:
            # Partial credit if we have movie year but not expected year
            score += 0.5 * scoring_config.year_proximity

        # Popularity (normalized)
        if movie.popularity:
            popularity_score = min(movie.popularity / 100.0, 1.0)
            score += popularity_score * scoring_config.popularity

        # Language match
        if llm_response.language_hints and movie.original_language:
            if movie.original_language in llm_response.language_hints:
                score += 1.0 * scoring_config.language_match
            else:
                score += 0.5 * scoring_config.language_match

        return min(score, 1.0)

    async def _search_by_title(self, title: str, year: Optional[int] = None) -> List[dict]:
        """Search movies by title.

        Args:
            title: Movie title to search for.
            year: Optional year filter.

        Returns:
            List of movie results.
        """
        url = f"{self._tmdb_config.base_url}/search/movie"
        params = {
            "api_key": self._tmdb_config.api_key,
            "query": title,
            "language": self._tmdb_config.language,
            "include_adult": "false",
        }

        if year:
            params["year"] = str(year)

        async with self._get_session().get(url, params=params) as response:
            response.raise_for_status()
            data = await response.json()
            results = data.get("results", [])
            if not isinstance(results, list):
                return []
            return results

    def _parse_movie_result(self, data: dict) -> MovieInfo:
        """Parse TMDb movie result into MovieInfo.

        Args:
            data: TMDb movie data.

        Returns:
            MovieInfo object.
        """
        # Parse release date
        release_date = None
        if data.get("release_date"):
            try:
                from datetime import datetime

                release_date = datetime.strptime(data["release_date"], "%Y-%m-%d").date()
            except ValueError:
                pass

        # Extract year from release date
        year = release_date.year if release_date else None

        return MovieInfo(
            title=data.get("title", ""),
            year=year,
            tmdb_id=data.get("id"),
            imdb_id=data.get("imdb_id"),
            overview=data.get("overview"),
            poster_path=data.get("poster_path"),
            backdrop_path=data.get("backdrop_path"),
            original_title=data.get("original_title"),
            original_language=data.get("original_language"),
            release_date=release_date,
            runtime=data.get("runtime"),
            genres=[g["name"] for g in data.get("genres", [])],
            popularity=data.get("popularity"),
            vote_average=data.get("vote_average"),
            vote_count=data.get("vote_count"),
        )

    def _get_score_breakdown(self, movie: MovieInfo, llm_response: LLMResponse) -> dict:
        """Get detailed score breakdown.

        Args:
            movie: Movie information.
            llm_response: LLM response.

        Returns:
            Score breakdown dictionary.
        """
        scoring_config = self._config.matching.scoring

        # Calculate individual components
        title_scores = []
        for title in llm_response.all_titles:
            title_scores.append(calculate_similarity(movie.title, title))
            if movie.original_title:
                title_scores.append(calculate_similarity(movie.original_title, title))
        title_score = max(title_scores) if title_scores else 0.0

        year_score = 0.0
        if movie.year and llm_response.year:
            year_diff = abs(movie.year - llm_response.year)
            year_tolerance = self._config.matching.year_tolerance
            if year_diff <= year_tolerance:
                year_score = 1.0 - (year_diff / max(year_tolerance, 1))

        popularity_score = min(movie.popularity / 100.0, 1.0) if movie.popularity else 0.0

        language_score = 0.0
        if llm_response.language_hints and movie.original_language:
            if movie.original_language in llm_response.language_hints:
                language_score = 1.0
            else:
                language_score = 0.5

        return {
            "title_similarity": title_score,
            "year_proximity": year_score,
            "popularity": popularity_score,
            "language_match": language_score,
            "weighted_title": title_score * scoring_config.title_similarity,
            "weighted_year": year_score * scoring_config.year_proximity,
            "weighted_popularity": popularity_score * scoring_config.popularity,
            "weighted_language": language_score * scoring_config.language_match,
        }

    def _get_session(self) -> aiohttp.ClientSession:
        """Get or create HTTP session.

        Returns:
            HTTP session.
        """
        if self._session is None:
            timeout = aiohttp.ClientTimeout(total=self._tmdb_config.timeout)
            # Disable SSL verification and warnings
            try:
                import urllib3

                urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
            except ImportError:
                pass
            connector = aiohttp.TCPConnector(ssl=False)
            self._session = aiohttp.ClientSession(timeout=timeout, connector=connector)
        return self._session

    async def close(self) -> None:
        """Close HTTP session."""
        if self._session:
            await self._session.close()
            self._session = None

    async def __aenter__(self) -> "TMDbService":
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit."""
        await self.close()

    def __del__(self) -> None:
        """Cleanup on deletion."""
        # Just log that cleanup is needed, don't try to clean up here
        if self._session and not self._session.closed:
            import logging

            logging.getLogger(__name__).debug("TMDbService session not properly closed")
