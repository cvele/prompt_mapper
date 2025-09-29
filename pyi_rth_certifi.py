"""
PyInstaller runtime hook for SSL certificates.
Simple approach: Set REQUESTS_CA_BUNDLE to point to bundled certificates.
"""

import os
import sys
from pathlib import Path

# Configure SSL certificates for PyInstaller frozen app
if hasattr(sys, "_MEIPASS"):
    # PyInstaller frozen app - point to bundled certificates
    cert_path = Path(sys._MEIPASS) / "certifi" / "cacert.pem"
    if cert_path.exists():
        os.environ["REQUESTS_CA_BUNDLE"] = str(cert_path)
        os.environ["SSL_CERT_FILE"] = str(cert_path)
