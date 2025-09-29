"""Text processing utilities."""

import re
from difflib import SequenceMatcher
from typing import Optional


def normalize_title(title: str) -> str:
    """Normalize movie title for comparison.

    Args:
        title: Original title.

    Returns:
        Normalized title.
    """
    # Convert to lowercase
    title = title.lower()

    # Remove common prefixes/suffixes
    prefixes = ["the ", "a ", "an "]
    for prefix in prefixes:
        if title.startswith(prefix):
            title = title[len(prefix) :]
            break

    # Remove special characters and extra spaces
    title = re.sub(r"[^\w\s]", " ", title)
    title = re.sub(r"\s+", " ", title)
    title = title.strip()

    return title


def calculate_similarity(text1: str, text2: str) -> float:
    """Calculate similarity between two text strings.

    Args:
        text1: First text.
        text2: Second text.

    Returns:
        Similarity score between 0.0 and 1.0.
    """
    if not text1 or not text2:
        return 0.0

    # Normalize both texts
    norm1 = normalize_title(text1)
    norm2 = normalize_title(text2)

    # Use SequenceMatcher for similarity
    return SequenceMatcher(None, norm1, norm2).ratio()


def extract_year_from_filename(filename: str) -> Optional[int]:
    """Extract year from filename.

    Args:
        filename: Filename to parse.

    Returns:
        Extracted year or None if not found.
    """
    # Look for 4-digit year patterns
    year_patterns = [
        r"\b(19\d{2}|20\d{2})\b",  # Years from 1900-2099
        r"\((\d{4})\)",  # Years in parentheses
        r"\[(\d{4})\]",  # Years in brackets
    ]

    for pattern in year_patterns:
        match = re.search(pattern, filename)
        if match:
            year = int(match.group(1))
            # Reasonable year range for movies
            if 1900 <= year <= 2030:
                return year

    return None


def clean_filename(filename: str) -> str:
    """Clean filename for analysis.

    Args:
        filename: Original filename.

    Returns:
        Cleaned filename.
    """
    # Remove file extension
    name = re.sub(r"\.[^.]+$", "", filename)

    # Remove common release group patterns
    release_patterns = [
        r"-[A-Z0-9]+$",  # Release group at end
        r"\[[^\]]+\]",  # Content in brackets
        r"\{[^}]+\}",  # Content in braces
        r"\b(720p|1080p|2160p|4k)\b",  # Quality indicators
        r"\b(x264|x265|h264|h265)\b",  # Codec indicators
        r"\b(bluray|bdrip|webrip|dvdrip)\b",  # Source indicators
        r"\b(ac3|dts|aac)\b",  # Audio indicators
        r"\bsample\b",  # Sample indicator
    ]

    for pattern in release_patterns:
        name = re.sub(pattern, " ", name, flags=re.IGNORECASE)

    # Clean up spaces and dots
    name = re.sub(r"[._]", " ", name)
    name = re.sub(r"\s+", " ", name)
    name = name.strip()

    return name


def extract_edition_info(filename: str) -> Optional[str]:
    """Extract edition information from filename.

    Args:
        filename: Filename to parse.

    Returns:
        Edition information or None if not found.
    """
    edition_patterns = [
        r"director'?s?\s*cut",
        r"extended\s*(cut|edition)",
        r"unrated\s*(cut|edition)",
        r"theatrical\s*(cut|edition)",
        r"final\s*cut",
        r"remastered",
        r"special\s*edition",
        r"ultimate\s*edition",
        r"criterion\s*(collection|edition)",
    ]

    for pattern in edition_patterns:
        match = re.search(pattern, filename, re.IGNORECASE)
        if match:
            return match.group(0).title()

    return None


def is_sample_file(filename: str) -> bool:
    """Check if filename indicates a sample file.

    Args:
        filename: Filename to check.

    Returns:
        True if appears to be a sample file.
    """
    sample_indicators = [
        "sample",
        "trailer",
        "preview",
        "teaser",
    ]

    filename_lower = filename.lower()
    return any(indicator in filename_lower for indicator in sample_indicators)


def extract_language_hints(filename: str) -> list:
    """Extract language hints from filename.

    Args:
        filename: Filename to parse.

    Returns:
        List of language codes or names found.
    """
    language_patterns = {
        "en": ["english", "eng"],
        "es": ["spanish", "esp", "castellano"],
        "fr": ["french", "fra", "francais"],
        "de": ["german", "ger", "deutsch"],
        "it": ["italian", "ita"],
        "pt": ["portuguese", "por"],
        "ru": ["russian", "rus"],
        "ja": ["japanese", "jpn"],
        "ko": ["korean", "kor"],
        "zh": ["chinese", "chi", "mandarin"],
        "sr": ["serbian", "srp"],
        "hr": ["croatian", "hrv"],
        "bs": ["bosnian", "bos"],
    }

    found_languages = []
    filename_lower = filename.lower()

    for lang_code, variations in language_patterns.items():
        for variation in variations:
            if variation in filename_lower:
                found_languages.append(lang_code)
                break

    return list(set(found_languages))  # Remove duplicates
