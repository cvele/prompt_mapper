"""
PyInstaller runtime hook for certifi SSL certificates.
This ensures SSL certificates are properly configured in the frozen application.
"""

import os
import sys
from pathlib import Path


def _configure_ssl_certificates():
    """Configure SSL certificates for the frozen application."""
    try:
        # Get the path to the bundled certificates
        if hasattr(sys, "_MEIPASS"):
            # PyInstaller frozen app
            cert_path = Path(sys._MEIPASS) / "certifi" / "cacert.pem"
            if cert_path.exists():
                os.environ["SSL_CERT_FILE"] = str(cert_path)
                os.environ["REQUESTS_CA_BUNDLE"] = str(cert_path)
                # For aiohttp and other libraries
                import ssl

                ssl._create_default_https_context = ssl._create_unverified_context
                # Override with proper context using our certs
                context = ssl.create_default_context(cafile=str(cert_path))
                ssl._create_default_https_context = lambda: context
    except Exception:
        # Fallback to system certificates if bundled ones fail
        pass


# Configure SSL certificates when the module is imported
_configure_ssl_certificates()
