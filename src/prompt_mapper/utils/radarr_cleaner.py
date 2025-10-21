"""Radarr-style filename cleaning utilities."""

import re
from pathlib import Path
from typing import Optional, Tuple, Union


def clean_movie_filename(filename: Union[str, Path]) -> Tuple[str, Optional[int]]:
    """Clean movie filename using Radarr-style parsing logic.

    Extracts movie name and year from filename by removing common patterns
    like quality indicators, codecs, release groups, etc.

    Args:
        filename: Original filename (can be full path or just filename).

    Returns:
        Tuple of (cleaned_movie_name, year_or_none).

    Examples:
        >>> clean_movie_filename("The.Matrix.1999.1080p.BluRay.x264-GROUP")
        ('The Matrix', 1999)
        >>> clean_movie_filename("Inception (2010) [1080p]")
        ('Inception', 2010)
    """
    # Convert Path to string if needed
    if isinstance(filename, Path):
        filename = filename.stem  # Get filename without extension
    else:
        # Remove file extension
        filename = re.sub(r"\.[^.]+$", "", filename)

    original = filename

    # Extract year first (we'll use it for splitting)
    year = _extract_year(original)

    # Remove content in brackets and parentheses (often contains quality/year)
    # But keep the year if it's there
    filename = re.sub(r"\[[^\]]*\]", "", filename)
    filename = re.sub(r"\([^)]*\)", "", filename)

    # Remove quality indicators
    quality_patterns = [
        r"\b(2160p|1080p|720p|480p|4k|uhd|hd|sd)\b",
        r"\b(bluray|bdrip|brrip|webrip|web-dl|webdl|hdtv|dvdrip|dvd|vhs)\b",
        r"\b(remux|repack|proper|real|retail)\b",
    ]
    for pattern in quality_patterns:
        filename = re.sub(pattern, " ", filename, flags=re.IGNORECASE)

    # Remove codec information
    codec_patterns = [
        r"\b(x264|x265|h264|h265|hevc|xvid|divx|avc)\b",
        r"\b(10bit|8bit|hi10p)\b",
    ]
    for pattern in codec_patterns:
        filename = re.sub(pattern, " ", filename, flags=re.IGNORECASE)

    # Remove audio information
    audio_patterns = [
        r"\b(aac|ac3|dts|dts-hd|truehd|atmos|dd|dd\+|eac3|flac|mp3|pcm)\b",
        r"\b([257])\.1\b",  # 2.1, 5.1, 7.1 audio
    ]
    for pattern in audio_patterns:
        filename = re.sub(pattern, " ", filename, flags=re.IGNORECASE)

    # Remove release group (usually at the end after a dash or in brackets)
    filename = re.sub(r"-[A-Za-z0-9]+$", "", filename)
    filename = re.sub(r"\{[^}]+\}", "", filename)

    # Remove other common tags
    other_patterns = [
        r"\b(extended|unrated|remastered|theatrical|director\'?s?\.?cut|final\.cut|special\.edition)\b",
        r"\b(internal|limited|festival|subbed|dubbed|multi|dual)\b",
        r"\b(complete|proper|real|retail)\b",
    ]
    for pattern in other_patterns:
        filename = re.sub(pattern, " ", filename, flags=re.IGNORECASE)

    # Remove year from title if present (we already extracted it)
    if year:
        filename = re.sub(rf"\b{year}\b", "", filename)

    # Replace dots, underscores with spaces
    filename = re.sub(r"[._]", " ", filename)

    # Remove multiple spaces
    filename = re.sub(r"\s+", " ", filename)

    # Clean up and capitalize
    filename = filename.strip()

    # Remove "sample" if present
    if "sample" in filename.lower():
        filename = re.sub(r"\bsample\b", "", filename, flags=re.IGNORECASE)
        filename = re.sub(r"\s+", " ", filename).strip()

    if not filename:
        # Fallback to original if we cleaned too much
        filename = re.sub(r"[._]", " ", original)
        filename = re.sub(r"\s+", " ", filename).strip()

    return filename, year


def _extract_year(filename: str) -> Optional[int]:
    """Extract year from filename.

    Args:
        filename: Filename to parse.

    Returns:
        Extracted year or None if not found.
    """
    # Look for year in common patterns
    year_patterns = [
        r"\((\d{4})\)",  # (2020)
        r"\[(\d{4})\]",  # [2020]
        r"\b(19\d{2}|20[0-2]\d)\b",  # 1900-2029
    ]

    for pattern in year_patterns:
        match = re.search(pattern, filename)
        if match:
            year = int(match.group(1))
            # Reasonable year range for movies
            if 1900 <= year <= 2030:
                return year

    return None


def extract_edition_info(filename: str) -> Optional[str]:
    """Extract edition information from filename (Director's Cut, Extended, etc.).

    Args:
        filename: Filename to parse.

    Returns:
        Edition information or None if not found.
    """
    edition_patterns = [
        (r"director'?s?\.?\s*cut", "Director's Cut"),
        (r"extended\.?\s*(cut|edition)?", "Extended"),
        (r"unrated\.?\s*(cut|edition)?", "Unrated"),
        (r"theatrical\.?\s*(cut|edition)?", "Theatrical"),
        (r"final\.?\s*cut", "Final Cut"),
        (r"remastered", "Remastered"),
        (r"special\.?\s*edition", "Special Edition"),
        (r"ultimate\.?\s*edition", "Ultimate Edition"),
        (r"criterion\.?\s*(collection|edition)", "Criterion"),
    ]

    for pattern, label in edition_patterns:
        if re.search(pattern, filename, re.IGNORECASE):
            return label

    return None
