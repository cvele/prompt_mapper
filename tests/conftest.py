"""Pytest configuration and fixtures."""

from pathlib import Path
from unittest.mock import Mock

import pytest

from prompt_mapper.config import Config, ConfigManager
from prompt_mapper.infrastructure import Container


@pytest.fixture
def temp_config_file(tmp_path):
    """Create a temporary configuration file."""
    config_content = """
llm:
  provider: "openai"
  model: "gpt-4"
  api_key: "test-key"

tmdb:
  api_key: "test-tmdb-key"

radarr:
  enabled: true
  url: "http://localhost:7878"
  api_key: "test-radarr-key"
  default_profile:
    quality_profile_id: 1
    root_folder_path: "/movies"

files:
  min_file_size_mb: 0  # Allow small test files

prompts:
  default: "Test prompt"
"""
    config_file = tmp_path / "config.yaml"
    config_file.write_text(config_content)
    return config_file


@pytest.fixture
def config_manager(temp_config_file):
    """Create a configuration manager with test config."""
    return ConfigManager(temp_config_file)


@pytest.fixture
def config(config_manager):
    """Load test configuration."""
    return config_manager.load_config()


@pytest.fixture
def container(config_manager):
    """Create a test container."""
    container = Container(config_manager)
    return container


@pytest.fixture
def mock_llm_service():
    """Mock LLM service."""
    return Mock()


@pytest.fixture
def mock_tmdb_service():
    """Mock TMDb service."""
    return Mock()


@pytest.fixture
def mock_radarr_service():
    """Mock Radarr service."""
    return Mock()


@pytest.fixture
def sample_movie_files(tmp_path):
    """Create sample movie files for testing."""
    movie_dir = tmp_path / "The Matrix (1999)"
    movie_dir.mkdir()

    # Create a fake video file
    video_file = movie_dir / "The.Matrix.1999.1080p.BluRay.x264-GROUP.mkv"
    video_file.write_bytes(b"fake video content" * 1000000)  # ~17MB

    # Create a subtitle file
    subtitle_file = movie_dir / "The.Matrix.1999.1080p.BluRay.x264-GROUP.srt"
    subtitle_file.write_text("1\n00:00:01,000 --> 00:00:03,000\nTest subtitle")

    return movie_dir
