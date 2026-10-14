# Licensing of PyFigures — how it works and why

A plain-language summary of the licensing choices for PyFigures, kept so the
reasoning does not have to be worked out again. It is a reading of the
licences, not legal advice.

## The short version

| What is distributed | Licence | Why |
|---|---|---|
| PyFigures' own source code (GitHub, PyPI) | **BSD 2-Clause** | It is your code; you choose its licence. |
| `pip install pyfigures` | **BSD 2-Clause** | You distribute only your code. pip installs the dependencies (PyQt6, pypdfium2, optionally PyMuPDF, ...) on the user's machine, each under its own licence. |
| The standalone apps (Windows / macOS executables) | **GNU GPL v3** as a whole | They *contain* GPL code (PyQt6, read-lif, pyqt6-plugins, FFmpeg built with x264/x265). Distributing a combined work that includes GPL code means distributing the whole under the GPL. |
| PyMuPDF | not in the apps | AGPL v3; pip-only optional extra (`pyfigures[pdf]`). The apps read PDFs with pypdfium2 (Apache/BSD) instead. |
| LaTeX (TinyTeX / TeX Live) | not in the apps | Downloaded on request (*Help → Install LaTeX for PyFigures…*, the MCP tool `install_latex`) from TinyTeX's own releases into the user's folder; the user receives it from TinyTeX/TeX Live under their licences (GPL, LPPL and others), so PyFigures distributes none of it and has no source to provide for it. Bundling it would add ~400 MB and TeX Live's source to every release. |

As the copyright holder you can license your own code differently in different
forms: it is BSD everywhere, and only the *combined* executable has to follow
the copyleft licences of what is bundled in it.

## Licence compatibility in one paragraph

Permissive licences (BSD, MIT, Apache) can flow *into* copyleft projects:
BSD code may be included in a GPL or AGPL program, and that program is then
distributed under the GPL/AGPL. The reverse is not possible: GPL/AGPL code
cannot be included in something you distribute under BSD. The GPL v3 and the
AGPL v3 are compatible with each other through their section 13. The LGPL
(used by Qt) only asks that the library can be replaced, which dynamic linking
satisfies.

## PDF panels: PyMuPDF or pypdfium2

Reading a PDF dropped onto the canvas is the only thing either library does
(`pdf_to_svg_bytes` in `batoolset/drawings/shapes/image2d.py`; page counts in
`pdf_page_count`, `batoolset/img.py`). Nothing else depends on them.

- **PyMuPDF** (AGPL v3, or a paid commercial licence from Artifex) converts
  the page to SVG, so the PDF stays a **vector panel** (drawn by
  `batoolset/drawings/pdf_svg_renderer.py`). Optional with pip:
  `pip install pyfigures[pdf]`. Used whenever it is installed.
- **pypdfium2** (Apache 2.0 / BSD-3, Google's PDFium) is a normal dependency.
  Without PyMuPDF the page is rendered as an image at 600 dpi (at most 25
  megapixels per page) and placed like a vector panel. Sharp in print, but
  not vector.
- **The standalone apps** bundle pypdfium2 and exclude PyMuPDF
  (`pyfigures.spec`, CI installs `.[video,zarr]`), so no AGPL code is in them.
  Decided 2026-10-14 to keep the apps' licence story to GPL v3 only.

The AGPL's extra clause concerns software that users interact with **over a
network**: whoever runs a *modified* version as a network service must offer
its source to those users. A desktop application is not affected, so bundling
PyMuPDF would have been legal (GPL v3 section 13); it was left out for
simplicity.

## omero-py (raw pixels from OMERO)

`pip install pyfigures[omero]` adds omero-py (**GPL v2 or later**) and its
network library zeroc-ice (Ice, ZeroC's **GPL v2** or commercial licence), for
raw 16-bit / float reads from OMERO servers. It is a pip-only optional extra
and is **not** bundled in the standalone apps: Ice has no PyPI wheel for
Windows, and, as ZeroC licenses Ice under the GPL v2 *only* (not "or later"),
it cannot be combined with the apps' GPL v3 components. omero-py itself would
be fine (v2 or later includes v3). Without them,
OMERO images are read through OMERO.web (256 levels per channel), which needs
nothing extra.

## What the standalone apps must provide (and already do)

1. **The licence texts and notices** of everything inside the bundle:
   `THIRD_PARTY_LICENSES.txt`, shown by *Help → About → Third-party licences*
   (GPL v3, LGPL v3, GPL v2, LGPL v2.1 texts included, and the AGPL v3 if an
   AGPL component were ever bundled).
2. **The complete corresponding source code** of every bundled component,
   offered from the same place as the executables (GPL v3 section 6(d)):
   `corresponding-source-*.tar` attached to the GitHub release. Qt's and
   FFmpeg's sources are fetched from their own releases.
3. **No extra restrictions** on users (no licence keys, no "non-commercial"
   clause on the executables).

All three are produced automatically by `packaging/collect_licenses.py` when
the executables are built (`.github/workflows/build.yml`), and checked by
`tests/test_licensing.py`.

## Things to keep in mind

- **Adding a dependency to the apps**: if it is GPL/AGPL, the apps stay GPL v3
  (nothing changes as long as `collect_licenses.py` finds its licence and
  source). If its metadata states no licence, add it to `KNOWN_LICENSES` in
  `collect_licenses.py`.
- **Never** add a GPL/AGPL library as a hard requirement of the pip package if
  you want users to be able to use PyFigures under BSD terms alone; keep such
  libraries optional extras (as with PyMuPDF), or accept that PyQt6 already
  makes most real installations GPL-combined anyway.
- **Commercial redistribution** of the apps by someone else is allowed under
  the GPL as long as they pass on the same rights (source + licence). They
  cannot make it closed source.
- **If you ever want a non-GPL app**: you would need PySide6 (LGPL) instead of
  PyQt6 and an LGPL-only FFmpeg build (no x264/x265). PDF reading is already
  permissive (pypdfium2).
