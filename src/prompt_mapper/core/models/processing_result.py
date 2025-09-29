"""Processing result data models."""

from enum import Enum
from pathlib import Path
from typing import List, Optional

from pydantic import BaseModel, Field

from .file_info import ScanResult
from .movie import MovieMatch


class ProcessingStatus(str, Enum):
    """Processing status enumeration."""

    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"
    USER_CANCELLED = "user_cancelled"
    REQUIRES_REVIEW = "requires_review"


class RadarrAction(str, Enum):
    """Radarr action enumeration."""

    ADDED = "added"
    EXISTS = "exists"
    UPDATED = "updated"
    SKIPPED = "skipped"
    FAILED = "failed"


class ImportResult(BaseModel):
    """File import result."""

    file_path: Path = Field(..., description="Original file path")
    imported: bool = Field(..., description="Whether import was successful")
    target_path: Optional[Path] = Field(None, description="Target path after import")
    error: Optional[str] = Field(None, description="Error message if import failed")
    method: Optional[str] = Field(None, description="Import method used (hardlink, copy, move)")

    class Config:
        """Pydantic configuration."""

        arbitrary_types_allowed = True


class ProcessingResult(BaseModel):
    """Result of processing a single movie."""

    source_path: Path = Field(..., description="Original source path")
    status: ProcessingStatus = Field(..., description="Processing status")
    scan_result: Optional[ScanResult] = Field(None, description="File scan result")
    movie_match: Optional[MovieMatch] = Field(None, description="Movie match result")
    radarr_action: Optional[RadarrAction] = Field(None, description="Action taken in Radarr")
    import_results: List[ImportResult] = Field(
        default_factory=list, description="File import results"
    )
    error_message: Optional[str] = Field(None, description="Error message if processing failed")
    processing_time_seconds: Optional[float] = Field(None, description="Time taken to process")

    # Links for reference
    tmdb_url: Optional[str] = Field(None, description="TMDb URL")
    radarr_url: Optional[str] = Field(None, description="Radarr URL")

    @property
    def is_successful(self) -> bool:
        """Check if processing was successful."""
        return self.status == ProcessingStatus.SUCCESS

    @property
    def files_imported_count(self) -> int:
        """Count of successfully imported files."""
        return sum(1 for result in self.import_results if result.imported)

    @property
    def total_files_count(self) -> int:
        """Total count of files processed."""
        return len(self.import_results)

    class Config:
        """Pydantic configuration."""

        arbitrary_types_allowed = True


class SessionSummary(BaseModel):
    """Summary of an entire processing session."""

    total_processed: int = Field(default=0, description="Total items processed")
    successful: int = Field(default=0, description="Successfully processed items")
    failed: int = Field(default=0, description="Failed items")
    skipped: int = Field(default=0, description="Skipped items")
    user_cancelled: int = Field(default=0, description="User cancelled items")
    requires_review: int = Field(default=0, description="Items requiring review")

    movies_added_to_radarr: int = Field(default=0, description="Movies added to Radarr")
    movies_existed_in_radarr: int = Field(default=0, description="Movies already in Radarr")
    files_imported: int = Field(default=0, description="Files successfully imported")

    total_processing_time_seconds: float = Field(default=0.0, description="Total processing time")
    results: List[ProcessingResult] = Field(default_factory=list, description="Individual results")

    @property
    def success_rate(self) -> float:
        """Calculate success rate."""
        if self.total_processed == 0:
            return 0.0
        return self.successful / self.total_processed

    @property
    def average_processing_time(self) -> float:
        """Calculate average processing time per item."""
        if self.total_processed == 0:
            return 0.0
        return self.total_processing_time_seconds / self.total_processed

    def add_result(self, result: ProcessingResult) -> None:
        """Add a processing result to the summary."""
        self.results.append(result)
        self.total_processed += 1

        if result.status == ProcessingStatus.SUCCESS:
            self.successful += 1
        elif result.status == ProcessingStatus.FAILED:
            self.failed += 1
        elif result.status == ProcessingStatus.SKIPPED:
            self.skipped += 1
        elif result.status == ProcessingStatus.USER_CANCELLED:
            self.user_cancelled += 1
        elif result.status == ProcessingStatus.REQUIRES_REVIEW:
            self.requires_review += 1

        if result.radarr_action == RadarrAction.ADDED:
            self.movies_added_to_radarr += 1
        elif result.radarr_action == RadarrAction.EXISTS:
            self.movies_existed_in_radarr += 1

        self.files_imported += result.files_imported_count

        if result.processing_time_seconds:
            self.total_processing_time_seconds += result.processing_time_seconds
