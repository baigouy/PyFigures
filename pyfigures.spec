# -*- mode: python ; coding: utf-8 -*-
import os
import sys
from PyInstaller.utils.hooks import (
    collect_data_files,
    collect_dynamic_libs,
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
datas += collect_data_files('pptx')               # default.pptx template + XML parts
datas += collect_data_files('latex2mathml')       # unimathsymbols.txt ($…$ -> PowerPoint equations)
# the chat sidebar (qtpy-ai-sidecar, a core part of the app): its icons and
# templates, the MCP client/server, and keyring's per-OS key stores (imported
# by entry point, invisible to the analysis)
# PYFIGURES_NO_AI=1: the "PyFigures NoAI" app, without the chat sidebar (its
# name hides the chat and MCP entries, pyfigures.assistant.ai_features_enabled);
# the mcp library stays: PyFigures' own operations are written with it
NO_AI = os.environ.get('PYFIGURES_NO_AI') == '1'
if not NO_AI:
    datas += collect_data_files('qtpy_ai_sidecar')
    datas += collect_data_files('keyring')
datas += collect_data_files('mcp')
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
hiddenimports += collect_submodules('zarr')          # OME-Zarr reading
hiddenimports += collect_submodules('numcodecs')
# pypdfium2 (Apache/BSD): PDF files as panels, rendered as images, with its
# native PDFium library. PyMuPDF (vector PDF panels) is AGPL and is left out
# of the apps (excluded below); pip users can add it with pyfigures[pdf].
hiddenimports += collect_submodules('pypdfium2')
hiddenimports += collect_submodules('pylatexenc')     # imported lazily (Illustrator maths)
hiddenimports += ['latex2mathml.converter', 'mathml2omml']
hiddenimports += collect_submodules('pypdfium2_raw')
if not NO_AI:
    hiddenimports += collect_submodules('qtpy_ai_sidecar')
    hiddenimports += collect_submodules('keyring')        # keyring.backends.Windows / macOS
# not mcp.cli: the `mcp` command line tool, it exits when typer is missing
hiddenimports += collect_submodules('mcp', filter=lambda name: not name.startswith('mcp.cli'))
if sys.platform.startswith('linux') and not NO_AI:
    # Linux key store: the desktop's Secret Service (GNOME Keyring, KWallet) over D-Bus
    hiddenimports += collect_submodules('secretstorage')
    hiddenimports += collect_submodules('jeepney')
hiddenimports += collect_submodules('httpx')
hiddenimports += collect_submodules('platformdirs')
datas += collect_data_files('pypdfium2_raw')         # version.json
binaries = collect_dynamic_libs('pypdfium2_raw')
# PYFIGURES_WEB_CHAT=1: the "PyFigures Web Chat" app, the same program with Qt
# WebEngine bundled (the web chat page docked in the window; about 150-200 MB
# more). Its name makes it open with the web chat (pyfigures/__main__.py).
WEB_CHAT = os.environ.get('PYFIGURES_WEB_CHAT') == '1'
APP_NAME = 'PyFigures Web Chat' if WEB_CHAT else 'PyFigures NoAI' if NO_AI else 'PyFigures'
# which of the three apps this is, written into it (pyfigures.assistant.bundled_app_kind):
# a renamed executable, and the Album / Poster launchers beside it, stay what they are
os.makedirs(os.path.join(SPECPATH, 'build'), exist_ok=True)
with open(os.path.join(SPECPATH, 'build', 'app_kind.txt'), 'w', encoding='utf-8') as _f:
    _f.write('web_chat' if WEB_CHAT else 'no_ai' if NO_AI else 'standard')
datas += [(os.path.join(SPECPATH, 'build', 'app_kind.txt'), 'pyfigures')]
if WEB_CHAT:
    hiddenimports += ['PyQt6.QtWebEngineWidgets', 'PyQt6.QtWebEngineCore', 'PyQt6.QtWebChannel',
                      'PyQt6.QtNetwork', 'qtpy.QtWebEngineWidgets', 'qtpy.QtWebEngineCore']
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
    'markdown',     # import name of the Markdown package
    'deprecated',
    'tqdm',
    'pandas',
]

# ---------------------------------------------------------------------------
# Icons (drawn by packaging/make_icons.py): .ico on Windows, .icns on macOS;
# on Linux the AppImage carries pyfigures/icons/pyfigures.png
# ---------------------------------------------------------------------------
sys.path.insert(0, os.path.abspath('.'))
from pyfigures.version import __VERSION__ as _version      # was a stale literal


def _icon(name):
    ext = {'win32': '.ico', 'darwin': '.icns'}.get(sys.platform)
    return os.path.join('images', 'icons', name + ext) if ext else None

# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------
a = Analysis(
    ['pyfigures/__main__.py'],
    pathex=[],
    binaries=binaries,
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
        'fitz',         # PyMuPDF: AGPL, never bundled
        'pymupdf',
    ] + (['qtpy_ai_sidecar', 'keyring'] if NO_AI else []),
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
    name=APP_NAME,
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
    icon=_icon('pyfigures'),
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
    if sys.platform != 'win32' or WEB_CHAT:     # the web chat app is the figure editor only
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
        icon=_icon(_launcher.lower().replace(' ', '_')),   # pyfigures_album / pyfigures_poster
    ))
if sys.platform == 'win32' and not NO_AI:
    # the chat sidebar's MCP server (PyFigures --live-mcp) talks over stdio, which
    # a windowed exe does not have: a console twin, started hidden by the MCP client
    extra_exes.append(EXE(
        pyz,
        a.scripts,
        [],
        exclude_binaries=True,
        name='PyFigures MCP',
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=True,
        console=True,
        disable_windowed_traceback=False,
        argv_emulation=False,
        target_arch=None,
        codesign_identity=None,
        entitlements_file=None,
        icon=_icon('pyfigures'),
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
    name=APP_NAME,
)

# ---------------------------------------------------------------------------
# macOS .app bundle (ignored on other platforms)
# ---------------------------------------------------------------------------
if sys.platform == 'darwin':
    app = BUNDLE(
        coll,
        name=APP_NAME + '.app',
        icon=_icon('pyfigures'),
        bundle_identifier=('com.aigouy.pyfigures.webchat' if WEB_CHAT else
                           'com.aigouy.pyfigures.noai' if NO_AI else 'com.aigouy.pyfigures'),
        info_plist={
            'NSHighResolutionCapable': True,
            'NSRequiresAquaSystemAppearance': False,  # allow dark mode
            'CFBundleShortVersionString': _version,
            'LSBackgroundOnly': False,
        },
    )