import setuptools
import os
from pyfigures.version import __VERSION__, __EMAIL__, __AUTHOR__, __DESCRIPTION__, __URL__

# def read_requirements(filename):
#     with open(filename, 'r') as f:
#         requirements = [line.strip() for line in f.readlines()]
#     return requirements
#
# # Read requirements.txt
# requirements = read_requirements(os.path.join(os.path.dirname(__file__), 'requirements.txt'))

with open('README.md', 'r') as fh:
    long_description = fh.read()

# PYFIGURES_NO_AI=1 builds "pyfigures-noai": the same code without the chat
# sidebar package (qtpy-ai-sidecar); PyFigures then hides its chat and MCP
# entries (pyfigures.assistant.ai_features_enabled). The mcp library stays:
# PyFigures' own operations are written with it.
NO_AI = os.environ.get('PYFIGURES_NO_AI') == '1'
# pip building pyfigures-noai from its source archive (no variable set): the
# archive's PKG-INFO says which distribution it is
if os.path.isfile('PKG-INFO'):
    with open('PKG-INFO', encoding='utf-8') as _f:
        NO_AI = NO_AI or any(line.strip() == 'Name: pyfigures-noai' for line in _f)
if NO_AI:
    long_description = ('**PyFigures without AI**: the same program as `pyfigures`, without the chat '
                        'sidebar and with no chat or MCP entries. Install either `pyfigures` or '
                        '`pyfigures-noai`, not both.\n\n' + long_description)


def _requirements(names):
    return [r for r in names if not (NO_AI and r.startswith('qtpy-ai-sidecar'))]


def _extras(extras):
    if NO_AI:
        extras.pop('chat')
        extras = {k: _requirements(v) for k, v in extras.items()}
    return extras


setuptools.setup(
    name='pyfigures-noai' if NO_AI else 'pyfigures',
    version=__VERSION__,
    author=__AUTHOR__,
    author_email=__EMAIL__,
    description=__DESCRIPTION__,
    long_description=long_description,
    long_description_content_type='text/markdown',
    url=__URL__,
    # window icons; gui/fonts is no package: without these patterns the wheel has
    # no fonts folder (fonts_dir missing, fonts dropped in it never shipped)
    package_data={'': ['*.md','*.json'],
                  'pyfigures': ['icons/*.png', 'gui/fonts/*.md', 'gui/fonts/*.ttf', 'gui/fonts/*.otf']},
    license='BSD',
    include_package_data=True,
    # only pyfigures: the repo's images/ folder has an __init__.py and was
    # installed as a top-level "images" package into site-packages
    packages=setuptools.find_packages(include=['pyfigures', 'pyfigures.*']),
    classifiers=[
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: BSD License',
        'Operating System :: OS Independent',
    ],
    install_requires=_requirements([
        "Markdown",
        "PyYAML",          # YAML recipes (on 3.11+ another package happened to bring it)
        "matplotlib>=3.5.2",
        "numpy>=1.24",
        "Pillow>=8.1.2",
        "PyQt6",
        "read-lif",
        "scikit-image>=0.19.3",
        "scipy>=1.7.3",
        "scikit-learn>=1.0.2",
        "tifffile>=2021.11.2",
        "tqdm",
        "natsort",
        "numexpr",
        "urllib3",
        "qtawesome",
        "pandas",
        # "numba",
        "roifile",
        "prettytable",
        "pyperclip",
        "QtPy>=2.1.0",
        "Deprecated",
        "Requests",
        "batoolset>=0.2.0",          # 0.2.0: the split, the Qt layer moved to batoolset-gui
        "batoolset-gui>=0.2.4",      # Qt layer; 0.2.4: "Loading…" placeholder, empty insets no longer hide annotations
        "staplot>=0.1.0",            # data-plot panels and stats brackets (staplot.api)
        "pyautogui",
        "imagecodecs",
        "psutil",
        "python-pptx",     # editable PowerPoint export
        "latex2mathml",    # $…$ label maths -> native PowerPoint equations (MIT)
        "mathml2omml",     # (MIT)
        "pylatexenc",      # $…$ label maths -> Unicode text for Illustrator (MIT)
        "pypdfium2",       # PDF files as panels, rendered as images (Apache/BSD)
        # the chat sidebar (Tools > Chat sidebar, a core part of PyFigures): a
        # local or API model edits the open figure through the MCP tools (BSD-2)
        "qtpy-ai-sidecar>=0.1.4",
        "mcp>=1.12,<2",    # MCP server (Claude, LM Studio…) and the sidebar's client; mcp 2 renamed FastMCP
    ]),
    extras_require=_extras({
        'ai': [
            "mcp>=1.12,<2",  # installed by default since 0.2.1; kept for older instructions
        ],
        'video': [
            "av",            # PyAV: reads videos and writes H.264 (bundles ffmpeg; Windows/macOS/Linux)
            "opencv-python-headless",   # batoolset's mp4/avi/mkv stacks (cv2)
        ],
        'fiji': [
            "pyimagej",      # Fiji / Bio-Formats reader for .lif, .czi, .nd2, ... (needs Java)
        ],
        # zarr 3 needs Python 3.11+; zarr 2 (all Python 3.10 gets) can't read them here
        'zarr': [
            "zarr>=3; python_version >= '3.11'",   # OME-Zarr images, local or from a URL (read over http with requests)
        ],
        'pdf': [
            "pymupdf",       # PDF files as vector panels (AGPL v3; not in the standalone apps)
        ],
        # raw (16-bit) pixels from OMERO; without it OMERO images are read
        # through OMERO.web with 256 levels per channel. Left out of the "all"
        # extra: it needs zeroc-ice, which has no PyPI wheel for Windows (README).
        'omero': [
            "omero-py",
        ],
        # the chat sidebar is installed by default since 0.2.1; kept so that
        # `pip install pyfigures[chat]` from older instructions still works
        'chat': [
            "mcp>=1.12,<2",
            "qtpy-ai-sidecar>=0.1.4",
        ],
        'all': [
            "mcp>=1.12,<2",
            "qtpy-ai-sidecar>=0.1.4",
            "av",
            "opencv-python-headless",
            "pyimagej",
            "zarr>=3; python_version >= '3.11'",
            "pymupdf",
        ],
        # running the test suite (pytest.ini sets a per-test timeout so a stuck
        # modal dialog fails the test instead of hanging the run)
        'test': [
            "pytest",
            "pytest-qt",
            "pytest-timeout",
        ],
    }),
    python_requires='>=3.10'  # staplot needs 3.10+; no upper cap
)