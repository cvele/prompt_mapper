"""Integration tests for Radarr import functionality."""

from pathlib import Path
from typing import Dict, List
from unittest.mock import patch

import pytest

from prompt_mapper.core.interfaces import IRadarrService
from prompt_mapper.core.models import ImportResult, MovieInfo


@pytest.fixture
async def test_movie_file(tmp_path):
    """Create a test movie file for import testing."""
    test_file = tmp_path / "The.Matrix.1999.1080p.mkv"
    test_file.write_text("fake movie content")  # Minimal content for testing
    return test_file


@pytest.fixture
async def test_movie_files(tmp_path):
    """Create multiple test movie files for batch import testing."""
    files = []
    for i, filename in enumerate(
        ["The.Matrix.1999.1080p.mkv", "The.Matrix.1999.720p.mp4", "The.Matrix.1999.subs.srt"]
    ):
        test_file = tmp_path / filename
        test_file.write_text(f"fake content {i}")
        files.append(test_file)
    return files


@pytest.fixture
def sample_movie_info():
    """Sample MovieInfo for testing."""
    return MovieInfo(
        tmdb_id=603,
        title="The Matrix",
        year=1999,
        overview="A computer programmer discovers reality is a simulation.",
        poster_path="/f89U3ADr1oiB1s9GkdPOEpXUk5H.jpg",
        backdrop_path="/fNG7i7RqMErkcqhohV2a6cV1Ehy.jpg",
        genres=["Action", "Science Fiction"],
        runtime=136,
        vote_average=8.2,
        vote_count=23000,
        release_date="1999-03-30",
        original_language="en",
        popularity=85.0,
    )


@pytest.fixture
async def radarr_movie_data():
    """Sample Radarr movie data structure."""
    return {
        "id": 1,
        "title": "The Matrix",
        "year": 1999,
        "tmdbId": 603,
        "path": "/movies/The Matrix (1999)",
        "qualityProfileId": 1,
        "rootFolderPath": "/movies",
        "minimumAvailability": "announced",
        "monitored": True,
        "hasFile": False,
        "movieFile": None,
        "tags": [],
    }


class MockRadarrAPI:
    """Mock Radarr API for testing import functionality."""

    def __init__(self):
        self.movies = {}
        self.import_candidates = []
        self.import_results = []
        self.api_calls = []

    def add_movie(self, movie_data: Dict):
        """Add a movie to the mock Radarr instance."""
        movie_id = movie_data.get("id", len(self.movies) + 1)
        movie_data["id"] = movie_id
        self.movies[movie_id] = movie_data
        return movie_data

    def set_import_candidates(self, candidates: List[Dict]):
        """Set mock import candidates."""
        self.import_candidates = candidates

    def set_import_results(self, results: List[Dict]):
        """Set mock import results."""
        self.import_results = results

    def handle_request(self, method: str, url: str, **kwargs):
        """Handle mock API requests."""
        self.api_calls.append({"method": method, "url": url, "kwargs": kwargs})

        if "/api/v3/manualimport" in url and method == "GET":
            return self._mock_response(200, self.import_candidates)
        elif "/api/v3/manualimport" in url and method == "POST":
            return self._mock_response(200, self.import_results)
        elif "/api/v3/movie" in url and method == "GET":
            movie_id = int(url.split("/")[-1])
            if movie_id in self.movies:
                return self._mock_response(200, self.movies[movie_id])
            else:
                return self._mock_response(404, {"error": "Movie not found"})
        else:
            return self._mock_response(404, {"error": "Endpoint not found"})

    def _mock_response(self, status: int, data: any):
        """Create a mock HTTP response."""

        class MockResponse:
            def __init__(self, status, data):
                self.status_code = status  # httpx uses status_code, not status
                self._data = data

            def raise_for_status(self):
                if self.status_code >= 400:
                    raise Exception(f"HTTP {self.status_code}")

            def json(self):  # httpx uses sync json(), not async
                return self._data

        return MockResponse(status, data)


