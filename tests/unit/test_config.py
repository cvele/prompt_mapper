"""Test configuration management."""

from pathlib import Path

import pytest

from prompt_mapper.config import Config, ConfigManager


def test_config_manager_loads_config(config_manager, temp_config_file):
    """Test that config manager loads configuration correctly."""
    config = config_manager.load_config()

    assert isinstance(config, Config)
    assert config.llm.provider == "openai"
    assert config.llm.model == "gpt-4"
    assert config.tmdb.api_key == "test-tmdb-key"


def test_config_manager_caches_config(config_manager):
    """Test that config manager caches loaded configuration."""
    config1 = config_manager.load_config()
    config2 = config_manager.get_config()

    assert config1 is config2


def test_config_manager_reload_config(config_manager):
    """Test that config manager can reload configuration."""
    config1 = config_manager.load_config()
    config2 = config_manager.reload_config()

    assert config1 is not config2
    assert config1.llm.provider == config2.llm.provider


def test_config_manager_missing_file():
    """Test that config manager raises error for missing file."""
    config_manager = ConfigManager(Path("nonexistent.yaml"))

    with pytest.raises(FileNotFoundError):
        config_manager.load_config()


def test_config_validation_invalid_provider(tmp_path):
    """Test config validation with invalid LLM provider."""
    config_content = """
llm:
  provider: "invalid"
  model: "test"
  api_key: "test"
tmdb:
  api_key: "test"
radarr:
  enabled: true
  url: "http://test"
  api_key: "test"
  default_profile:
    quality_profile_id: 1
    root_folder_path: "/test"
prompts:
  default: "test"
"""
    config_file = tmp_path / "invalid.yaml"
    config_file.write_text(config_content)

    config_manager = ConfigManager(config_file)

    with pytest.raises(Exception):  # Should raise ValidationError
        config_manager.load_config()


def test_create_default_config(tmp_path):
    """Test creating default configuration file."""
    output_path = tmp_path / "default_config.yaml"

    ConfigManager.create_default_config(output_path)

    assert output_path.exists()

    # Should be able to load the created config
    config_manager = ConfigManager(output_path)
    config = config_manager.load_config()
    assert isinstance(config, Config)
