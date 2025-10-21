"""Integration test fixtures and configuration."""

import asyncio
import os
from pathlib import Path

import pytest
import yaml

from prompt_mapper.config import ConfigManager
from prompt_mapper.core.interfaces import ILLMService
from prompt_mapper.core.models import LLMResponse
from prompt_mapper.infrastructure import Container


class MockLLMService:
    """Mock LLM service for integration tests."""

    def __init__(self):
        self.candidate_responses = {}
        self._call_count = 0

    def add_candidate_response(self, filename_pattern: str, selected_index: int, confidence: float):
        """Add a mock response for candidate selection."""
        self.candidate_responses[filename_pattern.lower()] = (selected_index, confidence)

    async def select_movie_from_candidates(
        self, candidates, original_filename, movie_name, movie_year, user_prompt
    ):
        """Mock movie selection from candidates."""
        self._call_count += 1

        # Default: select first candidate with medium confidence
        selected_index = 0
        confidence = 0.85

        # Check if we have a specific response for this filename
        filename_lower = original_filename.lower()
        for pattern, (idx, conf) in self.candidate_responses.items():
            if pattern in filename_lower:
                selected_index = idx
                confidence = conf
                break

        # Return selected candidate and confidence
        if candidates and 0 <= selected_index < len(candidates):
            return candidates[selected_index], confidence
        else:
            return None, 0.0


class MockTMDbService:
    """Mock TMDB service for integration tests."""

    async def search_movies(self, llm_response, max_results=10):
        """Mock TMDB search - return fake candidate."""
        from prompt_mapper.core.models import MovieCandidate, MovieInfo

        # Create a mock candidate based on the search query
        movie_info = MovieInfo(
            tmdb_id=12345,
            title=llm_response.canonical_title,
            year=llm_response.year or 2020,
            overview=f"Mock movie: {llm_response.canonical_title}",
            poster_path=None,
            imdb_id="tt1234567",
        )

        candidate = MovieCandidate(
            movie_info=movie_info,
            match_score=0.95,
            search_query=llm_response.canonical_title,
        )
        return [candidate]

    async def get_movie_details(self, tmdb_id):
        """Mock getting movie details."""
        from prompt_mapper.core.models import MovieInfo

        return MovieInfo(
            tmdb_id=tmdb_id,
            title="Mock Movie",
            year=2020,
            overview="Mock movie details",
            poster_path=None,
            imdb_id="tt1234567",
        )

    async def get_movie_by_imdb_id(self, imdb_id):
        """Mock getting movie by IMDB ID."""
        from prompt_mapper.core.models import MovieInfo

        return MovieInfo(
            tmdb_id=12345,
            title="Mock Movie",
            year=2020,
            overview="Mock movie from IMDB",
            poster_path=None,
            imdb_id=imdb_id,
        )

    def calculate_match_score(self, movie, llm_response):
        """Mock match score calculation."""
        return 0.95


class MockRadarrService:
    """Mock Radarr service for integration tests."""

    async def get_movie_by_tmdb_id(self, tmdb_id):
        """Mock getting movie from Radarr - always returns None (not in Radarr)."""
        return None

    async def add_movie(
        self,
        movie_info,
        root_folder_path=None,
        quality_profile_id=None,
        minimum_availability=None,
        tags=None,
    ):
        """Mock adding movie to Radarr."""
        return {
            "id": 123,
            "title": movie_info.title,
            "tmdbId": movie_info.tmdb_id,
            "path": f"/movies/{movie_info.title} ({movie_info.year})",
        }

    async def import_movie_files(self, radarr_movie, source_paths, import_mode="hardlink"):
        """Mock importing movie files."""
        from prompt_mapper.core.interfaces.radarr_service import ImportResult

        results = []
        for path in source_paths:
            results.append(
                ImportResult(
                    success=True,
                    source_path=path,
                    destination_path=Path(f"/movies/imported/{path.name}"),
                    message="Mock import successful",
                )
            )
        return results

    async def trigger_movie_search(self, radarr_movie):
        """Mock triggering movie search."""
        return True


@pytest.fixture(scope="session")
def docker_compose_file():
    """Path to docker-compose file."""
    return Path(__file__).parent.parent.parent / "docker-compose.yml"


