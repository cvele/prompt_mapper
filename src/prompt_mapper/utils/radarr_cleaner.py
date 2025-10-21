"""Movie filename parsing utilities using GuessIt library."""

from pathlib import Path
from typing import Optional, Tuple, Union

import guessit

# Mapping of GuessIt edition names to readable format
EDITION_MAP = {
    "director's cut": "Director's Cut",
    "directors cut": "Director's Cut",
    "extended": "Extended",
    "unrated": "Unrated",
    "theatrical": "Theatrical",
    "final cut": "Final Cut",
    "remastered": "Remastered",
    "special": "Special Edition",
    "special edition": "Special Edition",
    "ultimate": "Ultimate Edition",
    "ultimate edition": "Ultimate Edition",
    "criterion": "Criterion",
}


def clean_movie_filename(filename: Union[str, Path]) -> Tuple[str, Optional[int]]:
    """Extract movie name and year from filename using GuessIt library.

    Args:
        filename: Original filename (can be full path or just filename).

    Returns:
        Tuple of (movie_title, year_or_none).

    Examples:
        >>> clean_movie_filename("The.Matrix.1999.1080p.BluRay.x264-GROUP")
        ('The Matrix', 1999)
        >>> clean_movie_filename("Inception (2010) [1080p]")
        ('Inception', 2010)
        >>> clean_movie_filename("Goosebumps.2015.1080p.BluRay.DTS.X264.CyTSuNee.mkv")
        ('Goosebumps', 2015)
    """
    # Convert Path to string if needed
    if isinstance(filename, Path):
        filename = str(filename.name)  # Get just the filename part
    else:
        # Extract just the filename if it's a full path
        filename = str(Path(filename).name)

    # Use GuessIt to parse the filename
    guess = guessit.guessit(filename)

    # Extract title
    title = guess.get("title", "")

    # Remove "sample" from title if present (sample files)
    if title and "sample" in title.lower():
        # Remove the word "sample" from the title
        title = " ".join(word for word in title.split() if word.lower() != "sample")
        title = title.strip()

    # Extract year if available
    year = guess.get("year")

    return title, year


def extract_edition_info(filename: str) -> Optional[str]:
    """Extract edition information from filename (Director's Cut, Extended, etc.).

    Args:
        filename: Filename to parse.

    Returns:
        Edition information or None if not found.
    """
    # Use GuessIt to parse the filename
    guess = guessit.guessit(filename)

    # GuessIt provides 'edition' field for special editions
    edition = guess.get("edition")

    if edition:
        # GuessIt returns edition as a list sometimes
        if isinstance(edition, list):
            result = []
            for e in edition:
                e_str = str(e).lower()
                # Check if it's in our map
                mapped = EDITION_MAP.get(e_str, str(e).title())
                result.append(mapped)
            return " ".join(result)
        else:
            # Single edition string
            e_str = str(edition).lower()
            return EDITION_MAP.get(e_str, str(edition).title())

    # Fallback: Check title for edition keywords
    # Sometimes GuessIt includes edition info in the title
    title = str(guess.get("title", "")).lower()
    if title:
        # Check for edition patterns in the title
        if "extended edition" in title or "extended cut" in title:
            return "Extended"
        elif "unrated cut" in title or "unrated edition" in title:
            return "Unrated"
        elif "final cut" in title:
            return "Final Cut"
        elif "director's cut" in title or "directors cut" in title:
            return "Director's Cut"
        elif "theatrical" in title:
            return "Theatrical"
        elif "remastered" in title:
            return "Remastered"
        elif "special edition" in title:
            return "Special Edition"
        elif "ultimate edition" in title:
            return "Ultimate Edition"
        elif "criterion" in title:
            return "Criterion"

    # Check for other edition-like fields
    if guess.get("other"):
        other = guess.get("other")
        if isinstance(other, list):
            # Look for edition-related keywords
            for item in other:
                item_str = str(item).lower()
                if "remastered" in item_str:
                    return "Remastered"
                elif "criterion" in item_str:
                    return "Criterion"

    return None
