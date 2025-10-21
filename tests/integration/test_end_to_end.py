"""End-to-end integration tests."""

import pytest

from prompt_mapper.core.interfaces import IFileScanner, IMovieOrchestrator
from prompt_mapper.core.models.processing_result import ProcessingStatus


@pytest.mark.integration
@pytest.mark.asyncio
async def test_file_scanner_integration(integration_container, test_movies_path):
    """Test file scanner with real test files."""
    scanner = integration_container.get(IFileScanner)

    # Test scanning the flat test movies directory
    if not test_movies_path.exists():
        pytest.skip(f"Test directory not found: {test_movies_path}")

    # Check if directory has any .mkv files
    mkv_files = list(test_movies_path.glob("*.mkv"))
    if len(mkv_files) == 0:
        pytest.skip(
            f"No test movie files found in: {test_movies_path}. Test movies may not have been created."
        )

    result = await scanner.scan_directory(test_movies_path)

    assert result.root_path == test_movies_path
    assert len(result.video_files) >= 1
    assert result.total_size_mb > 0

    # Check that video files are properly detected
    video_files = [f for f in result.video_files if f.name.endswith(".mkv")]
    assert len(video_files) >= 1

    # Check file properties
    main_video = result.main_video_file
    assert main_video is not None
    assert main_video.is_video
    assert main_video.size_bytes > 0  # Should have some content (minimal 1 byte)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_file_scanner_list_files(integration_container, test_movies_path):
    """Test file scanner's flat file listing."""
    scanner = integration_container.get(IFileScanner)

    if not test_movies_path.exists():
        pytest.skip(f"Test directory not found: {test_movies_path}")

    # Check if directory has any .mkv files
    mkv_files = list(test_movies_path.glob("*.mkv"))
    if len(mkv_files) == 0:
        pytest.skip(
            f"No test movie files found in: {test_movies_path}. Test movies may not have been created."
        )

    # Test the new list_movie_files method
    movie_files = await scanner.list_movie_files(test_movies_path)

    assert len(movie_files) >= 1
    for file_path in movie_files:
        assert file_path.exists()
        assert file_path.suffix.lower() in [".mkv", ".mp4", ".avi", ".mov"]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_tmdb_integration(integration_config):
    """Test TMDb service integration with REAL TMDB API."""
    import os

    from prompt_mapper.config import ConfigManager
    from prompt_mapper.core.models import LLMResponse
    from prompt_mapper.core.services import TMDbService

    # Check if TMDB is properly configured (not a placeholder test key)
    if os.getenv("TMDB_API_KEY", "test-tmdb-key") == "test-tmdb-key":
        pytest.skip("TMDB_API_KEY not configured - skipping real API test")

    # Use real TMDb service for this test
    config_manager = ConfigManager(integration_config)
    tmdb_service = TMDbService(config_manager.load_config())

    # Test search with known movie
    llm_response = LLMResponse(
        canonical_title="Aladdin", year=1992, confidence=0.9, rationale="Disney animated movie"
    )

    candidates = await tmdb_service.search_movies(llm_response, max_results=5)

    assert len(candidates) > 0

    # Check first candidate
    top_candidate = candidates[0]
    assert top_candidate.movie_info.title is not None
    assert top_candidate.movie_info.tmdb_id is not None
    assert top_candidate.match_score > 0

    # Test getting movie details
    movie_details = await tmdb_service.get_movie_details(top_candidate.movie_info.tmdb_id)
    assert movie_details is not None
    assert movie_details.tmdb_id == top_candidate.movie_info.tmdb_id


@pytest.mark.integration
@pytest.mark.asyncio
async def test_directory_processing(integration_container, test_movies_path, setup_mock_responses):
    """Test processing a directory with movie files (using mocked services)."""
    orchestrator = integration_container.get(IMovieOrchestrator)

    if not test_movies_path.exists():
        pytest.skip(f"Test directory not found: {test_movies_path}")

    # Check if directory has any .mkv files
    mkv_files = list(test_movies_path.glob("*.mkv"))
    if len(mkv_files) == 0:
        pytest.skip(
            f"No test movie files found in: {test_movies_path}. Test movies may not have been created."
        )

    # Process the directory - this will process each file individually
    summary = await orchestrator.process_directory(
        directory=test_movies_path,
        user_prompt="Animated movies",
        auto_add=False,
    )

    assert summary is not None
    assert summary.total_processed >= 1
    assert summary.successful >= 0
    assert summary.total_processing_time_seconds > 0

    # Check that results exist
    assert len(summary.results) >= 1
    for result in summary.results:
        assert result.status in [
            ProcessingStatus.SUCCESS,
            ProcessingStatus.FAILED,
            ProcessingStatus.SKIPPED,
        ]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_prerequisites_validation(integration_container):
    """Test prerequisites validation."""
    orchestrator = integration_container.get(IMovieOrchestrator)

    errors = await orchestrator.validate_prerequisites()

    # Should return list (may be empty if all good, or contain errors)
    assert isinstance(errors, list)

    # Print any validation errors for debugging
    if errors:
        print("Validation errors:")
        for error in errors:
            print(f"  - {error}")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_configuration_loading(integration_config):
    """Test configuration loading and validation."""
    from prompt_mapper.config import ConfigManager

    config_manager = ConfigManager(integration_config)
    config = config_manager.load_config()

    assert config is not None
    assert config.llm.provider == "openai"
    assert config.radarr.enabled is True
    assert config.app.interactive is False

    # Test config validation
    assert config.matching.confidence_threshold == 0.95
    assert len(config.files.extensions["video"]) > 0