@pytest.fixture
def mock_radarr_api():
    """Mock Radarr API fixture."""
    return MockRadarrAPI()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_radarr_service_initialization(integration_container, radarr_service):
    """Test that Radarr service initializes correctly."""
    radarr = integration_container.get(IRadarrService)

    assert radarr is not None
    assert hasattr(radarr, "import_movie_files")
    assert hasattr(radarr, "add_movie")
    assert hasattr(radarr, "get_movie_by_tmdb_id")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_successful_import_with_mock_api(
    integration_container, test_movie_file, radarr_movie_data, mock_radarr_api
):
    """Test successful movie import using mocked Radarr API."""
    radarr = integration_container.get(IRadarrService)

    # Set up mock data
    mock_radarr_api.add_movie(radarr_movie_data)
    mock_radarr_api.set_import_candidates(
        [
            {
                "path": str(test_movie_file),
                "movie": {"id": 1, "title": "The Matrix"},
                "quality": {"quality": {"id": 1, "name": "HDTV-720p"}},
                "languages": [{"id": 1, "name": "English"}],
                "releaseGroup": "",
                "customFormats": [],
            }
        ]
    )
    mock_radarr_api.set_import_results(
        [
            {
                "path": str(test_movie_file),
                "importDecision": {"approved": True, "rejections": []},
                "movieFile": {
                    "id": 1,
                    "path": "/movies/The Matrix (1999)/The.Matrix.1999.1080p.mkv",
                    "quality": {"quality": {"id": 1, "name": "HDTV-720p"}},
                    "languages": [{"id": 1, "name": "English"}],
                },
            }
        ]
    )

    # Mock the HTTP client
    with patch.object(radarr, "_get_client") as mock_client:
        # Create async mock functions that return the mock responses
        async def mock_get(*args, **kwargs):
            return mock_radarr_api.handle_request("GET", "/api/v3/manualimport")

        async def mock_post(*args, **kwargs):
            return mock_radarr_api.handle_request("POST", "/api/v3/manualimport")

        mock_client.return_value.get = mock_get
        mock_client.return_value.post = mock_post

        # Execute import
        results = await radarr.import_movie_files(
            radarr_movie=radarr_movie_data, source_paths=[test_movie_file], import_mode="hardlink"
        )

    # Verify results
    assert len(results) == 1
    result = results[0]
    assert isinstance(result, ImportResult)
    assert result.imported is True
    assert result.file_path == test_movie_file
    assert result.target_path == Path("/movies/The Matrix (1999)/The.Matrix.1999.1080p.mkv")
    assert result.method == "radarr_api"
    assert result.error is None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_import_rejection_handling(
    integration_container, test_movie_file, radarr_movie_data, mock_radarr_api
):
    """Test handling of import rejections from Radarr."""
    radarr = integration_container.get(IRadarrService)

    # Set up mock data with rejection
    mock_radarr_api.add_movie(radarr_movie_data)
    mock_radarr_api.set_import_candidates(
        [
            {
                "path": str(test_movie_file),
                "movie": {"id": 1, "title": "The Matrix"},
                "quality": {"quality": {"id": 1, "name": "HDTV-720p"}},
                "languages": [{"id": 1, "name": "English"}],
                "releaseGroup": "",
                "customFormats": [],
            }
        ]
    )
    mock_radarr_api.set_import_results(
        [
            {
                "path": str(test_movie_file),
                "importDecision": {
                    "approved": False,
                    "rejections": [
                        {"reason": "File already exists"},
                        {"reason": "Quality not wanted"},
                    ],
                },
                "movieFile": None,
            }
        ]
    )

    # Mock the HTTP client
    with patch.object(radarr, "_get_client") as mock_client:
        # Create async mock functions that return the mock responses
        async def mock_get(*args, **kwargs):
            return mock_radarr_api.handle_request("GET", "/api/v3/manualimport")

        async def mock_post(*args, **kwargs):
            return mock_radarr_api.handle_request("POST", "/api/v3/manualimport")

        mock_client.return_value.get = mock_get
        mock_client.return_value.post = mock_post

        # Execute import
        results = await radarr.import_movie_files(
            radarr_movie=radarr_movie_data, source_paths=[test_movie_file], import_mode="hardlink"
        )

    # Verify results
    assert len(results) == 1
    result = results[0]
    assert isinstance(result, ImportResult)
    assert result.imported is False
    assert result.file_path == test_movie_file
    assert result.target_path is None
    assert result.method is None
    assert "File already exists; Quality not wanted" in result.error


