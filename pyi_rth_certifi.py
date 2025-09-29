"""
PyInstaller runtime hook - disable SSL verification.
Aggressive approach to ensure SSL is completely disabled.
"""

import os
import ssl

# Disable SSL verification globally in every possible way
os.environ["PYTHONHTTPSVERIFY"] = "0"
os.environ["CURL_CA_BUNDLE"] = ""
os.environ["REQUESTS_CA_BUNDLE"] = ""

# Override SSL context creation
ssl._create_default_https_context = ssl._create_unverified_context


# Also override the default context directly
def create_unverified_context(*args, **kwargs):
    context = ssl.create_default_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    return context


ssl.create_default_context = create_unverified_context