@pytest.fixture(scope="session")
def radarr_url():
    """Radarr service URL."""
    return "http://localhost:7878"


@pytest.fixture(scope="session")
def test_movies_path():
    """Path to test movies directory."""
    # Use the same logic as create_test_movies.py to find the test movies directory
    movies_dir = os.getenv("MOVIES_DIR")
    if not movies_dir:
        # In CI environments, use RUNNER_TEMP for guaranteed write access
        runner_temp = os.getenv("RUNNER_TEMP")
        if runner_temp:
            movies_dir = os.path.join(runner_temp, "test_movies")
        else:
            movies_dir = "test_movies"

    # If it's a relative path, make it relative to the project root
    if not os.path.isabs(movies_dir):
        project_root = Path(__file__).parent.parent.parent
        test_path = project_root / movies_dir
    else:
        test_path = Path(movies_dir)

    # Debug logging for CI troubleshooting
    print("Test movies path resolution:")
    print(f"   MOVIES_DIR env var: {os.getenv('MOVIES_DIR')}")
    print(f"   RUNNER_TEMP env var: {os.getenv('RUNNER_TEMP')}")
    print(f"   Resolved movies_dir: {movies_dir}")
    print(f"   Final test path: {test_path}")
    print(f"   Path exists: {test_path.exists()}")

    return test_path


@pytest.fixture(scope="session")
async def radarr_service(radarr_url):
    """Wait for Radarr service to be ready."""
    import httpx

    max_attempts = 30
    attempt = 0

    async with httpx.AsyncClient(timeout=5, verify=False) as client:
        while attempt < max_attempts:
            try:
                response = await client.get(f"{radarr_url}/ping")
                if response.status_code == 200:
                    print(f"Radarr is ready at {radarr_url}")
                    return radarr_url
            except Exception:
                pass

            attempt += 1
            print(f"Waiting for Radarr... ({attempt}/{max_attempts})")
            await asyncio.sleep(2)

    pytest.skip(f"Radarr not available at {radarr_url} after {max_attempts} attempts")


def _get_radarr_api_key():
    """Get Radarr API key from environment or config file."""
    # First try environment variable
    api_key = os.getenv("RADARR_API_KEY")
    if api_key:
        return api_key

    # Fallback for integration tests
    return "test-radarr-api-key"


