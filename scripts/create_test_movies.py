#!/usr/bin/env python3
"""Create test movie files based on the provided image structure."""

import locale
import os
import sys
from pathlib import Path

# Movie files from the screenshot - flat structure (filename, unused_size_range)
MOVIE_FILES = [
    # Column 1 - from screenshot
    ("101 Dalmatians (1961).mkv", (800, 1200)),
    ("101 Dalmatians 2 - Patchs London Adventure (2003).mkv", (700, 1000)),
    ("101 Dalmatians 2 - Patchs London Adventure (2003).srt", (0.1, 0.2)),
    ("Ainbo - Dobri duh Amazonije (2021).mkv", (900, 1300)),
    ("Aladdin 2 the Return of Jafar (1994).mkv", (650, 950)),
    ("Aladdin 2 the Return of Jafar (1994).srt", (0.1, 0.2)),
    ("Aladin i leteci cilim (2018).mkv", (800, 1100)),
    ("Alice in Wonderland (1951).mkv", (600, 900)),
    ("Alice in Wonderland (1951).srt", (0.1, 0.2)),
    ("Alladin (1992).mkv", (700, 1000)),
    ("Alladin 3 Kralj lopova (1996).mkv", (750, 1050)),
    ("Alladin Up and Away (2018).mkv", (650, 950)),
    ("Alladin Up and Away (2018).srt", (0.1, 0.2)),
    ("Arthur 2 The Revenge of Maltazard (2009).mkv", (800, 1200)),
    ("Arthur 3 The War of Two Worlds (2010).mkv", (850, 1250)),
    # Column 2 - from screenshot
    ("Arthur Christmas (2011).mkv", (900, 1300)),
    ("Arthur Christmas (2011).srt", (0.1, 0.2)),
    ("Arthur i Minimoji (2006).mkv", (750, 1100)),
    ("Asterix 2 and Cleopatra (1968).mkv", (500, 800)),
    ("Asterix 3 The Twelve Tasks of Asterix (1976).mkv", (550, 850)),
    ("Asterix 3 The Twelve Tasks of Asterix (1976).srt", (0.1, 0.2)),
    ("Asterix 4 Protiv Cezara (1985).mkv", (600, 900)),
    ("Asterix 5 U Britaniji (1986).mkv", (580, 880)),
    ("Asterix 6 and the Big Fight (1989).mkv", (620, 920)),
    ("Asterix 6 and the Big Fight (1989).srt", (0.1, 0.2)),
    ("Asterix 7 Osvaja Ameriku (1994).mkv", (650, 950)),
    ("Asterix 8 Vikinzi (2006).mkv", (700, 1000)),
    ("Asterix The Mansions of The Gods (2014).mkv", (850, 1250)),
    ("Asterix The Secret Of The Magic Potion (2018).mkv", (900, 1300)),
    ("Asterix The Secret Of The Magic Potion (2018).srt", (0.1, 0.2)),
    # Column 3 - from screenshot
    ("Asterix(1967).mkv", (450, 750)),
    ("Atlantida - Izgubljeno kraljevstvo (2001).mkv", (800, 1200)),
    ("Balto 1 (1995).mkv", (600, 900)),
    ("Balto 1 (1995).srt", (0.1, 0.2)),
    ("Balto 2 - Vučija potraga (2002).mkv", (650, 950)),
    ("Balto 3 - Krila promena (2004).mkv", (700, 1000)),
    ("Bambi (1942).mkv", (500, 800)),
    ("Bambi 2 (2006).mkv", (600, 900)),
    ("Beauty and the Beast 1 (1991).mkv", (700, 1000)),
    ("Beauty and the Beast 1 (1991).srt", (0.1, 0.2)),
    ("Beauty and the Beast 2 The Enchanted Christmas (1997).mkv", (650, 950)),
    ("Beauty and the Beast 2 The Enchanted Christmas (1997).srt", (0.1, 0.2)),
    ("Beli očnjak (2018).mkv", (800, 1200)),
    ("Blinki Bil Neustrasiva Koala (2015).mkv", (750, 1100)),
    ("Bolt - Grom - Munja (2008).mkv", (800, 1200)),
    # Additional examples for better testing variety
    ("Brojne pustolovine Vinja Pua (1977).mkv", (450, 750)),
    ("Brzi Ozzy (2016).mkv", (700, 1000)),
    ("Cars (2006).mkv", (900, 1300)),
    ("Cars 2 (2011).mkv", (850, 1200)),
    ("Cars 3 (2017).mkv", (900, 1300)),
    ("Coco (2017).mkv", (950, 1400)),
    ("Čarobni mač - U potrazi za Kamelotom (1998).mkv", (600, 900)),
    ("Čarobni princ (2018).mkv", (750, 1100)),
    ("Čarolija usnulog zmaja (2016).mkv", (700, 1000)),
    ("Finding Nemo (2003).mkv", (800, 1200)),
    ("Finding Dory (2016).mkv", (850, 1250)),
    ("Frozen (2013).mkv", (900, 1300)),
    ("Frozen 2 (2019).mkv", (950, 1400)),
    ("How to Train Your Dragon (2010).mkv", (800, 1200)),
    ("How to Train Your Dragon 2 (2014).mkv", (850, 1250)),
    ("Ice Age (2002).mkv", (700, 1000)),
    ("Ice Age 2 The Meltdown (2006).mkv", (750, 1100)),
    ("Madagascar (2005).mkv", (750, 1100)),
    ("Madagascar 2 (2008).mkv", (800, 1200)),
    ("Moana (2016).mkv", (900, 1300)),
    ("Monsters Inc (2001).mkv", (750, 1100)),
    ("Monsters University (2013).mkv", (850, 1250)),
    ("Ratatouille (2007).mkv", (850, 1250)),
    ("Shrek (2001).mkv", (700, 1000)),
    ("Shrek 2 (2004).mkv", (750, 1100)),
    ("Shrek 3 (2007).mkv", (800, 1200)),
    ("Shrek Forever After (2010).mkv", (800, 1200)),
    ("The Incredibles (2004).mkv", (800, 1200)),
    ("The Incredibles 2 (2018).mkv", (900, 1300)),
    ("The Lion King (1994).mkv", (700, 1000)),
    ("The Lion King (2019).mkv", (950, 1400)),
    ("Toy Story (1995).mkv", (650, 950)),
    ("Toy Story 2 (1999).mkv", (700, 1000)),
    ("Toy Story 3 (2010).mkv", (800, 1200)),
    ("Toy Story 4 (2019).mkv", (900, 1300)),
    ("Up (2009).mkv", (800, 1200)),
    ("WALL-E (2008).mkv", (750, 1100)),
]


