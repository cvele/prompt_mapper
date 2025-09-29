# -*- mode: python ; coding: utf-8 -*-

import sys
from pathlib import Path
import certifi

# Get the source directory
src_dir = Path('src')

# Analysis configuration
a = Analysis(
    ['main_entry.py'],
    pathex=[str(src_dir)],
    binaries=[],
    datas=[
        # Include configuration example
        ('config/config.example.yaml', 'config/'),
    ],
    hiddenimports=[
        # Core dependencies
        'prompt_mapper',
        'prompt_mapper.cli',
        'prompt_mapper.config',
        'prompt_mapper.core',
        'prompt_mapper.infrastructure',
        'prompt_mapper.utils',
        # Third-party dependencies that might not be auto-detected
        'aiohttp',
        'aiofiles',
        'click',
        'pydantic',
        'yaml',
        'tenacity',
        'openai',
        'anthropic',
        # Platform-specific imports
        'asyncio',
        'ssl',
        'certifi',
        # SSL certificate handling
        'certifi.core',
        '_ssl',
        'hashlib',
        'hmac',
        # Additional SSL-related modules
        'socket',
        'urllib3.util.ssl_',
        'urllib3.contrib.pyopenssl',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=['pyi_rth_certifi.py'],
    excludes=[
        # Exclude unnecessary modules to reduce size
        'tkinter',
        'matplotlib',
        'numpy',
        'scipy',
        'pandas',
        'PIL',
        'PyQt5',
        'PyQt6',
        'PySide2',
        'PySide6',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
    noarchive=False,
)

# Remove duplicate entries
pyz = PYZ(a.pure, a.zipped_data, cipher=None)

# Executable configuration
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='prompt-mapper',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,  # Add icon path here if you have one
)