@pytest.fixture
def integration_config(tmp_path, radarr_url):
    """Create integration test configuration."""
    config_content = {
        "llm": {
            "provider": "openai",
            "model": "gpt-4",
            "api_key": os.getenv("OPENAI_API_KEY", "test-key-integration"),
            "max_tokens": 1000,
            "temperature": 0.1,
            "timeout": 30,
        },
        "tmdb": {
            "api_key": os.getenv("TMDB_API_KEY", "test-tmdb-key"),
            "base_url": "https://api.themoviedb.org/3",
            "language": "en-US",
            "timeout": 10,
        },
        "radarr": {
            "enabled": True,
            "url": radarr_url,
            "api_key": _get_radarr_api_key(),
            "timeout": 30,
            "default_profile": {
                "quality_profile_id": 1,
                "root_folder_path": "/movies",
                "minimum_availability": "announced",
                "tags": [],
            },
            "import": {"mode": "hardlink", "delete_empty_folders": False},
        },
        "matching": {
            "confidence_threshold": 0.95,
            "year_tolerance": 1,
            "max_search_results": 10,
            "auto_add_to_radarr": False,
            "auto_import": False,
            "skip_existing": True,
            "scoring": {
                "title_similarity": 0.4,
                "year_proximity": 0.3,
                "popularity": 0.2,
                "language_match": 0.1,
            },
        },
        "files": {
            "extensions": {
                "video": [".mkv", ".mp4", ".avi", ".mov"],
                "subtitle": [".srt", ".sub", ".ass"],
            },
            "ignore_patterns": ["sample", "trailer", "extras"],
            "min_file_size_mb": 0,  # Allow minimal files for testing
            "scan_depth": 2,
        },
        "prompts": {
            "default": "Analyze the movie file and extract canonical information.",
            "profiles": {
                "serbian": "These are Serbian/Croatian/Bosnian movies. Translate to English titles.",
                "animation": "These are animated movies, mostly for children.",
            },
        },
        "logging": {
            "level": "DEBUG",
            "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        },
        "app": {
            "interactive": False,
            "retry_attempts": 3,
            "cache_enabled": False,
        },
    }

    config_file = tmp_path / "integration_config.yaml"
    with open(config_file, "w") as f:
        yaml.dump(config_content, f, default_flow_style=False, indent=2)

    return config_file


@pytest.fixture
def integration_container(integration_config):
    """Create container with integration configuration (all services mocked)."""
    config_manager = ConfigManager(integration_config)
    container = Container(config_manager)

    # Replace LLM service with mock
    mock_llm = MockLLMService()
    container.register_instance(ILLMService, mock_llm)

    # Replace TMDB service with mock (to avoid real API calls in tests)
    mock_tmdb = MockTMDbService()
    from prompt_mapper.core.interfaces import ITMDbService

    container.register_instance(ITMDbService, mock_tmdb)

    # Replace Radarr service with mock (to avoid waiting for real Radarr)
    mock_radarr = MockRadarrService()
    from prompt_mapper.core.interfaces import IRadarrService

    container.register_instance(IRadarrService, mock_radarr)

    # Configure other services normally
    from prompt_mapper.core.interfaces import IFileScanner, IMovieOrchestrator, IMovieResolver
    from prompt_mapper.core.services import FileScanner, MovieOrchestrator, MovieResolver

    container.register_singleton(IFileScanner, FileScanner)
    container.register_singleton(IMovieResolver, MovieResolver)
    container.register_singleton(IMovieOrchestrator, MovieOrchestrator)

    return container


@pytest.fixture
def radarr_integration_container(integration_config):
    """Create container with REAL Radarr service (for Radarr-specific tests)."""
    config_manager = ConfigManager(integration_config)
    container = Container(config_manager)

    # Replace LLM service with mock
    mock_llm = MockLLMService()
    container.register_instance(ILLMService, mock_llm)

    # Replace TMDB service with mock
    mock_tmdb = MockTMDbService()
    from prompt_mapper.core.interfaces import ITMDbService

    container.register_instance(ITMDbService, mock_tmdb)

    # Use REAL Radarr service (for tests that need to patch its internals)
    from prompt_mapper.core.interfaces import IRadarrService
    from prompt_mapper.core.services import RadarrService

    container.register_singleton(IRadarrService, RadarrService)

    # Configure other services normally
    from prompt_mapper.core.interfaces import IFileScanner, IMovieOrchestrator, IMovieResolver
    from prompt_mapper.core.services import FileScanner, MovieOrchestrator, MovieResolver

    container.register_singleton(IFileScanner, FileScanner)
    container.register_singleton(IMovieResolver, MovieResolver)
    container.register_singleton(IMovieOrchestrator, MovieOrchestrator)

    return container


@pytest.fixture
def mock_llm_responses():
    """Pre-configured mock LLM candidate selection responses."""
    # Map filename patterns to (selected_index, confidence)
    responses = {
        "101 dalmatians": (0, 0.95),
        "aladdin": (0, 0.98),
        "asterix": (0, 0.90),
        "bambi": (0, 0.95),
        "cars": (0, 0.98),
        "beauty and the beast": (0, 0.95),
        "arthur": (0, 0.85),
        "ainbo": (0, 0.88),
        "beli": (0, 0.92),  # For "Beli očnjak"
    }
    return responses


@pytest.fixture
def setup_mock_responses(integration_container, mock_llm_responses):
    """Set up mock LLM responses in the container."""
    llm_service = integration_container.get(ILLMService)

    for pattern, (idx, conf) in mock_llm_responses.items():
        llm_service.add_candidate_response(pattern, idx, conf)

    return llm_service


@pytest.fixture
async def clean_radarr(radarr_service):
    """Clean up Radarr before and after tests."""
    # Note: In a real scenario, you might want to backup/restore Radarr state
    # For now, we'll just ensure we clean up any test movies we add
    yield
    # Cleanup code would go here
