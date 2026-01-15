# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for NLMap V3 Taxonomy Matcher

Build with: pyinstaller NLMap_V3.spec --noconfirm
Or use: build.bat

Output: dist/NLMap_V3/ folder containing exe and data files
"""

import os
from pathlib import Path

# Get the project root directory
project_root = Path(SPECPATH)

# Collect all country data folders
country_data = []
countries_dir = project_root / 'countries'
if countries_dir.exists():
    for country_folder in countries_dir.iterdir():
        if country_folder.is_dir():
            # Add each country's folder
            country_data.append((str(country_folder), f'countries/{country_folder.name}'))

block_cipher = None

a = Analysis(
    ['taxonomy_matcher_gui.py'],
    pathex=[str(project_root)],
    binaries=[],
    datas=[
        # Config file - will be copied to dist folder
        ('config.yaml', '.'),
        # Country data folders (synonyms, etc.)
        *country_data,
    ],
    hiddenimports=[
        'fuzzywuzzy',
        'Levenshtein',
        'openpyxl',
        'yaml',
        'tkinter',
        'tkinter.ttk',
        'tkinter.filedialog',
        'tkinter.messagebox',
        'tkinter.scrolledtext',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='NLMap_V3',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # No console window (GUI app)
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='NLMap_V3',
)
