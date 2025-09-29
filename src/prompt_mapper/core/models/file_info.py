"""File-related data models."""

from pathlib import Path
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class FileInfo(BaseModel):
    """Information about a movie file."""

    path: Path = Field(..., description="Full path to the file")
    name: str = Field(..., description="File name")
    size_bytes: int = Field(..., description="File size in bytes")
    extension: str = Field(..., description="File extension")
    is_video: bool = Field(..., description="Whether this is a video file")
    is_subtitle: bool = Field(default=False, description="Whether this is a subtitle file")
    directory_name: str = Field(..., description="Parent directory name")
    relative_path: Path = Field(..., description="Path relative to scan root")

    @property
    def size_mb(self) -> float:
        """Get file size in MB."""
        return self.size_bytes / (1024 * 1024)

    @property
    def display_name(self) -> str:
        """Get display name for the file."""
        return (
            f"{self.directory_name}/{self.name}" if self.directory_name != self.name else self.name
        )

    model_config = ConfigDict(arbitrary_types_allowed=True)


class ScanResult(BaseModel):
    """Result of scanning a directory for movie files."""

    root_path: Path = Field(..., description="Root path that was scanned")
    video_files: List[FileInfo] = Field(default_factory=list, description="Video files found")
    subtitle_files: List[FileInfo] = Field(default_factory=list, description="Subtitle files found")
    ignored_files: List[FileInfo] = Field(
        default_factory=list, description="Files that were ignored"
    )
    total_size_bytes: int = Field(default=0, description="Total size of video files")
    scan_depth: int = Field(..., description="Depth of the scan")
    errors: List[str] = Field(default_factory=list, description="Errors encountered during scan")

    @property
    def total_size_mb(self) -> float:
        """Get total size in MB."""
        return self.total_size_bytes / (1024 * 1024)

    @property
    def main_video_file(self) -> Optional[FileInfo]:
        """Get the main video file (largest)."""
        if not self.video_files:
            return None
        return max(self.video_files, key=lambda f: f.size_bytes)

    @property
    def has_multiple_videos(self) -> bool:
        """Check if there are multiple video files."""
        return len(self.video_files) > 1

    model_config = ConfigDict(arbitrary_types_allowed=True)
