"""Logging configuration and setup."""

import logging
import logging.handlers
from pathlib import Path
from typing import Callable, Optional

from ..config.models import LoggingConfig


def setup_logging(config: LoggingConfig) -> None:
    """Set up logging configuration.

    Args:
        config: Logging configuration.
    """
    # Create logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, config.level))

    # Clear existing handlers
    root_logger.handlers.clear()

    # Create formatter
    formatter = logging.Formatter(config.format)

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(getattr(logging, config.level))
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # File handler (if configured)
    if config.file:
        log_path = Path(config.file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        file_handler = logging.handlers.RotatingFileHandler(
            log_path,
            maxBytes=config.max_size_mb * 1024 * 1024,
            backupCount=config.backup_count,
            encoding="utf-8",
        )
        file_handler.setLevel(getattr(logging, config.level))
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)

    # Set third-party loggers to WARNING to reduce noise
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("requests").setLevel(logging.WARNING)

    logging.info(f"Logging configured with level {config.level}")


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance.

    Args:
        name: Logger name (typically __name__).

    Returns:
        Logger instance.
    """
    return logging.getLogger(name)


class LoggerMixin:
    """Mixin class that provides logging functionality."""

    @property
    def logger(self) -> logging.Logger:
        """Get logger for this class."""
        return logging.getLogger(f"{self.__class__.__module__}.{self.__class__.__name__}")


def log_function_call(logger: Optional[logging.Logger] = None) -> Callable:
    """Decorator to log function calls.

    Args:
        logger: Logger to use. If None, uses function's module logger.
    """

    def decorator(func: Callable) -> Callable:
        def wrapper(*args, **kwargs):  # type: ignore
            func_logger = logger or logging.getLogger(func.__module__)
            func_logger.debug(f"Calling {func.__name__} with args={args}, kwargs={kwargs}")
            try:
                result = func(*args, **kwargs)
                func_logger.debug(f"{func.__name__} completed successfully")
                return result
            except Exception as e:
                func_logger.error(f"{func.__name__} failed with error: {e}")
                raise

        return wrapper

    return decorator
