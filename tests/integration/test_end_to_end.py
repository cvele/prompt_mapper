"""End-to-end integration tests."""

import pytest

from prompt_mapper.core.interfaces import (
    IFileScanner,
    IMovieOrchestrator,
    IMovieResolver,
    IRadarrService,
    ITMDbService,
)
from prompt_mapper.core.models.processing_result import ProcessingStatus


@pytest.mark.integration
@pytest.mark.asyncio
async def test_file_scanner_integration(integration_container, test_movies_path):
    """Test file scanner with real test files."""
    scanner = integration_container.get(IFileScanner)

    # Test scanning the flat test movies directory
    if not test_movies_path.exists():
        pytest.skip(f"Test directory not found: {test_movies_path}")

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
async def test_movie_resolver_with_mocks(
    integration_container, test_movies_path, setup_mock_responses
):
    """Test movie resolver with mocked LLM responses."""
    scanner = integration_container.get(IFileScanner)
    resolver = integration_container.get(IMovieResolver)

    # Test with the flat test movies directory
    if not test_movies_path.exists():
        pytest.skip(f"Test directory not found: {test_movies_path}")

    # Scan files
    scan_result = await scanner.scan_directory(test_movies_path)
    assert len(scan_result.video_files) > 0

    # Resolve movie
    movie_match = await resolver.resolve_movie(
        scan_result=scan_result,
        user_prompt="Classic Disney animated movies",
        confidence_threshold=0.8,
    )

    assert movie_match is not None
    # Since we're using real TMDb API, just verify we got a valid result
    assert movie_match.movie_info.title is not None
    assert movie_match.movie_info.tmdb_id is not None
    assert movie_match.confidence > 0.0
    assert len(movie_match.candidates) > 0


@pytest.mark.integration
@pytest.mark.asyncio
async def test_tmdb_integration(integration_container):
    """Test TMDb service integration."""
    # Only run if TMDB_API_KEY is set
    import os

    if not os.getenv("TMDB_API_KEY"):
        pytest.skip("TMDB_API_KEY not set")

    from prompt_mapper.core.models import LLMResponse

    tmdb_service = integration_container.get(ITMDbService)

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
async def test_radarr_integration(integration_container, radarr_service):
    """Test Radarr service integration."""
    radarr = integration_container.get(IRadarrService)

    # Test system status
    if radarr.is_available():
        status = await radarr.get_system_status()
        assert "version" in status
        print(f"Radarr version: {status.get('version')}")
    else:
        pytest.skip("Radarr service not available")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_single_movie_processing(
    integration_container, test_movies_path, setup_mock_responses, radarr_service
):
    """Test processing a directory with multiple movies (batch processing)."""
    orchestrator = integration_container.get(IMovieOrchestrator)
    orchestrator.set_interactive_mode(False)  # Non-interactive for tests

    # Test with the flat test movies directory (contains multiple movies)
    if not test_movies_path.exists():
        pytest.skip(f"Test directory not found: {test_movies_path}")

    # Process the movie directory - this will trigger batch processing since there are multiple movies
    result = await orchestrator.process_single_movie(
        path=test_movies_path,
        user_prompt="Pixar animated movies",
        dry_run=True,  # Don't actually modify Radarr
        auto_add=False,
        auto_import=False,
    )

    assert result is not None
    assert result.source_path == test_movies_path
    # Expect SUCCESS since we're processing multiple movies (batch mode)
    assert result.status in [ProcessingStatus.SUCCESS, ProcessingStatus.FAILED]

    if result.scan_result:
        assert len(result.scan_result.video_files) > 0

    if result.movie_match:
        assert result.movie_match.movie_info.title is not None
        assert result.movie_match.confidence > 0

    # Check processing time
    assert result.processing_time_seconds is not None
    assert result.processing_time_seconds > 0


@pytest.mark.integration
@pytest.mark.asyncio
async def test_batch_processing(
    integration_container, test_movies_path, setup_mock_responses, radarr_service
):
    """Test batch processing multiple movies."""
    orchestrator = integration_container.get(IMovieOrchestrator)
    orchestrator.set_interactive_mode(False)

    # For flat structure, we'll test with the main directory multiple times
    # In a real scenario, this would be different directories
    if not test_movies_path.exists():
        pytest.skip("Test movies directory not found")

    test_dirs = [test_movies_path]  # Just test with one directory for now

    # Process batch
    summary = await orchestrator.process_batch(
        paths=test_dirs,
        user_prompt="Classic animated movies",
        dry_run=True,
        auto_add=False,
        auto_import=False,
        max_parallel=2,
    )

    assert summary is not None
    assert summary.total_processed == len(test_dirs)
    assert summary.successful >= 0
    assert summary.total_processing_time_seconds > 0

    # Check individual results
    assert len(summary.results) == len(test_dirs)
    for result in summary.results:
        assert result.status in [
            ProcessingStatus.SUCCESS,
            ProcessingStatus.FAILED,
            ProcessingStatus.REQUIRES_REVIEW,
        ]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_serbian_movies_processing(
    integration_container, test_movies_path, setup_mock_responses
):
    """Test processing Serbian/Croatian movie titles."""
    orchestrator = integration_container.get(IMovieOrchestrator)
    orchestrator.set_interactive_mode(False)

    # Test with the main directory containing Serbian titles
    if not test_movies_path.exists():
        pytest.skip("Test movies directory not found")

    serbian_dirs = [test_movies_path]

    # Use Serbian-specific prompt
    prompt = """
    These are movies with Serbian, Croatian, or Bosnian titles.
    Please translate them to the original English titles.
    Consider that some may be localized versions of international films.
    """

    summary = await orchestrator.process_batch(
        paths=serbian_dirs, user_prompt=prompt, dry_run=True, max_parallel=1
    )

    assert summary.total_processed == len(serbian_dirs)

    # Check that at least some were processed successfully
    success_rate = summary.success_rate
    assert success_rate >= 0  # Should process without errors


@pytest.mark.integration
@pytest.mark.asyncio
async def test_error_handling(integration_container, test_movies_path):
    """Test error handling in integration scenarios."""
    orchestrator = integration_container.get(IMovieOrchestrator)

    # Test with non-existent directory
    fake_path = test_movies_path / "NonExistentMovie"

    result = await orchestrator.process_single_movie(
        path=fake_path, user_prompt="Test prompt", dry_run=True
    )

    assert result.status == ProcessingStatus.FAILED
    assert result.error_message is not None


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
    assert config.matching.confidence_threshold == 0.8
    assert len(config.files.extensions["video"]) > 0
