#!/usr/bin/env python3
"""Entry point for PyInstaller binary."""

# DISABLE SSL VERIFICATION WITHOUT USING SSL MODULE
import os
import sys
from pathlib import Path

# Set environment variables to disable SSL verification everywhere
os.environ["PYTHONHTTPSVERIFY"] = "0"
os.environ["REQUESTS_CA_BUNDLE"] = ""
os.environ["CURL_CA_BUNDLE"] = ""

# Add src to path so we can import prompt_mapper
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

from prompt_mapper.cli.main import main

if __name__ == "__main__":
    main()
