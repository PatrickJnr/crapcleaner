# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec file for CrapCleaner.

Bundles the application into a fast, standalone, and reliable binary
including all crapcleaner subpackages and required Qt/PySide6 runtime modules.
"""

import sys
import os
from PyInstaller.utils.hooks import collect_all

# Base repository directory
ROOT_DIR = os.path.abspath(SPECPATH)

sys.path.insert(0, ROOT_DIR)
from crapcleaner.constants import VERSION  # noqa: E402
from scripts.version_info import write as write_version_info  # noqa: E402

IS_WINDOWS = sys.platform.startswith('win')

# The icon is committed rather than rendered here, so a build needs no Qt and the
# icon in a release is the one that was reviewed. Regenerate with scripts/make_icon.py.
ICON_PATH = os.path.join(ROOT_DIR, 'crapcleaner', 'assets', 'crapcleaner.ico')
ICON = ICON_PATH if IS_WINDOWS and os.path.isfile(ICON_PATH) else None

# Version metadata is generated from crapcleaner.constants so it cannot drift from
# the version the application reports.
VERSION_FILE = None
if IS_WINDOWS:
    VERSION_FILE = write_version_info(
        os.path.join(ROOT_DIR, 'build', 'file_version_info.txt'), VERSION
    )

# Collect all crapcleaner modules, categories, analyzers, and package data
crap_datas, crap_binaries, crap_hiddenimports = collect_all('crapcleaner')

datas = [
    (os.path.join(ROOT_DIR, 'crapcleaner', 'assets'), 'crapcleaner/assets'),
] + crap_datas

# scripts/ is a build-time helper, not application code: it must not be bundled.

binaries = crap_binaries

hiddenimports = list(
    set(
        [
            'crapcleaner',
            'crapcleaner.constants',
            'crapcleaner.config',
            'crapcleaner.history',
            'crapcleaner.registry',
            'crapcleaner.reports',
            'crapcleaner.cli',
            'crapcleaner.analysis',
            'crapcleaner.analysis.recycle_bin',
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
            'crapcleaner.utils.format',
            'crapcleaner.utils.files',
            'crapcleaner.utils.platform',
            'crapcleaner.utils.updater',
            'crapcleaner.utils.windows_errors',
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
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data)

exe_name = 'CrapCleaner' if sys.platform.startswith('win') else 'crapcleaner-linux-x86_64'

# onefile by default; the build scripts set this to 'onedir' for a folder build,
# which starts noticeably faster because nothing is unpacked at launch.
ONEDIR = os.environ.get('CRAPCLEANER_BUILD_MODE', 'onefile').strip().lower() == 'onedir'

if ONEDIR:
    exe = EXE(
        pyz,
        a.scripts,
        [],
        exclude_binaries=True,
        name=exe_name,
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=False,
        console=False,
        disable_windowed_traceback=False,
        argv_emulation=False,
        target_arch=None,
        codesign_identity=None,
        entitlements_file=None,
        icon=ICON,
        version=VERSION_FILE,
    )
    coll = COLLECT(
        exe,
        a.binaries,
        a.zipfiles,
        a.datas,
        strip=False,
        upx=False,
        name=exe_name,
    )
else:
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
        upx=False,
        runtime_tmpdir=None,
        console=False,
        disable_windowed_traceback=False,
        argv_emulation=False,
        target_arch=None,
        codesign_identity=None,
        entitlements_file=None,
        icon=ICON,
        version=VERSION_FILE,
    )
