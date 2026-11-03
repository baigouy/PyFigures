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

setuptools.setup(
    name='pyfigures',
    version=__VERSION__,
    author=__AUTHOR__,
    author_email=__EMAIL__,
    description=__DESCRIPTION__,
    long_description=long_description,
    long_description_content_type='text/markdown',
    url=__URL__,
    package_data={'': ['*.md','*.json'], 'pyfigures': ['icons/*.png']},   # window icons
    license='BSD',
    include_package_data=True,
    packages=setuptools.find_packages(),
    classifiers=[
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: BSD License',
        'Operating System :: OS Independent',
    ],
    install_requires=[
        "Markdown",
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
        "pyqt6-plugins",   # Qt image format plugins (qtiff, etc.)
        "pandas",
        # "numba",
        "elasticdeform",
        "roifile",
        "prettytable",
        "pyperclip",
        "QtPy>=2.1.0",
        "Deprecated",
        "Requests",
        "batoolset>=0.2.0",          # 0.2.0: the split, the Qt layer moved to batoolset-gui
        "batoolset-gui>=0.2.0",      # batoolset.drawings / figure / luts / pyqts (Qt layer); inverted LUTs
        "pyautogui",
        "imagecodecs",
        "psutil",
        "python-pptx",     # editable PowerPoint export
        "latex2mathml",    # $…$ label maths -> native PowerPoint equations (MIT)
        "mathml2omml",     # (MIT)
        "pylatexenc",      # $…$ label maths -> Unicode text for Illustrator (MIT)
        "pypdfium2",       # PDF files as panels, rendered as images (Apache/BSD)
    ],
    extras_require={
        'ai': [
            "mcp>=1.0",      # MCP server (Claude Code integration)
        ],
        'video': [
            "av",            # PyAV: reads videos and writes H.264 (bundles ffmpeg; Windows/macOS/Linux)
        ],
        'bioformats': [
            "pyimagej",      # Fiji / Bio-Formats reader for .lif, .czi, .nd2, ... (needs Java)
        ],
        'zarr': [
            "zarr",          # OME-Zarr images, local or from a URL (read over http with requests)
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
        # Tools > Chat sidebar: the separate qtpy-ai-sidecar package (local or
        # API model) docked beside the figure. NB: until qtpy-ai-sidecar is on
        # PyPI, `pip install pyfigures[chat]` / `[all]` needs it installed first
        # (pip install -e path/to/qtpy_ai_sidecar).
        'chat': [
            "mcp>=1.0",
            "qtpy-ai-sidecar",
        ],
        'all': [
            "mcp>=1.0",
            "qtpy-ai-sidecar",
            "av",
            "pyimagej",
            "zarr",
            "pymupdf",
        ],
        # running the test suite (pytest.ini sets a per-test timeout so a stuck
        # modal dialog fails the test instead of hanging the run)
        'test': [
            "pytest",
            "pytest-qt",
            "pytest-timeout",
        ],
    },
    python_requires='>=3.9'  # PyQt6 dropped 3.7/3.8; tested up to 3.12
)