"""
PyInstaller runtime hook - disable SSL verification without ssl module.
"""

import os

# Just set environment variables to disable SSL verification
os.environ["PYTHONHTTPSVERIFY"] = "0"
os.environ["REQUESTS_CA_BUNDLE"] = ""
os.environ["CURL_CA_BUNDLE"] = ""
