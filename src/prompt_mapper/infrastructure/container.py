"""Dependency injection container."""

import logging
from functools import lru_cache
from typing import Any, Callable, Dict, Optional, Type, TypeVar

from ..config import Config, ConfigManager
from ..core.interfaces import (
    IFileScanner,
    ILLMService,
    IMovieOrchestrator,
    IMovieResolver,
    IRadarrService,
    ITMDbService,
)

T = TypeVar("T")


class Container:
    """Dependency injection container using registry pattern."""

    def __init__(self, config_manager: Optional[ConfigManager] = None) -> None:
        """Initialize container.

        Args:
            config_manager: Configuration manager instance. If None, creates default.
        """
        self._services: Dict[Type, Any] = {}
        self._factories: Dict[Type, Callable[[], Any]] = {}
        self._singletons: Dict[Type, Any] = {}
        self._config_manager = config_manager or ConfigManager()
        self._logger = logging.getLogger(__name__)

    def register_singleton(self, interface: Type[T], implementation: Type[Any]) -> None:
        """Register a singleton service.

        Args:
            interface: Interface type.
            implementation: Implementation type.
        """
        self._services[interface] = implementation
        self._logger.debug(
            f"Registered singleton: {interface.__name__} -> {implementation.__name__}"
        )

    def register_factory(self, interface: Type[T], factory: Callable[[], T]) -> None:
        """Register a factory function.

        Args:
            interface: Interface type.
            factory: Factory function that creates instances.
        """
        self._factories[interface] = factory
        self._logger.debug(f"Registered factory: {interface.__name__}")

    def register_instance(self, interface: Type[T], instance: T) -> None:
        """Register a specific instance.

        Args:
            interface: Interface type.
            instance: Pre-created instance.
        """
        self._singletons[interface] = instance
        self._logger.debug(f"Registered instance: {interface.__name__}")

    def get(self, interface: Type[T]) -> T:
        """Get service instance.

        Args:
            interface: Interface type to resolve.

        Returns:
            Service instance.

        Raises:
            ValueError: If service is not registered.
        """
        # Check for pre-registered instances
        if interface in self._singletons:
            return self._singletons[interface]  # type: ignore

        # Check for factory functions
        if interface in self._factories:
            return self._factories[interface]()  # type: ignore

        # Check for singleton services
        if interface in self._services:
            if interface not in self._singletons:
                implementation = self._services[interface]
                instance = self._create_instance(implementation)
                self._singletons[interface] = instance
            return self._singletons[interface]  # type: ignore

        raise ValueError(f"Service not registered: {interface.__name__}")

    def _create_instance(self, implementation: Type[T]) -> T:
        """Create instance with dependency injection.

        Args:
            implementation: Implementation class to instantiate.

        Returns:
            Created instance with dependencies injected.
        """
        # Get constructor signature and resolve dependencies
        import inspect

        sig = inspect.signature(implementation.__init__)
        kwargs = {}

        for param_name, param in sig.parameters.items():
            if param_name == "self":
                continue

            if param.annotation == Config:
                kwargs[param_name] = self._config_manager.get_config()
            elif hasattr(param.annotation, "__origin__"):
                # Skip generic types for now
                continue
            elif (
                param.annotation in self._services
                or param.annotation in self._factories
                or param.annotation in self._singletons
            ):
                kwargs[param_name] = self.get(param.annotation)
            elif param.default is not inspect.Parameter.empty:
                # Has default value, skip
                continue
            else:
                self._logger.warning(
                    f"Cannot resolve dependency: {param_name} of type {param.annotation}"
                )

        return implementation(**kwargs)

    @lru_cache(maxsize=1)
    def get_config(self) -> Config:
        """Get configuration instance.

        Returns:
            Configuration instance.
        """
        return self._config_manager.get_config()

    def configure_default_services(self) -> None:
        """Configure default service registrations."""
        from ..core.services import (
            AnthropicLLMService,
            FileScanner,
            MovieOrchestrator,
            MovieResolver,
            OpenAILLMService,
            RadarrService,
            TMDbService,
        )

        # Register config-dependent services
        config = self.get_config()

        # LLM Service based on provider
        if config.llm.provider == "openai":
            self.register_singleton(ILLMService, OpenAILLMService)  # type: ignore
        elif config.llm.provider == "anthropic":
            self.register_singleton(ILLMService, AnthropicLLMService)  # type: ignore
        else:
            raise ValueError(f"Unsupported LLM provider: {config.llm.provider}")

        # Other services
        self.register_singleton(ITMDbService, TMDbService)  # type: ignore
        self.register_singleton(IRadarrService, RadarrService)  # type: ignore
        self.register_singleton(IFileScanner, FileScanner)  # type: ignore
        self.register_singleton(IMovieResolver, MovieResolver)  # type: ignore
        self.register_singleton(IMovieOrchestrator, MovieOrchestrator)  # type: ignore

        self._logger.info("Default services configured")

    def create_child_container(self) -> "Container":
        """Create a child container that inherits registrations.

        Returns:
            New child container.
        """
        child = Container(self._config_manager)
        child._services = self._services.copy()
        child._factories = self._factories.copy()
        # Don't copy singletons - child should create its own instances
        return child

    def reset(self) -> None:
        """Reset container state."""
        self._services.clear()
        self._factories.clear()
        self._singletons.clear()
        # Clear config cache
        self.get_config.cache_clear()
        self._logger.debug("Container reset")

    def __enter__(self) -> "Container":
        """Context manager entry."""
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Context manager exit."""
        # Cleanup resources if needed
        pass
