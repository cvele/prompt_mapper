#!/usr/bin/env python3
"""Entry point for PyInstaller binary."""

import os
import sys
from pathlib import Path

# Configure SSL certificates for PyInstaller (must be done early)
if hasattr(sys, "_MEIPASS"):
    # PyInstaller frozen app - set certificate path
    cert_path = Path(sys._MEIPASS) / "certifi" / "cacert.pem"
    if cert_path.exists():
        os.environ["REQUESTS_CA_BUNDLE"] = str(cert_path)

# Add src to path so we can import prompt_mapper
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

from prompt_mapper.cli.main import main

if __name__ == "__main__":
    main()
