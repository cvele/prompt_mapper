#!/usr/bin/env python3
"""Setup script for Prompt-Based Movie Mapper."""

import os

from setuptools import find_packages, setup

# Read the contents of README file
this_directory = os.path.abspath(os.path.dirname(__file__))
with open(os.path.join(this_directory, "README.md"), encoding="utf-8") as f:
    long_description = f.read()

setup(
    name="prompt-movie-mapper",
    version="0.1.0",
    author="Prompt Movie Mapper Team",
    description="Prompt-driven movie file matching and Radarr integration",
    long_description=long_description,
    long_description_content_type="text/markdown",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    python_requires=">=3.8",
    install_requires=[
        "pyyaml>=6.0",
        "requests>=2.28.0",
        "click>=8.0.0",
        "pydantic>=1.10.0",
        "python-dotenv>=0.19.0",
        "aiohttp>=3.8.0",
        "aiofiles>=22.0.0",
        "tenacity>=8.0.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "pytest-asyncio>=0.21.0",
            "pytest-cov>=4.0.0",
            "black>=22.0.0",
            "isort>=5.10.0",
            "flake8>=5.0.0",
            "mypy>=0.991",
            "pre-commit>=2.20.0",
        ],
        "openai": ["openai>=1.0.0"],
        "anthropic": ["anthropic>=0.7.0"],
    },
    entry_points={
        "console_scripts": [
            "prompt-mapper=prompt_mapper.cli:main",
        ],
    },
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: End Users/Desktop",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Topic :: Multimedia :: Video",
        "Topic :: System :: Archiving",
    ],
)