def create_dummy_file(file_path: Path, size_mb: float) -> None:
    """Create a minimal dummy file for testing.

    Args:
        file_path: Path to create the file at.
        size_mb: Size in megabytes (ignored, creates minimal files).
    """
    try:
        # Create parent directory if it doesn't exist
        file_path.parent.mkdir(parents=True, exist_ok=True)

        # Create minimal file with just 1 byte
        with open(file_path, "wb") as f:
            if file_path.suffix.lower() in [".mkv", ".mp4", ".avi"]:
                # Minimal video file marker
                f.write(b"V")
            elif file_path.suffix.lower() == ".srt":
                # Minimal subtitle file marker
                f.write(b"S")
            else:
                # Generic file marker
                f.write(b"F")
    except PermissionError as e:
        print(f"⚠️  Permission error creating {file_path}: {e}")
        print("💡 This might be a CI environment issue. Continuing...")
    except Exception as e:
        print(f"❌ Error creating {file_path}: {e}")
        raise


def main() -> None:
    """Create all test movie files in a flat structure."""
    # Force UTF-8 locale for proper handling of special characters
    try:
        locale.setlocale(locale.LC_ALL, "C.UTF-8")
    except locale.Error:
        try:
            locale.setlocale(locale.LC_ALL, "en_US.UTF-8")
        except locale.Error:
            print("⚠️  Could not set UTF-8 locale, special characters may not work properly")

    # Respect MOVIES_DIR environment variable, fallback to RUNNER_TEMP in CI, then test_movies
    movies_dir = os.environ.get("MOVIES_DIR")
    if not movies_dir:
        # In CI environments, use RUNNER_TEMP for guaranteed write access
        runner_temp = os.environ.get("RUNNER_TEMP")
        if runner_temp:
            movies_dir = os.path.join(runner_temp, "test_movies")
            print(f"💡 Using CI temp directory: {movies_dir}")
        else:
            movies_dir = "test_movies"

    base_path = Path(movies_dir).resolve()

    print(f"Creating test movie files in {base_path.absolute()}")

    try:
        # Create base directory with proper permissions
        base_path.mkdir(parents=True, exist_ok=True, mode=0o755)
        print(f"📁 Base directory created/verified: {base_path}")

        # Test write permissions
        test_file = base_path / ".write_test"
        try:
            test_file.write_text("test")
            test_file.unlink()
            print("✅ Write permissions verified")
        except PermissionError:
            print(f"❌ No write permissions in {base_path}")
            print(
                "💡 Try setting MOVIES_DIR to a writable directory or running with proper permissions"
            )
            return
    except PermissionError as e:
        print(f"❌ Permission denied creating directory {base_path}: {e}")
        print("💡 Solutions:")
        print("   - Set MOVIES_DIR environment variable to a writable directory")
        print("   - In CI: Use $RUNNER_TEMP (should be set automatically)")
        print("   - Run with appropriate permissions or change directory ownership")
        return
    except Exception as e:
        print(f"❌ Unexpected error creating directory {base_path}: {e}")
        return

    total_files = 0

    print(f"\nCreating {len(MOVIE_FILES)} files in flat structure:")

    successful_files = 0
    for filename, size_range in MOVIE_FILES:
        file_path = base_path / filename
        print(f"  Creating: {filename} (1 byte)")

        create_dummy_file(file_path, 0.000001)  # Size ignored, creates 1 byte

        # Check if file was actually created
        if file_path.exists():
            successful_files += 1
        total_files += 1

    print(f"\n✅ Created {successful_files}/{total_files} files in flat structure")
    if successful_files != total_files:
        print(f"⚠️  {total_files - successful_files} files failed (likely permission issues)")
    print(f"📊 Total size: {successful_files} bytes (~{successful_files / 1024:.2f} KB)")

    # Create a summary file
    summary_path = base_path / "README.md"
    try:
        with open(summary_path, "w") as f:
            f.write("# Test Movie Files\n\n")
            f.write(
                "This directory contains minimal dummy movie files for testing the Prompt-Based Movie Mapper.\n\n"
            )
            f.write(f"- **Total files**: {successful_files}/{total_files}\n")
            f.write("- **Structure**: Flat (all files in one directory)\n")
            f.write(
                f"- **Total size**: {successful_files} bytes (~{successful_files / 1024:.2f} KB)\n"
            )
            f.write("- **File size**: 1 byte each (minimal for testing)\n\n")
            f.write("## Files List\n\n")

            # Group by type for better readability
            video_files = [f for f, _ in MOVIE_FILES if f.endswith(".mkv")]
            subtitle_files = [f for f, _ in MOVIE_FILES if f.endswith(".srt")]

            f.write(f"### Video Files ({len(video_files)})\n")
            for filename in sorted(video_files):
                f.write(f"- {filename}\n")

            f.write(f"\n### Subtitle Files ({len(subtitle_files)})\n")
            for filename in sorted(subtitle_files):
                f.write(f"- {filename}\n")

        print(f"📄 Created summary file: {summary_path}")
    except PermissionError:
        print("⚠️  Could not create summary file due to permissions")


if __name__ == "__main__":
    main()
