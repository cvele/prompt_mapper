"""Prompt-Based Movie Mapper.

A tool for matching local movie files with canonical metadata using
natural language prompts and integrating with Radarr for automated
library management.
"""

try:
    # Try to get version from setuptools_scm (when installed from git)
    from ._version import version as __version__
except ImportError:
    # Fallback: try setuptools_scm directly
    try:
        from setuptools_scm import get_version

        __version__ = get_version(root="../..", relative_to=__file__)
    except ImportError:
        # Final fallback for development
        __version__ = "0.1.0-dev"

__author__ = "Vladimir Cvetic"
__email__ = "vladimir@cvetic.in.rs"
