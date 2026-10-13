# Licensing of PyFigures — how it works and why

A plain-language summary of the licensing choices for PyFigures, kept so the
reasoning does not have to be worked out again. It is a reading of the
licences, not legal advice.

## The short version

| What is distributed | Licence | Why |
|---|---|---|
| PyFigures' own source code (GitHub, PyPI) | **BSD 2-Clause** | It is your code; you choose its licence. |
| `pip install pyfigures` | **BSD 2-Clause** | You distribute only your code. pip installs the dependencies (PyQt6, PyMuPDF, ...) on the user's machine, each under its own licence. |
| The standalone apps (Windows / macOS executables) | **GNU GPL v3** as a whole | They *contain* GPL code (PyQt6, read-lif, pyqt6-plugins, FFmpeg built with x264/x265). Distributing a combined work that includes GPL code means distributing the whole under the GPL. |
| PyMuPDF / MuPDF inside the apps | **GNU AGPL v3** (keeps its own licence) | GPL v3 section 13 (and the same section of the AGPL v3) explicitly allows combining the two; each part keeps its terms. |

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

## What PyMuPDF does here

PyMuPDF (AGPL v3, or a paid commercial licence from Artifex) has one job in
PyFigures: it converts a PDF dropped onto the canvas into SVG so the PDF
becomes a **vector panel** (`pdf_to_svg_bytes` in
`batoolset/drawings/shapes/image2d.py`; drawn by
`batoolset/drawings/pdf_svg_renderer.py`). Nothing else depends on it.
Permissive alternatives (pypdfium2) can only rasterise PDFs, which defeats the
point; Poppler is GPL and would need an external program.

- With pip it is optional: `pip install pyfigures[pdf]`. Without it, PDF
  panels are unavailable and everything else works.
- The standalone apps bundle it (`pyfigures.spec`, CI installs
  `.[video,zarr,pdf]`).

The AGPL's extra clause concerns software that users interact with **over a
network**: whoever runs a *modified* version as a network service must offer
its source to those users. A desktop application is not affected.

## What the standalone apps must provide (and already do)

1. **The licence texts and notices** of everything inside the bundle:
   `THIRD_PARTY_LICENSES.txt`, shown by *Help → About → Third-party licences*
   (GPL v3, AGPL v3, LGPL v3, GPL v2, LGPL v2.1 texts included).
2. **The complete corresponding source code** of every bundled component,
   offered from the same place as the executables (GPL v3 section 6(d)):
   `corresponding-source-*.tar` attached to the GitHub release. PyMuPDF's
   source archive on PyPI contains the MuPDF source; Qt's and FFmpeg's sources
   are fetched from their own releases.
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
  PyQt6, an LGPL-only FFmpeg build (no x264/x265), and no PyMuPDF (or
  Artifex's commercial licence).
