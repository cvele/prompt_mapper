#!/usr/bin/env python3
"""Entry point for PyInstaller binary."""

# DISABLE SSL VERIFICATION FIRST - BEFORE ANY OTHER IMPORTS
import os
import ssl
import sys

# Always disable SSL verification - no conditions, just do it
os.environ["PYTHONHTTPSVERIFY"] = "0"
ssl._create_default_https_context = ssl._create_unverified_context

from pathlib import Path

# Add src to path so we can import prompt_mapper
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

from prompt_mapper.cli.main import main

if __name__ == "__main__":
    main()
