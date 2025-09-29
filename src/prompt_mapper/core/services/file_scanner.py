"""File scanner service implementation."""

import asyncio
from pathlib import Path
from typing import List

from ...config.models import Config
from ...infrastructure.logging import LoggerMixin
from ...utils import FileScannerError, get_file_size, is_hidden_file
from ..interfaces import IFileScanner
from ..models import FileInfo, ScanResult


class FileScanner(IFileScanner, LoggerMixin):
    """File scanner service implementation."""

    def __init__(self, config: Config):
        """Initialize file scanner.

        Args:
            config: Application configuration.
        """
        self._config = config
        self._video_extensions = set(
            ext.lower() for ext in config.files.extensions.get("video", [])
        )
        self._subtitle_extensions = set(
            ext.lower() for ext in config.files.extensions.get("subtitle", [])
        )
        self._ignore_patterns = [pattern.lower() for pattern in config.files.ignore_patterns]
        self._min_size_bytes = config.files.min_file_size_mb * 1024 * 1024
        self._max_depth = config.files.scan_depth

    async def scan_directory(self, path: Path) -> ScanResult:
        """Scan directory for movie files.

        Args:
            path: Directory path to scan.

        Returns:
            Scan result with found files.

        Raises:
            FileScannerError: If scan fails.
        """
        if not path.exists():
            raise FileScannerError(f"Path does not exist: {path}")

        if not path.is_dir():
            raise FileScannerError(f"Path is not a directory: {path}")

        self.logger.info(f"Scanning directory: {path}")

        scan_result = ScanResult(root_path=path, scan_depth=self._max_depth)

        try:
            await self._scan_recursive(path, path, scan_result, depth=0)
        except Exception as e:
            error_msg = f"Error scanning directory {path}: {e}"
            self.logger.error(error_msg)
            scan_result.errors.append(error_msg)

        # Calculate total size
        scan_result.total_size_bytes = sum(f.size_bytes for f in scan_result.video_files)

        self.logger.info(
            f"Scan completed: {len(scan_result.video_files)} video files, "
            f"{len(scan_result.subtitle_files)} subtitle files, "
            f"{len(scan_result.ignored_files)} ignored files"
        )

        return scan_result

    async def scan_multiple_directories(self, paths: List[Path]) -> List[ScanResult]:
        """Scan multiple directories for movie files.

        Args:
            paths: List of directory paths to scan.

        Returns:
            List of scan results.

        Raises:
            FileScannerError: If scan fails.
        """
        self.logger.info(f"Scanning {len(paths)} directories")

        tasks = [self.scan_directory(path) for path in paths]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        scan_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                self.logger.error(f"Failed to scan {paths[i]}: {result}")
                # Create empty result with error
                scan_result = ScanResult(
                    root_path=paths[i], scan_depth=self._max_depth, errors=[str(result)]
                )
                scan_results.append(scan_result)
            else:
                scan_results.append(result)

        return scan_results

    def is_video_file(self, path: Path) -> bool:
        """Check if file is a video file.

        Args:
            path: File path to check.

        Returns:
            True if file is a video file.
        """
        return path.suffix.lower() in self._video_extensions

    def is_subtitle_file(self, path: Path) -> bool:
        """Check if file is a subtitle file.

        Args:
            path: File path to check.

        Returns:
            True if file is a subtitle file.
        """
        return path.suffix.lower() in self._subtitle_extensions

    def should_ignore_file(self, path: Path) -> bool:
        """Check if file should be ignored.

        Args:
            path: File path to check.

        Returns:
            True if file should be ignored.
        """
        filename_lower = path.name.lower()

        # Check ignore patterns
        for pattern in self._ignore_patterns:
            if pattern in filename_lower:
                return True

        # Check if hidden file
        if is_hidden_file(path):
            return True

        # Check file size for video files
        if self.is_video_file(path):
            try:
                size = get_file_size(path)
                if size < self._min_size_bytes:
                    self.logger.debug(f"Ignoring small video file: {path} ({size} bytes)")
                    return True
            except OSError:
                self.logger.warning(f"Cannot get size for file: {path}")
                return True

        return False

    async def _scan_recursive(
        self, current_path: Path, root_path: Path, scan_result: ScanResult, depth: int
    ) -> None:
        """Recursively scan directory.

        Args:
            current_path: Current directory being scanned.
            root_path: Original root path.
            scan_result: Scan result to populate.
            depth: Current recursion depth.
        """
        if depth > self._max_depth:
            return

        try:
            # Iterate through directory contents
            for item in current_path.iterdir():
                if item.is_file():
                    await self._process_file(item, root_path, scan_result)
                elif item.is_dir() and not is_hidden_file(item):
                    # Recurse into subdirectory
                    await self._scan_recursive(item, root_path, scan_result, depth + 1)
        except PermissionError:
            error_msg = f"Permission denied accessing: {current_path}"
            self.logger.warning(error_msg)
            scan_result.errors.append(error_msg)
        except OSError as e:
            error_msg = f"Error accessing {current_path}: {e}"
            self.logger.warning(error_msg)
            scan_result.errors.append(error_msg)

    async def _process_file(
        self, file_path: Path, root_path: Path, scan_result: ScanResult
    ) -> None:
        """Process a single file.

        Args:
            file_path: Path to file.
            root_path: Root scan path.
            scan_result: Scan result to populate.
        """
        try:
            # Create file info
            file_info = FileInfo(
                path=file_path,
                name=file_path.name,
                size_bytes=get_file_size(file_path),
                extension=file_path.suffix,
                is_video=self.is_video_file(file_path),
                is_subtitle=self.is_subtitle_file(file_path),
                directory_name=file_path.parent.name,
                relative_path=file_path.relative_to(root_path),
            )

            # Check if should be ignored
            if self.should_ignore_file(file_path):
                scan_result.ignored_files.append(file_info)
                return

            # Categorize file
            if file_info.is_video:
                scan_result.video_files.append(file_info)
                self.logger.debug(f"Found video file: {file_path}")
            elif file_info.is_subtitle:
                scan_result.subtitle_files.append(file_info)
                self.logger.debug(f"Found subtitle file: {file_path}")
            else:
                # Not a recognized media file, ignore
                scan_result.ignored_files.append(file_info)

        except OSError as e:
            error_msg = f"Error processing file {file_path}: {e}"
            self.logger.warning(error_msg)
            scan_result.errors.append(error_msg)
