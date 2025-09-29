"""File system utilities."""

import os
from pathlib import Path
from typing import Optional


def get_file_size(path: Path) -> int:
    """Get file size in bytes.

    Args:
        path: Path to file.

    Returns:
        File size in bytes.

    Raises:
        OSError: If file cannot be accessed.
    """
    return path.stat().st_size


def is_hidden_file(path: Path) -> bool:
    """Check if file is hidden.

    Args:
        path: Path to check.

    Returns:
        True if file is hidden.
    """
    # Unix-style hidden files (start with dot)
    if path.name.startswith("."):
        return True

    # Windows hidden files
    if os.name == "nt":
        try:
            import stat

            return bool(path.stat().st_file_attributes & stat.FILE_ATTRIBUTE_HIDDEN)
        except (AttributeError, OSError):
            pass

    return False


def get_directory_size(path: Path) -> int:
    """Get total size of directory in bytes.

    Args:
        path: Directory path.

    Returns:
        Total size in bytes.
    """
    total_size = 0

    try:
        for file_path in path.rglob("*"):
            if file_path.is_file():
                try:
                    total_size += get_file_size(file_path)
                except OSError:
                    # Skip files we can't access
                    continue
    except OSError:
        # Skip directories we can't access
        pass

    return total_size


def ensure_directory(path: Path) -> None:
    """Ensure directory exists, create if necessary.

    Args:
        path: Directory path to ensure.
    """
    path.mkdir(parents=True, exist_ok=True)


def is_same_file(path1: Path, path2: Path) -> bool:
    """Check if two paths refer to the same file.

    Args:
        path1: First path.
        path2: Second path.

    Returns:
        True if paths refer to the same file.
    """
    try:
        return path1.resolve() == path2.resolve()
    except OSError:
        return False


def get_available_space(path: Path) -> Optional[int]:
    """Get available disk space for path.

    Args:
        path: Path to check.

    Returns:
        Available space in bytes or None if cannot determine.
    """
    try:
        if hasattr(os, "statvfs"):  # Unix
            statvfs = os.statvfs(path)
            return statvfs.f_frsize * statvfs.f_bavail
        elif os.name == "nt":  # Windows
            import shutil

            return shutil.disk_usage(path).free
    except OSError:
        pass

    return None


def create_hardlink(source: Path, target: Path) -> bool:
    """Create hardlink from source to target.

    Args:
        source: Source file path.
        target: Target file path.

    Returns:
        True if hardlink was created successfully.
    """
    try:
        # Ensure target directory exists
        target.parent.mkdir(parents=True, exist_ok=True)

        # Create hardlink
        os.link(source, target)
        return True
    except OSError:
        return False


def safe_move_file(source: Path, target: Path) -> bool:
    """Safely move file from source to target.

    Args:
        source: Source file path.
        target: Target file path.

    Returns:
        True if move was successful.
    """
    try:
        import shutil

        # Ensure target directory exists
        target.parent.mkdir(parents=True, exist_ok=True)

        # Move file
        shutil.move(str(source), str(target))
        return True
    except (OSError, shutil.Error):
        return False


def safe_copy_file(source: Path, target: Path) -> bool:
    """Safely copy file from source to target.

    Args:
        source: Source file path.
        target: Target file path.

    Returns:
        True if copy was successful.
    """
    try:
        import shutil

        # Ensure target directory exists
        target.parent.mkdir(parents=True, exist_ok=True)

        # Copy file
        shutil.copy2(str(source), str(target))
        return True
    except (OSError, shutil.Error):
        return False
