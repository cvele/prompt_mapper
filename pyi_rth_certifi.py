"""
PyInstaller runtime hook - disable SSL verification.
Simple and reliable approach.
"""

import os
import ssl

# Disable SSL verification globally
os.environ["PYTHONHTTPSVERIFY"] = "0"
ssl._create_default_https_context = ssl._create_unverified_context
