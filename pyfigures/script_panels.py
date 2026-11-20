"""Panels drawn by Python code (add_scripted_image, set_script, a recipe's ``script:``):
what such a script must do, and a check that runs it as PyFigures does.

The contract (docs/SCRIPT_PANELS.md has it in full, for a person or a coding agent
writing a script for a plot PyFigures has no tool for, e.g. a phylogenetic tree):

* the script is plain Python; ``plt`` (matplotlib.pyplot), ``np`` (numpy), ``self`` (the
  panel) and ``file_path`` (the panel's linked file, or None) are already defined;
* it ends by setting ``self.img`` to ONE of:
    - a matplotlib ``Figure`` (best: vector in the PDF / SVG export, its text follows the
      figure's font and size settings, title / axis labels / ticks / legend each
      adjustable);
    - a NumPy image (H x W grey or H x W x 3 RGB, uint8): pixels, for a rendered image;
    - the path of an SVG or PDF file it wrote (a vector drawing from another tool);
* it reads its data from ``file_path`` or an absolute path; it never calls ``plt.show()``.

Check a script outside PyFigures::

    python -m pyfigures.script_panels tree_panel.py [data_file]
"""
from __future__ import annotations

import os
import sys

CONTRACT = __doc__.split("Check a script")[0].strip()


def check_script(script: str, file_path: str | None = None) -> dict:
    """Run *script* as PyFigures runs a panel's script. Returns {'ok', 'kind' ('figure' |
    'image' | 'file'), 'size' ('w x h in' or 'w x h px'), 'error', 'log'}."""
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    import matplotlib.pyplot as plt
    import numpy as np
    try:
        compile(script, "<panel script>", "exec")
    except SyntaxError as e:
        return {"ok": False, "error": f"syntax error line {e.lineno}: {e.msg}", "log": ""}
    from batoolset.drawings.shapes.image2d import Image2D
    try:
        panel = Image2D(custom_loading_script=script, filename=file_path)
    except Exception as e:                       # the panel itself could not be built
        return {"ok": False, "error": f"{type(e).__name__}: {e}", "log": ""}
    log = (getattr(panel, "script_log", "") or "").strip()
    img = panel.img
    out = {"ok": True, "log": log}
    if isinstance(img, plt.Figure):
        w, h = img.get_size_inches()
        out.update(kind="figure", size=f"{w:.2f} x {h:.2f} in")
    elif isinstance(img, np.ndarray):
        out.update(kind="image", size=f"{img.shape[1]} x {img.shape[0]} px")
    elif isinstance(img, str) and os.path.isfile(img):
        out.update(kind="file", size=os.path.basename(img))
    else:
        err = next((ln for ln in reversed(log.splitlines()) if "Error" in ln or "error" in ln), "")
        out.update(ok=False, error=(err or "the script did not set self.img to a matplotlib Figure, "
                                     "a NumPy image or the path of an SVG / PDF file"))
    return out


def failure_message(report: dict) -> str:
    """One line for a tool's ERROR: what failed, and the end of the script's log."""
    tail = "\n".join((report.get("log") or "").splitlines()[-6:])
    return report.get("error", "the script failed") + (f"\n{tail}" if tail else "")


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    with open(argv[0], encoding="utf-8") as f:
        script = f.read()
    report = check_script(script, argv[1] if len(argv) > 1 else None)
    if report["ok"]:
        print(f"OK: the panel is {report['kind']} ({report['size']}).")
        if report.get("log"):
            print("Its output:\n" + report["log"])
        return 0
    print("FAILED: " + failure_message(report))
    print("\n" + CONTRACT)
    return 1


if __name__ == "__main__":
    sys.exit(main())
