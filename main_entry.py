#!/usr/bin/env python3
"""Entry point for PyInstaller binary."""

import sys
from pathlib import Path

# Add src to path so we can import prompt_mapper
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

from prompt_mapper.cli.main import main

if __name__ == "__main__":
    main()
