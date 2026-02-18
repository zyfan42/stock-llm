# -*- mode: python ; coding: utf-8 -*-
import sys
import os
from PyInstaller.utils.hooks import copy_metadata, collect_data_files, collect_submodules, collect_all

# -----------------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------------
MAIN_SCRIPT = '../app/main.py'
APP_NAME = 'StockLLM'
ICON_PATH = '../assets/icon.ico'

# -----------------------------------------------------------------------------
# Hidden Imports & Datas
# -----------------------------------------------------------------------------
binaries = []
datas = []

hiddenimports = [
    'streamlit',
    'streamlit.web.cli',
    'streamlit.runtime.scriptrunner.magic_funcs',
    'engineio.async_drivers.threading', 
    'pywebview',
    'webview',
    'webview.platforms.winforms',
    'plotly',
    'altair',
    'pydeck',
    'pandas',
    'numpy',
    'requests',
    'toml',
    'dotenv',
    'watchdog',
    'sklearn', # Often needed by some streamlit dependencies
    'baostock',
]

hiddenimports += collect_submodules('app')
hiddenimports += collect_submodules('data')
hiddenimports += collect_submodules('llm')
hiddenimports += collect_submodules('utils')
hiddenimports += collect_submodules('baostock')

# Broader collection for dynamic/plug-in style packages
for pkg_name in [
    'streamlit',
    'plotly',
    'pydeck',
    'altair',
    'pandas',
    'numpy',
    'requests',
    'toml',
    'dotenv',
    'watchdog',
    'openai',
    'ta',
    'pywebview',
    'webview',
    'baostock',
]:
    pkg_datas, pkg_bins, pkg_hidden = collect_all(pkg_name)
    datas += pkg_datas
    binaries += pkg_bins
    hiddenimports += pkg_hidden

def safe_copy_metadata(package_name):
    """Safely copy metadata for a package if it exists"""
    try:
        return copy_metadata(package_name)
    except Exception:
        return []

# Collect Streamlit data
datas += collect_data_files('streamlit')
datas += safe_copy_metadata('streamlit')
datas += safe_copy_metadata('plotly')
datas += safe_copy_metadata('tqdm')
datas += safe_copy_metadata('regex')
datas += safe_copy_metadata('requests')
datas += safe_copy_metadata('packaging')
datas += safe_copy_metadata('filelock')
datas += safe_copy_metadata('numpy')
datas += safe_copy_metadata('tokenizers')
datas += safe_copy_metadata('baostock')

# Project specific datas
# Format: (source_path, dest_folder)
datas += [
    ('../app', 'app'),
    ('../webui', 'webui'),
    ('../assets', 'assets'),
    ('../data', 'data'),
    ('../llm', 'llm'),
    ('../utils', 'utils'),
    ('../config.example.toml', '.'),
    ('../.env.example', '.'),
]

# -----------------------------------------------------------------------------
# Analysis
# -----------------------------------------------------------------------------
block_cipher = None

a = Analysis(
    [MAIN_SCRIPT],
    pathex=['..'], # Add root to path so it can find app, data, utils, llm
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
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
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name=APP_NAME,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=ICON_PATH,
)

