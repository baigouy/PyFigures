# -*- mode: python ; coding: utf-8 -*-
import sys
from PyInstaller.utils.hooks import (
    collect_data_files,
    collect_submodules,
)

# ---------------------------------------------------------------------------
# Data files
# ---------------------------------------------------------------------------
datas = []
datas += collect_data_files('pyfigures')
datas += collect_data_files('batoolset')
datas += collect_data_files('qtawesome')          # icon font files
datas += collect_data_files('matplotlib')
datas += collect_data_files('skimage')
datas += collect_data_files('sklearn')
# Licence texts + where the corresponding source is (GPLv3: the bundle includes
# PyQt6, Qt and FFmpeg/x264); made by packaging/collect_licenses.py, shown by
# Help > About
import os
for _f in ('THIRD_PARTY_LICENSES.txt', 'SOURCES.md'):
    if os.path.isfile(os.path.join('third_party', _f)):
        datas.append((os.path.join('third_party', _f), 'third_party'))
    else:
        raise SystemExit('run "python packaging/collect_licenses.py notices third_party" first')

# ---------------------------------------------------------------------------
# Hidden imports that PyInstaller cannot detect automatically
# ---------------------------------------------------------------------------
hiddenimports = []
hiddenimports += collect_submodules('pyfigures')
hiddenimports += collect_submodules('batoolset')
hiddenimports += collect_submodules('sklearn')
hiddenimports += collect_submodules('scipy')
hiddenimports += collect_submodules('scipy.special')
# hiddenimports += collect_submodules('numba')
hiddenimports += collect_submodules('numexpr')
hiddenimports += collect_submodules('imagecodecs')
# PyAV (pyfigures[video]): H.264 export that plays on a Mac + video reading;
# the frozen app cannot pip install it later, so it must be bundled here
hiddenimports += collect_submodules('av')
hiddenimports += [
    # PyQt6 / Qt
    'PyQt6',
    'PyQt6.QtCore',
    'PyQt6.QtGui',
    'PyQt6.QtWidgets',
    'PyQt6.QtPrintSupport',
    'PyQt6.QtSvg',
    'PyQt6.QtXml',
    'PyQt6.QtOpenGL',
    'PyQt6.sip',
    'qtpy',
    'qtpy.QtCore',
    'qtpy.QtGui',
    'qtpy.QtWidgets',
    'qtawesome',
    # Scientific / image
    'PIL._imaging',
    'PIL.Image',
    'tifffile',
    'czifile',
    'roifile',
    'read_lif',
    'elasticdeform',
    # Utilities
    'natsort',
    'prettytable',
    'pyperclip',
    'pyautogui',
    'psutil',
    'requests',
    'urllib3',
    'Markdown',
    'deprecated',
    'tqdm',
    'pandas',
]

# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------
a = Analysis(
    ['pyfigures/__main__.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={
        'matplotlib': {'backends': 'all'},
    },
    runtime_hooks=[],
    excludes=[
        'tkinter',
        '_tkinter',
    ],
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data)

# ---------------------------------------------------------------------------
# Executable
# ---------------------------------------------------------------------------
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='PyFigures',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,          # GUI app — no terminal window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,              # replace with 'images/PyFigures.ico' on Windows
                            #             'images/PyFigures.icns' on macOS
)

# The photo album and poster designers as their own executables: the same
# program under another name (pyfigures/__main__.py opens the album/poster
# designer when its executable name contains "Album"/"Poster"), sharing the
# bundle's libraries. Windows only: on macOS "PyFigures Album.app" and
# "PyFigures Poster.app" are small launchers made by
# packaging/make_macos_launcher_apps.sh that run PyFigures.app --album /
# --poster, so the whole app isn't shipped three times.
extra_exes = []
for _launcher in ('PyFigures Album', 'PyFigures Poster'):
    if sys.platform != 'win32':
        break
    extra_exes.append(EXE(
        pyz,
        a.scripts,
        [],
        exclude_binaries=True,
        name=_launcher,
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=True,
        console=False,
        disable_windowed_traceback=False,
        argv_emulation=False,
        target_arch=None,
        codesign_identity=None,
        entitlements_file=None,
        icon=None,
    ))

# ---------------------------------------------------------------------------
# Collect (one-directory bundle)
# ---------------------------------------------------------------------------
coll = COLLECT(
    exe,
    *extra_exes,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='PyFigures',
)

# ---------------------------------------------------------------------------
# macOS .app bundle (ignored on other platforms)
# ---------------------------------------------------------------------------
if sys.platform == 'darwin':
    app = BUNDLE(
        coll,
        name='PyFigures.app',
        icon=None,          # replace with 'images/PyFigures.icns' when available
        bundle_identifier='com.aigouy.pyfigures',
        info_plist={
            'NSHighResolutionCapable': True,
            'NSRequiresAquaSystemAppearance': False,  # allow dark mode
            'CFBundleShortVersionString': '0.1.11',
            'LSBackgroundOnly': False,
        },
    )