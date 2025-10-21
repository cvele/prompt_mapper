"""CLI integration tests."""

import os
import subprocess
from pathlib import Path

import pytest


@pytest.mark.integration
def test_cli_help():
    """Test CLI help command."""
    result = subprocess.run(
        ["python", "-m", "prompt_mapper.cli", "--help"],
        capture_output=True,
        text=True,
        cwd=Path(__file__).parent.parent.parent,
    )

    assert result.returncode == 0
    assert "Prompt-Based Movie Mapper" in result.stdout
    assert "scan" in result.stdout
    assert "validate" in result.stdout
    assert "init" in result.stdout


@pytest.mark.integration
def test_cli_init_command(tmp_path):
    """Test CLI init command."""
    config_path = tmp_path / "test_config.yaml"

    result = subprocess.run(
        ["python", "-m", "prompt_mapper.cli", "init", "--output", str(config_path)],
        capture_output=True,
        text=True,
        cwd=Path(__file__).parent.parent.parent,
    )

    assert result.returncode == 0
    assert config_path.exists()

    # Check config content
    content = config_path.read_text()
    assert "llm:" in content
    assert "tmdb:" in content
    assert "radarr:" in content


@pytest.mark.integration
def test_cli_validate_command(integration_config):
    """Test CLI validate command."""
    result = subprocess.run(
        ["python", "-m", "prompt_mapper.cli", "--config", str(integration_config), "validate"],
        capture_output=True,
        text=True,
        cwd=Path(__file__).parent.parent.parent,
    )

    # Should not crash (may have validation errors but shouldn't fail)
    assert result.returncode in [0, 1]  # 1 for validation errors is OK


@pytest.mark.integration
def test_cli_status_command(integration_config):
    """Test CLI status command."""
    result = subprocess.run(
        ["python", "-m", "prompt_mapper.cli", "--config", str(integration_config), "status"],
        capture_output=True,
        text=True,
        cwd=Path(__file__).parent.parent.parent,
    )

    assert result.returncode == 0
    assert "Prompt-Based Movie Mapper Status" in result.stdout
    assert "LLM Provider" in result.stdout
    assert "TMDb Configured" in result.stdout


@pytest.mark.integration
def test_cli_with_real_api_keys(test_movies_path, integration_config):
    """Test CLI with real API keys if available."""
    # Load config to check if real API keys are configured
    import tempfile

    import yaml

    with open(integration_config) as f:
        config_data = yaml.safe_load(f)

    tmdb_key = config_data.get("tmdb", {}).get("api_key")
    openai_key = config_data.get("llm", {}).get("api_key")

    # Skip if using placeholder test keys
    if tmdb_key == "test-tmdb-key" or openai_key == "test-key-integration":
        pytest.skip("Real API keys not configured in integration config")

    # Create temporary config with real keys

    config_data = {
        "llm": {"provider": "openai", "model": "gpt-4o-mini", "api_key": openai_key},
        "tmdb": {"api_key": tmdb_key},
        "radarr": {
            "enabled": False,  # Disable for this test
            "url": "http://localhost:7878",  # Still required even when disabled
            "api_key": "dummy-key",
            "default_profile": {"quality_profile_id": 1, "root_folder_path": "/movies"},
        },
        "prompts": {"default": "Extract movie information from filename"},
        "app": {"interactive": False},
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        yaml.dump(config_data, f)
        config_path = f.name

    try:
        # Test with the test movies directory
        if not test_movies_path.exists():
            pytest.skip("Test directory not found")

        result = subprocess.run(
            [
                "python",
                "-m",
                "prompt_mapper.cli",
                "--config",
                config_path,
                "scan",
                str(test_movies_path),
            ],
            capture_output=True,
            text=True,
            timeout=120,  # Longer timeout for real API calls
            cwd=Path(__file__).parent.parent.parent,
        )

        print("STDOUT:", result.stdout)
        print("STDERR:", result.stderr)

        # Should succeed with real API keys
        assert result.returncode == 0
        assert "Cars" in result.stdout or "Processing" in result.stdout

    finally:
        # Clean up temp file
        os.unlink(config_path)
