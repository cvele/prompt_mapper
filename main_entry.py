#!/usr/bin/env python3
"""Entry point for PyInstaller binary."""

import os
import sys
from pathlib import Path

# Configure SSL certificates for PyInstaller (must be done early)
if hasattr(sys, "_MEIPASS"):
    # PyInstaller frozen app - set certificate path
    cert_path = Path(sys._MEIPASS) / "cacert.pem"
    if cert_path.exists():
        os.environ["REQUESTS_CA_BUNDLE"] = str(cert_path)
        # Debug: verify certificate file
        try:
            with open(cert_path, "r") as f:
                content = f.read(100)  # Read first 100 chars
                if content.startswith("-----BEGIN CERTIFICATE-----"):
                    print(f"DEBUG: SSL certificate loaded from {cert_path}")
                else:
                    print(f"DEBUG: Invalid certificate format at {cert_path}")
        except Exception as e:
            print(f"DEBUG: Failed to read certificate: {e}")
    else:
        print(f"DEBUG: Certificate file not found at {cert_path}")
        # List what's actually in the directory
        try:
            meipass_path = Path(sys._MEIPASS)
            print(f"DEBUG: Contents of {meipass_path}:")
            for item in meipass_path.iterdir():
                print(f"  - {item}")
        except Exception as e:
            print(f"DEBUG: Failed to list directory: {e}")

        # Fallback: disable SSL verification if certificates can't be found
        print("DEBUG: Disabling SSL verification as fallback")
        os.environ["PYTHONHTTPSVERIFY"] = "0"
        import ssl

        ssl._create_default_https_context = ssl._create_unverified_context

# Add src to path so we can import prompt_mapper
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

from prompt_mapper.cli.main import main

if __name__ == "__main__":
    main()
