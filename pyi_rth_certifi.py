"""
PyInstaller runtime hook - disable SSL verification completely.
"""

import os
import ssl

# Just disable SSL verification, nothing else
os.environ["PYTHONHTTPSVERIFY"] = "0"
ssl._create_default_https_context = ssl._create_unverified_context
