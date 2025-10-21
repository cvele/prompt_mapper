"""File scanner interface."""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import List

from ..models import ScanResult


class IFileScanner(ABC):
    """Interface for file scanning services."""

    @abstractmethod
    async def scan_directory(self, path: Path) -> ScanResult:
        """Scan directory for movie files.

        Args:
            path: Directory path to scan.

        Returns:
            Scan result with found files.

        Raises:
            FileScannerError: If scan fails.
        """
        pass

    @abstractmethod
    async def scan_multiple_directories(self, paths: List[Path]) -> List[ScanResult]:
        """Scan multiple directories for movie files.

        Args:
            paths: List of directory paths to scan.

        Returns:
            List of scan results.

        Raises:
            FileScannerError: If scan fails.
        """
        pass

    @abstractmethod
    async def list_movie_files(self, path: Path) -> List[Path]:
        """List all movie files recursively in a directory (flat list).

        Args:
            path: Directory path to scan.

        Returns:
            Flat list of movie file paths.

        Raises:
            FileScannerError: If scan fails.
        """
        pass

    @abstractmethod
    def is_video_file(self, path: Path) -> bool:
        """Check if file is a video file.

        Args:
            path: File path to check.

        Returns:
            True if file is a video file.
        """
        pass

    @abstractmethod
    def is_subtitle_file(self, path: Path) -> bool:
        """Check if file is a subtitle file.

        Args:
            path: File path to check.

        Returns:
            True if file is a subtitle file.
        """
        pass

    @abstractmethod
    def should_ignore_file(self, path: Path) -> bool:
        """Check if file should be ignored.

        Args:
            path: File path to check.

        Returns:
            True if file should be ignored.
        """
        pass
