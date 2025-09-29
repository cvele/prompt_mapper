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
                # Set environment variables for various SSL libraries
                os.environ["SSL_CERT_FILE"] = str(cert_path)
                os.environ["REQUESTS_CA_BUNDLE"] = str(cert_path)
                os.environ["CURL_CA_BUNDLE"] = str(cert_path)

                # For aiohttp specifically - set the CA bundle path
                import ssl

                import certifi

                # Monkey patch certifi to use our bundled certificates
                certifi.where = lambda: str(cert_path)

                # Create a proper SSL context without overriding the default context creator
                # This avoids ASN1 parsing issues
                try:
                    # Test that the certificate file is valid
                    ssl.create_default_context(cafile=str(cert_path))
                except Exception:
                    # If bundled certs are invalid, fall back to system certs
                    pass
            else:
                # Fallback: try to use system certificates or certifi's default
                try:
                    import certifi

                    os.environ["SSL_CERT_FILE"] = certifi.where()
                    os.environ["REQUESTS_CA_BUNDLE"] = certifi.where()
                except ImportError:
                    pass
        else:
            # Not a frozen app, use certifi's default
            try:
                import certifi

                os.environ["SSL_CERT_FILE"] = certifi.where()
                os.environ["REQUESTS_CA_BUNDLE"] = certifi.where()
            except ImportError:
                pass
    except Exception:
        # Fallback to system certificates if anything fails
        # Remove any problematic environment variables
        for env_var in ["SSL_CERT_FILE", "REQUESTS_CA_BUNDLE", "CURL_CA_BUNDLE"]:
            os.environ.pop(env_var, None)


# Configure SSL certificates when the module is imported
_configure_ssl_certificates()