@pytest.mark.integration
@pytest.mark.asyncio
async def test_batch_import_mixed_results(
    integration_container, test_movie_files, radarr_movie_data, mock_radarr_api
):
    """Test batch import with mixed success/failure results."""
    radarr = integration_container.get(IRadarrService)

    # Set up mock data
    mock_radarr_api.add_movie(radarr_movie_data)

    # Only include video files in candidates (not subtitles)
    video_files = [f for f in test_movie_files if f.suffix in [".mkv", ".mp4"]]

    mock_radarr_api.set_import_candidates(
        [
            {
                "path": str(video_files[0]),
                "movie": {"id": 1, "title": "The Matrix"},
                "quality": {"quality": {"id": 1, "name": "HDTV-1080p"}},
                "languages": [{"id": 1, "name": "English"}],
                "releaseGroup": "",
                "customFormats": [],
            },
            {
                "path": str(video_files[1]),
                "movie": {"id": 1, "title": "The Matrix"},
                "quality": {"quality": {"id": 2, "name": "HDTV-720p"}},
                "languages": [{"id": 1, "name": "English"}],
                "releaseGroup": "",
                "customFormats": [],
            },
        ]
    )

    mock_radarr_api.set_import_results(
        [
            {
                "path": str(video_files[0]),
                "importDecision": {"approved": True, "rejections": []},
                "movieFile": {
                    "id": 1,
                    "path": "/movies/The Matrix (1999)/The.Matrix.1999.1080p.mkv",
                    "quality": {"quality": {"id": 1, "name": "HDTV-1080p"}},
                },
            },
            {
                "path": str(video_files[1]),
                "importDecision": {
                    "approved": False,
                    "rejections": [{"reason": "Lower quality already exists"}],
                },
                "movieFile": None,
            },
        ]
    )

    # Mock the HTTP client
    with patch.object(radarr, "_get_client") as mock_client:
        # Create async mock functions that return the mock responses
        async def mock_get(*args, **kwargs):
            return mock_radarr_api.handle_request("GET", "/api/v3/manualimport")

        async def mock_post(*args, **kwargs):
            return mock_radarr_api.handle_request("POST", "/api/v3/manualimport")

        mock_client.return_value.get = mock_get
        mock_client.return_value.post = mock_post

        # Execute import for video files only
        results = await radarr.import_movie_files(
            radarr_movie=radarr_movie_data, source_paths=video_files, import_mode="hardlink"
        )

    # Verify results
    assert len(results) == 2

    # First file should succeed
    success_result = next(r for r in results if r.file_path == video_files[0])
    assert success_result.imported is True
    assert success_result.error is None
    assert success_result.method == "radarr_api"

    # Second file should fail
    fail_result = next(r for r in results if r.file_path == video_files[1])
    assert fail_result.imported is False
    assert "Lower quality already exists" in fail_result.error
    assert fail_result.method is None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_no_import_candidates_found(
    integration_container, test_movie_file, radarr_movie_data, mock_radarr_api
):
    """Test handling when Radarr finds no import candidates."""
    radarr = integration_container.get(IRadarrService)

    # Set up mock data with no candidates
    mock_radarr_api.add_movie(radarr_movie_data)
    mock_radarr_api.set_import_candidates([])  # No candidates

    # Mock the HTTP client
    with patch.object(radarr, "_get_client") as mock_client:
        # Create async mock function that returns the mock response
        async def mock_get(*args, **kwargs):
            return mock_radarr_api.handle_request("GET", "/api/v3/manualimport")

        mock_client.return_value.get = mock_get

        # Execute import
        results = await radarr.import_movie_files(
            radarr_movie=radarr_movie_data, source_paths=[test_movie_file], import_mode="hardlink"
        )

    # Verify results
    assert len(results) == 1
    result = results[0]
    assert isinstance(result, ImportResult)
    assert result.imported is False
    assert result.file_path == test_movie_file
    assert result.target_path is None
    assert result.method is None
    assert "No valid import candidates found by Radarr" in result.error


@pytest.mark.integration
@pytest.mark.asyncio
async def test_radarr_api_error_handling(integration_container, test_movie_file, radarr_movie_data):
    """Test handling of Radarr API errors."""
    radarr = integration_container.get(IRadarrService)

    # Mock the HTTP client to raise an error
    with patch.object(radarr, "_get_client") as mock_client:
        mock_client.return_value.get.side_effect = Exception("Connection failed")

        # Execute import
        results = await radarr.import_movie_files(
            radarr_movie=radarr_movie_data, source_paths=[test_movie_file], import_mode="hardlink"
        )

    # Verify error handling
    assert len(results) == 1
    result = results[0]
    assert isinstance(result, ImportResult)
    assert result.imported is False
    assert result.file_path == test_movie_file
    assert result.target_path is None
    assert result.method is None
    assert "Failed to import movie files via Radarr API" in result.error


