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
        self.responses = {}
        self._call_count = 0

    def add_response(self, filename_pattern: str, response: LLMResponse):
        """Add a mock response for a filename pattern."""
        self.responses[filename_pattern] = response

    async def resolve_movies_batch(self, movies_data, user_prompt):
        """Mock batch movie resolution."""
        self._call_count += 1
        responses = []

        for movie_data in movies_data:
            file_info = movie_data["file_info"]

            # Get the main file name
            main_file = max(file_info, key=lambda f: f.size_bytes)
            filename = main_file.name.lower()

            # Find matching response
            found_response = None
            for pattern, response in self.responses.items():
                if pattern.lower() in filename:
                    found_response = response
                    break

            # Use found response or default
            if found_response:
                responses.append(found_response)
            else:
                responses.append(
                    LLMResponse(
                        canonical_title="Unknown Movie",
                        year=2000,
                        confidence=0.5,
                        rationale="Mock response for testing",
                    )
                )

        return responses

    def validate_response(self, response: str) -> bool:
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
    return Path(__file__).parent.parent.parent / "test_movies"


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
                    print(f"✅ Radarr is ready at {radarr_url}")
                    return radarr_url
            except Exception:
                pass

            attempt += 1
            print(f"⏳ Waiting for Radarr... ({attempt}/{max_attempts})")
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
            "confidence_threshold": 0.8,
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
            "dry_run": False,
            "interactive": False,
            "batch_size": 5,
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
    """Create container with integration configuration."""
    config_manager = ConfigManager(integration_config)
    container = Container(config_manager)

    # Replace LLM service with mock
    mock_llm = MockLLMService()
    container.register_instance(ILLMService, mock_llm)

    # Configure other services normally
    from prompt_mapper.core.interfaces import (
        IFileScanner,
        IMovieOrchestrator,
        IMovieResolver,
        IRadarrService,
        ITMDbService,
    )
    from prompt_mapper.core.services import (
        FileScanner,
        MovieOrchestrator,
        MovieResolver,
        RadarrService,
        TMDbService,
    )

    container.register_singleton(ITMDbService, TMDbService)
    container.register_singleton(IRadarrService, RadarrService)
    container.register_singleton(IFileScanner, FileScanner)
    container.register_singleton(IMovieResolver, MovieResolver)
    container.register_singleton(IMovieOrchestrator, MovieOrchestrator)

    return container


@pytest.fixture
def mock_llm_responses():
    """Pre-configured mock LLM responses for test movies."""
    responses = {
        "101 dalmatians (1961)": LLMResponse(
            canonical_title="101 Dalmatians",
            year=1961,
            aka_titles=["One Hundred and One Dalmatians"],
            language_hints=["en"],
            confidence=0.95,
            rationale="Classic Disney animated film",
            genre_hints=["Animation", "Family", "Comedy"],
        ),
        "aladdin": LLMResponse(
            canonical_title="Aladdin",
            year=1992,
            aka_titles=["Disney's Aladdin"],
            language_hints=["en"],
            confidence=0.98,
            rationale="Disney animated classic",
            genre_hints=["Animation", "Family", "Musical"],
        ),
        "asterix": LLMResponse(
            canonical_title="Asterix the Gaul",
            year=1967,
            aka_titles=["Astérix le Gaulois"],
            language_hints=["fr", "en"],
            confidence=0.90,
            rationale="French animated comic adaptation",
            genre_hints=["Animation", "Comedy", "Family"],
        ),
        "bambi": LLMResponse(
            canonical_title="Bambi",
            year=1942,
            aka_titles=[],
            language_hints=["en"],
            confidence=0.95,
            rationale="Disney animated classic about a young deer",
            genre_hints=["Animation", "Drama", "Family"],
        ),
        "cars": LLMResponse(
            canonical_title="Cars",
            year=2006,
            aka_titles=[],
            language_hints=["en"],
            confidence=0.98,
            rationale="Pixar animated film about racing cars",
            genre_hints=["Animation", "Comedy", "Family", "Sport"],
        ),
        "beauty and the beast": LLMResponse(
            canonical_title="Beauty and the Beast",
            year=1991,
            aka_titles=["La Belle et la Bête"],
            language_hints=["en"],
            confidence=0.95,
            rationale="Disney animated musical",
            genre_hints=["Animation", "Family", "Musical", "Romance"],
        ),
        "arthur": LLMResponse(
            canonical_title="Arthur and the Invisibles",
            year=2006,
            aka_titles=["Arthur and the Minimoys", "Arthur et les Minimoys"],
            language_hints=["fr", "en"],
            confidence=0.85,
            rationale="French fantasy adventure film",
            genre_hints=["Animation", "Adventure", "Family"],
        ),
        # Serbian/Croatian titles
        "ainbo": LLMResponse(
            canonical_title="Ainbo: Spirit of the Amazon",
            year=2021,
            aka_titles=["Ainbo - Dobri duh Amazonije"],
            language_hints=["en", "sr"],
            confidence=0.88,
            rationale="Animated adventure about Amazon rainforest",
            genre_hints=["Animation", "Adventure", "Family"],
        ),
        "beli očnjak": LLMResponse(
            canonical_title="White Fang",
            year=2018,
            aka_titles=["Beli očnjak"],
            language_hints=["en", "sr"],
            confidence=0.92,
            rationale="Netflix animated adaptation of Jack London's novel",
            genre_hints=["Animation", "Adventure", "Family"],
        ),
    }
    return responses


@pytest.fixture
def setup_mock_responses(integration_container, mock_llm_responses):
    """Set up mock LLM responses in the container."""
    llm_service = integration_container.get(ILLMService)

    for pattern, response in mock_llm_responses.items():
        llm_service.add_response(pattern, response)

    return llm_service


@pytest.fixture
async def clean_radarr(radarr_service):
    """Clean up Radarr before and after tests."""
    # Note: In a real scenario, you might want to backup/restore Radarr state
    # For now, we'll just ensure we clean up any test movies we add
    yield
    # Cleanup code would go here
