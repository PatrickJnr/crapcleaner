# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec file for CrapCleaner.

Bundles the application into a fast, standalone, and reliable binary
including all crapcleaner subpackages and required Qt/PySide6 runtime modules.
"""

import sys
import os
from PyInstaller.utils.hooks import collect_all

block_cipher = None

# Base repository directory
ROOT_DIR = os.path.abspath(SPECPATH)

# Collect all crapcleaner modules, categories, analyzers, and package data
crap_datas, crap_binaries, crap_hiddenimports = collect_all('crapcleaner')

datas = [
    (os.path.join(ROOT_DIR, 'crapcleaner', 'assets'), 'crapcleaner/assets'),
] + crap_datas

binaries = crap_binaries

hiddenimports = list(
    set(
        [
            'crapcleaner',
            'crapcleaner.app',
            'crapcleaner.constants',
            'crapcleaner.config',
            'crapcleaner.history',
            'crapcleaner.registry',
            'crapcleaner.reports',
            'crapcleaner.cli',
            'crapcleaner.analysis',
            'crapcleaner.categories',
            'crapcleaner.core',
            'crapcleaner.gui',
            'crapcleaner.gui.app',
            'crapcleaner.gui.dialogs',
            'crapcleaner.gui.icons',
            'crapcleaner.gui.sidebar',
            'crapcleaner.gui.theme',
            'crapcleaner.gui.theme_picker',
            'crapcleaner.gui.views',
            'crapcleaner.gui.workers',
            'crapcleaner.models',
            'crapcleaner.system',
            'crapcleaner.utils',
            'crapcleaner.utils.contributors',
            'crapcleaner.utils.formatting',
            'crapcleaner.utils.recycle_bin',
            'crapcleaner.utils.theme_watcher',
            'crapcleaner.utils.updater',
            'PySide6.QtCore',
            'PySide6.QtGui',
            'PySide6.QtWidgets',
            'PySide6.QtSvg',
            'PySide6.QtSvgWidgets',
            'PySide6.QtNetwork',
        ]
        + crap_hiddenimports
    )
)

excludes = [
    'tkinter',
    'unittest',
    'pydoc',
    'PySide6.QtWebEngineCore',
    'PySide6.QtWebEngineWidgets',
    'PySide6.Qt3DCore',
    'PySide6.Qt3DRender',
    'PySide6.Qt3DInput',
    'PySide6.Qt3DExtras',
    'PySide6.QtQuick',
    'PySide6.QtQuickWidgets',
    'PySide6.QtQml',
    'PySide6.QtDesigner',
    'PySide6.QtMultimedia',
    'PySide6.QtBluetooth',
    'PySide6.QtSensors',
    'PySide6.QtSpatialAudio',
    'PySide6.QtGraphs',
    'PySide6.QtGraphsWidgets',
]

a = Analysis(
    ['scripts/launcher.py'],
    pathex=[ROOT_DIR],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe_name = 'CrapCleaner' if sys.platform.startswith('win') else 'crapcleaner-linux-x86_64'

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name=exe_name,
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
)