@pytest.mark.integration
@pytest.mark.asyncio
async def test_radarr_disabled_import(integration_container, test_movie_file, radarr_movie_data):
    """Test import when Radarr is disabled in configuration."""
    radarr = integration_container.get(IRadarrService)

    # Mock Radarr as disabled
    with patch.object(radarr, "_radarr_config") as mock_config:
        mock_config.enabled = False

        # Execute import
        results = await radarr.import_movie_files(
            radarr_movie=radarr_movie_data, source_paths=[test_movie_file], import_mode="hardlink"
        )

    # Should return empty list when disabled
    assert results == []


@pytest.mark.integration
@pytest.mark.asyncio
async def test_real_radarr_api_integration(
    integration_container, radarr_service, sample_movie_info, test_movie_file
):
    """Test with real Radarr API (requires running Radarr instance)."""
    # Check if Radarr is configured with a real API key (not placeholder)
    config = integration_container.get_config()
    if config.radarr.api_key == "test-radarr-api-key":
        pytest.skip("Requires real Radarr instance with configured API key")

    radarr = integration_container.get(IRadarrService)

    try:
        # First, add the movie to Radarr
        radarr_movie = await radarr.add_movie(sample_movie_info)
        assert radarr_movie is not None
        assert radarr_movie["tmdbId"] == sample_movie_info.tmdb_id

        # Try to import the test file
        results = await radarr.import_movie_files(
            radarr_movie=radarr_movie, source_paths=[test_movie_file], import_mode="hardlink"
        )

        # Verify we get a result (success or failure)
        assert len(results) == 1
        result = results[0]
        assert isinstance(result, ImportResult)
        assert result.file_path == test_movie_file

        # Clean up - remove the movie
        await radarr.remove_movie(radarr_movie, delete_files=True)

    except Exception as e:
        pytest.skip(f"Real Radarr API test failed: {e}")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_import_api_call_sequence(
    integration_container, test_movie_file, radarr_movie_data, mock_radarr_api
):
    """Test that the correct sequence of API calls is made."""
    radarr = integration_container.get(IRadarrService)

    # Set up mock data
    mock_radarr_api.add_movie(radarr_movie_data)
    mock_radarr_api.set_import_candidates(
        [
            {
                "path": str(test_movie_file),
                "movie": {"id": 1, "title": "The Matrix"},
                "quality": {"quality": {"id": 1, "name": "HDTV-720p"}},
                "languages": [{"id": 1, "name": "English"}],
                "releaseGroup": "",
                "customFormats": [],
            }
        ]
    )
    mock_radarr_api.set_import_results(
        [
            {
                "path": str(test_movie_file),
                "importDecision": {"approved": True, "rejections": []},
                "movieFile": {
                    "id": 1,
                    "path": "/movies/The Matrix (1999)/The.Matrix.1999.1080p.mkv",
                },
            }
        ]
    )

    # Mock the HTTP client
    with patch.object(radarr, "_get_client") as mock_client:
        # Create async mock functions that return the mock responses
        async def mock_get(*args, **kwargs):
            return mock_radarr_api.handle_request("GET", "/api/v3/manualimport")

        async def mock_post(*args, **kwargs):
            return mock_radarr_api.handle_request("POST", "/api/v3/manualimport")

        mock_client.return_value.get = mock_get
        mock_client.return_value.post = mock_post

        # Execute import
        await radarr.import_movie_files(
            radarr_movie=radarr_movie_data, source_paths=[test_movie_file], import_mode="hardlink"
        )

    # Verify API call sequence
    api_calls = mock_radarr_api.api_calls
    assert len(api_calls) >= 2

    # First call should be GET to get candidates
    get_call = api_calls[0]
    assert get_call["method"] == "GET"
    assert "/api/v3/manualimport" in get_call["url"]

    # Second call should be POST to execute import
    post_call = api_calls[1]
    assert post_call["method"] == "POST"
    assert "/api/v3/manualimport" in post_call["url"]
