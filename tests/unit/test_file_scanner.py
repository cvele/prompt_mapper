"""Test file scanner service."""

from pathlib import Path

import pytest

from prompt_mapper.core.models import ScanResult
from prompt_mapper.core.services import FileScanner


@pytest.mark.asyncio
async def test_file_scanner_scan_directory(config, sample_movie_files):
    """Test file scanner can scan a directory."""
    scanner = FileScanner(config)

    result = await scanner.scan_directory(sample_movie_files)

    assert isinstance(result, ScanResult)
    assert result.root_path == sample_movie_files
    assert len(result.video_files) == 1
    assert len(result.subtitle_files) == 1
    assert result.video_files[0].name.endswith(".mkv")
    assert result.subtitle_files[0].name.endswith(".srt")


@pytest.mark.asyncio
async def test_file_scanner_nonexistent_directory(config):
    """Test file scanner with nonexistent directory."""
    scanner = FileScanner(config)

    with pytest.raises(Exception):  # Should raise FileScannerError
        await scanner.scan_directory(Path("/nonexistent"))


def test_is_video_file(config):
    """Test video file detection."""
    scanner = FileScanner(config)

    assert scanner.is_video_file(Path("movie.mkv"))
    assert scanner.is_video_file(Path("movie.mp4"))
    assert not scanner.is_video_file(Path("movie.txt"))


def test_is_subtitle_file(config):
    """Test subtitle file detection."""
    scanner = FileScanner(config)

    assert scanner.is_subtitle_file(Path("movie.srt"))
    assert scanner.is_subtitle_file(Path("movie.ass"))
    assert not scanner.is_subtitle_file(Path("movie.mkv"))


def test_should_ignore_file(config, tmp_path):
    """Test file ignore logic."""
    scanner = FileScanner(config)

    # Create test files
    sample_file = tmp_path / "sample.mkv"
    sample_file.write_bytes(b"fake content")

    trailer_file = tmp_path / "trailer.mp4"
    trailer_file.write_bytes(b"fake content")

    normal_file = tmp_path / "movie.mkv"
    normal_file.write_bytes(b"fake content")

    # Should ignore sample files
    assert scanner.should_ignore_file(sample_file)
    assert scanner.should_ignore_file(trailer_file)

    # Should not ignore normal files
    assert not scanner.should_ignore_file(normal_file)
