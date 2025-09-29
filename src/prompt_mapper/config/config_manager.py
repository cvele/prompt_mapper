"""Configuration management."""

import os
from pathlib import Path
from typing import Any, Dict, Optional

import yaml
from pydantic import ValidationError

from .models import Config


class ConfigManager:
    """Manages application configuration loading and validation."""

    def __init__(self, config_path: Optional[Path] = None):
        """Initialize config manager.

        Args:
            config_path: Path to configuration file. If None, searches standard locations.
        """
        self._config_path = config_path
        self._config: Optional[Config] = None

    def load_config(self) -> Config:
        """Load and validate configuration.

        Returns:
            Validated configuration object.

        Raises:
            FileNotFoundError: If configuration file is not found.
            ValidationError: If configuration is invalid.
            yaml.YAMLError: If YAML parsing fails.
        """
        if self._config is not None:
            return self._config

        config_path = self._find_config_file()
        raw_config = self._load_yaml_file(config_path)

        try:
            self._config = Config(**raw_config)
        except ValidationError as e:
            raise ValueError(f"Configuration validation failed: {e}")

        return self._config

    def reload_config(self) -> Config:
        """Reload configuration from file.

        Returns:
            Newly loaded configuration object.
        """
        self._config = None
        return self.load_config()

    def get_config(self) -> Config:
        """Get current configuration, loading if necessary.

        Returns:
            Current configuration object.
        """
        if self._config is None:
            return self.load_config()
        return self._config

    def _find_config_file(self) -> Path:
        """Find configuration file in standard locations.

        Returns:
            Path to configuration file.

        Raises:
            FileNotFoundError: If no configuration file is found.
        """
        if self._config_path is not None:
            if self._config_path.exists():
                return self._config_path
            raise FileNotFoundError(f"Configuration file not found: {self._config_path}")

        # Search standard locations
        search_paths = [
            Path.cwd() / "config" / "config.yaml",
            Path.cwd() / "config.yaml",
            Path.home() / ".config" / "prompt_mapper" / "config.yaml",
            Path.home() / ".prompt_mapper" / "config.yaml",
        ]

        # Add environment variable path if set
        env_config = os.getenv("PROMPT_MAPPER_CONFIG")
        if env_config:
            search_paths.insert(0, Path(env_config))

        for path in search_paths:
            if path.exists():
                return path

        raise FileNotFoundError(
            f"Configuration file not found in any of these locations: "
            f"{[str(p) for p in search_paths]}"
        )

    def _load_yaml_file(self, path: Path) -> Dict[str, Any]:
        """Load YAML file with environment variable expansion.

        Args:
            path: Path to YAML file.

        Returns:
            Parsed YAML data with environment variables expanded.

        Raises:
            yaml.YAMLError: If YAML parsing fails.
        """
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()

        # Expand environment variables
        content = os.path.expandvars(content)

        try:
            result = yaml.safe_load(content)
            if not isinstance(result, dict):
                raise yaml.YAMLError(f"YAML file {path} must contain a dictionary at root level")
            return result
        except yaml.YAMLError as e:
            raise yaml.YAMLError(f"Failed to parse YAML file {path}: {e}")

    @classmethod
    def create_default_config(cls, output_path: Path) -> None:
        """Create a default configuration file.

        Args:
            output_path: Path where to create the configuration file.
        """
        # Read the example config from the package
        example_config_path = (
            Path(__file__).parent.parent.parent.parent / "config" / "config.example.yaml"
        )

        if not example_config_path.exists():
            # Fallback to creating a minimal config
            default_config = {
                "llm": {
                    "provider": "openai",
                    "model": "gpt-4",
                    "api_key": "${OPENAI_API_KEY}",
                },
                "tmdb": {
                    "api_key": "${TMDB_API_KEY}",
                },
                "radarr": {
                    "enabled": True,
                    "url": "http://localhost:7878",
                    "api_key": "${RADARR_API_KEY}",
                    "default_profile": {
                        "quality_profile_id": 1,
                        "root_folder_path": "/movies",
                    },
                },
                "prompts": {
                    "default": (
                        "Analyze the following movie filename/folder name and extract "
                        "the canonical movie information. Consider common naming patterns, "
                        "release years, and quality indicators. Ignore release group tags "
                        "and technical details."
                    )
                },
            }

            with open(output_path, "w", encoding="utf-8") as f:
                yaml.dump(default_config, f, default_flow_style=False, indent=2)
        else:
            # Copy the example config
            import shutil

            shutil.copy2(example_config_path, output_path)

    def validate_config_file(self, config_path: Path) -> bool:
        """Validate a configuration file without loading it as current config.

        Args:
            config_path: Path to configuration file to validate.

        Returns:
            True if configuration is valid, False otherwise.
        """
        try:
            raw_config = self._load_yaml_file(config_path)
            Config(**raw_config)
            return True
        except (ValidationError, yaml.YAMLError, FileNotFoundError):
            return False
