"""Shared machinery of the end-to-end GUI layer (pytest marker ``gui_e2e``).

What the tests in ``test_gui_e2e_*.py`` do with it:

* build real input files (PNG, 8/16-bit TIFF, RGB, Z and time stacks, a
  2-page PDF = a multi-series file, CSV, .pyf, .tex, a short video, ...);
* open a real ``EZFIG_GUI`` on a small figure;
* list EVERY action a user can reach — menu bar, toolbar, the canvas
  right-click menu for each kind of selection, the drop menu for each drop
  situation and the menus of internal drags (``all_entries``);
* drive them with real Qt events (drag-enter/move/drop with file URLs, mouse
  press/move/release on the canvas, the in-window drop menu's buttons);
* check the RESULT on the saved file: ``snapshot`` writes the figure to a
  .pyf and reads back ``layout_rows`` (the actual arrangement) plus the key
  properties of every panel; ``check_invariants`` verifies undo / redo and a
  save / reload round trip after an action;
* fail on any uncaught exception, Qt warning or error logged by PyFigures
  while an action runs (``Watch``).

Nothing here touches the real screen, the user's settings or the network.
"""
from __future__ import annotations

import logging
import os
import re
import sys
import time
from contextlib import contextmanager

import numpy as np

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_API", "pyqt6")

from qtpy.QtCore import QEvent, QMimeData, QPoint, QPointF, Qt, QTimer, QUrl, qInstallMessageHandler
from qtpy.QtGui import QDragEnterEvent, QDragMoveEvent, QDropEvent, QMouseEvent
from qtpy.QtWidgets import (QApplication, QDialog, QFrame, QMenu, QMessageBox, QPushButton,
                            QWidgetAction)


# ---------------------------------------------------------------------------
# input files
# ---------------------------------------------------------------------------

def _save(path, arr, dims):
    from batoolset.img import Img
    Img(arr, dimensions=dims).save(str(path))
    return str(path)


def _blobs(seed, h=40, w=60, dtype=np.uint8, top=200):
    rng = np.random.default_rng(seed)
    yy, xx = np.mgrid[0:h, 0:w]
    img = np.full((h, w), 20.0)
    for _ in range(4):
        cy, cx, r = rng.uniform(5, h - 5), rng.uniform(5, w - 5), rng.uniform(3, 8)
        img = img + top * np.exp(-((yy - cy) ** 2 + (xx - cx) ** 2) / (2 * r * r))
    return np.clip(img, 0, np.iinfo(dtype).max).astype(dtype)


def make_files(d) -> dict:
    """Every kind of input a user drops or opens, written into folder *d*."""
    d = str(d)
    os.makedirs(d, exist_ok=True)
    f = {}
    from PIL import Image
    png = os.path.join(d, "cells.png")
    Image.fromarray(_blobs(1)).save(png)
    f["png"] = png
    f["png2"] = os.path.join(d, "cells2.png")
    Image.fromarray(_blobs(2)).save(f["png2"])
    f["tif8"] = _save(os.path.join(d, "gray8.tif"), _blobs(3), "hw")
    f["tif16"] = _save(os.path.join(d, "gray16.tif"), _blobs(4, dtype=np.uint16, top=40000), "hw")
    rgb = np.stack([_blobs(5), _blobs(6), _blobs(7)], -1)
    f["rgb"] = _save(os.path.join(d, "rgb.tif"), rgb, "hwc")
    z = np.zeros((4, 40, 60), np.uint8)
    z[2, 10:20, 10:30] = 220                      # only in slice 2: shows in the max projection
    f["zstack"] = _save(os.path.join(d, "zstack.tif"), z, "dhw")
    f["tstack"] = _save(os.path.join(d, "movie.tif"), np.stack([_blobs(10 + i) for i in range(5)]), "thw")
    f["pdf2"] = _two_page_pdf(os.path.join(d, "two_pages.pdf"))
    f["csv"] = os.path.join(d, "values.csv")
    with open(f["csv"], "w", encoding="utf-8") as fh:
        fh.write("group,value\nctrl,1.0\nctrl,1.2\nctrl,0.9\nmut,2.1\nmut,2.4\nmut,1.9\n")
    f["txt"] = os.path.join(d, "notes.txt")
    with open(f["txt"], "w", encoding="utf-8") as fh:
        fh.write("not an image")
    f["tex"] = os.path.join(d, "eq.tex")
    with open(f["tex"], "w", encoding="utf-8") as fh:
        fh.write("\\documentclass{article}\n\\begin{document}\n$E = mc^2$\n\\end{document}\n")
    f["video"] = _video(os.path.join(d, "clip.mp4"))
    sub = os.path.join(d, "folder")
    os.makedirs(sub, exist_ok=True)
    Image.fromarray(_blobs(20)).save(os.path.join(sub, "f1.png"))
    Image.fromarray(_blobs(21)).save(os.path.join(sub, "f2.png"))
    f["folder"] = sub
    from pyfigures import mcp_server as M
    f["pyf"] = os.path.join(d, "other.pyf")
    M.create_figure(f["pyf"], mode="groups", num_groups=1, orientation="X", spacing=3)
    M.add_image(f["pyf"], [0], f["tif8"])
    M.add_image(f["pyf"], [0], f["png2"])
    return f


def _two_page_pdf(path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_pdf import PdfPages
    with PdfPages(path) as pdf:
        for k in range(2):
            fig = plt.figure(figsize=(2, 1.5))
            fig.text(0.5, 0.5, f"page {k + 1}", ha="center")
            pdf.savefig(fig)
            plt.close(fig)
    return path


def _video(path):
    import cv2
    w = cv2.VideoWriter(path, cv2.VideoWriter_fourcc(*"mp4v"), 5, (64, 48))
    for i in range(6):
        frame = np.zeros((48, 64, 3), np.uint8)
        frame[:, i * 8:i * 8 + 16] = 200
        w.write(frame)
    w.release()
    return path


def base_figure(d, files) -> str:
    """The figure most scenarios start from:
    row 1 = gray8 | png (scale bar + text + ROI + inset on gray8),
    row 2 = rgb | zstack."""
    from pyfigures import mcp_server as M
    pyf = os.path.join(str(d), "base.pyf")
    M.create_figure(pyf, mode="groups", num_groups=2, orientation="X", spacing=3)
    M.add_image(pyf, [0], files["tif8"], label="A")
    M.add_image(pyf, [0], files["png"], label="B")
    M.add_image(pyf, [1], files["rgb"], label="C")
    M.add_image(pyf, [1], files["zstack"], label="D")
    M.set_scale_bar(pyf, [0], 0, 10)
    M.add_annotation(pyf, [0], 0, "note")
    M.add_roi_rect(pyf, [0], 0, 5, 5, 10, 10)
    M.add_inset(pyf, [0], 0, files["png2"])
    return pyf


# ---------------------------------------------------------------------------
# window
# ---------------------------------------------------------------------------

def new_gui(qapp, size=(1300, 900)):
    from pyfigures.gui.pfgui import EZFIG_GUI
    EZFIG_GUI.show_tips = lambda self: None
    g = EZFIG_GUI()
    g.resize(*size)
    g.show()
    g._edit_hint_shown = True               # the once-per-session hint is tested on its own
    qapp.processEvents()
    return g


def close_gui(qapp, g):
    tut = getattr(g, "_tutorial", None)
    if tut is not None and hasattr(tut, "stop"):
        try:
            tut.stop()
        except Exception:
            pass
    g._dirty = False
    g._stop_all_img_loaders()
    for w in qapp.topLevelWidgets():
        if w is not g and w.isVisible():
            canvas = getattr(w, "canvas", None)
            if hasattr(canvas, "mark_saved"):
                canvas.mark_saved()
            w.close()
    g.close()
    qapp.processEvents()


def panel(g):
    return g.paint.EZFIG_panel


def images(g_or_shape):
    """Every Image2D panel (not the insets), depth first, in figure order."""
    from batoolset.drawings.shapes.image2d import Image2D
    roots = panel(g_or_shape).shapes_to_draw if hasattr(g_or_shape, "paint") else [g_or_shape]
    out, stack = [], list(roots)
    while stack:
        s = stack.pop(0)
        if isinstance(s, Image2D):
            out.append(s)
        stack[0:0] = list(getattr(s, "content", None) or [])
    return out


def photos(g):
    return [i for i in images(g) if not i.isText]


def rows(g):
    return [s for s in panel(g).shapes_to_draw if type(s).__name__ == "Group" and not s.isText]


def by_name(g, stem):
    return next(i for i in images(g) if os.path.basename(str(i.filename or "")).startswith(stem))


def busy(g):
    th = getattr(g, "_pyf_loader_thread", None)
    try:
        running = th is not None and th.isRunning()
    except RuntimeError:
        running = False
    return bool(running or getattr(g, "_lazy_img_queue", None) or getattr(g, "_active_img_loaders", None))


def settle(qapp, g, cond=None, timeout=30):
    """Until no loader runs, every image has its pixels and *cond* holds."""
    t0 = time.time()
    while time.time() - t0 < timeout:
        qapp.processEvents()
        loaded = all(i.img is not None for i in images(g)
                     if i.filename and i.filename != "@template@")
        if not busy(g) and loaded and (cond is None or cond()):
            break
        time.sleep(0.003)
    for _ in range(4):
        qapp.processEvents()


def load(qapp, g, pyf):
    g._start_pyf_loader([pyf], append=False, reset_undo=True)
    settle(qapp, g, lambda: bool(g.undo_stack))
    g.current_file = pyf
    g._mark_clean()


# ---------------------------------------------------------------------------
# watching for errors
# ---------------------------------------------------------------------------

# Qt messages that say nothing about PyFigures (offscreen platform limits)
_BENIGN_QT = (
    "This plugin does not support",
    "QFont::setPointSize",
    "QFont::setPixelSize",
    "Unable to set geometry",
    "propagateSizeHints",
    "QWindowsWindow::setGeometry",
    "Retrying to obtain clipboard",
    "QBasicTimer::start: Timers cannot be started from another thread",
)


class Watch:
    """Collects uncaught exceptions (sys.excepthook), Qt warnings/criticals
    and ERROR records logged by pyfigures / batoolset while active."""

    def __init__(self):
        self.problems = []

    def __enter__(self):
        self._old_hook = sys.excepthook
        sys.excepthook = lambda t, v, tb: self.problems.append(f"exception {t.__name__}: {v}")

        def qt_handler(mode, ctx, msg):
            name = getattr(mode, "name", str(mode))
            if ("Warning" in name or "Critical" in name or "Fatal" in name) \
                    and not any(b in msg for b in _BENIGN_QT):
                self.problems.append(f"Qt {name}: {msg}")
        self._old_qt = qInstallMessageHandler(qt_handler)

        watch = self

        class _H(logging.Handler):
            def emit(self, record):
                if record.levelno >= logging.ERROR and record.name.split(".")[0] in ("pyfigures", "batoolset"):
                    watch.problems.append(f"log {record.name}: {record.getMessage()[:300]}")
        self._handler = _H()
        logging.getLogger().addHandler(self._handler)
        return self

    def __exit__(self, *exc):
        sys.excepthook = self._old_hook
        qInstallMessageHandler(self._old_qt)
        logging.getLogger().removeHandler(self._handler)
        return False

    def clear(self):
        self.problems.clear()

    def check(self, what=""):
        probs, self.problems = self.problems[:], []
        assert not probs, f"{what}: {probs}"


# ---------------------------------------------------------------------------
# the saved state
# ---------------------------------------------------------------------------

def _plain(html):
    from pyfigures.mcp_tools.core import _html_to_plain
    return _html_to_plain(html or "")


def _txt(el, tag):
    from pyfigures.mcp_tools.core import _child_text
    v = _child_text(el, tag)
    return None if v in (None, "None") else v


def _num(el, tag):
    v = _txt(el, tag)
    try:
        return round(float(v), 1)
    except (TypeError, ValueError):
        return v


def _panel_state(img):
    annots = img.find("annotations")
    kids = list(annots) if annots is not None else []
    letters = sorted(_plain(_txt(a, "text")) for a in kids
                     if a.tag == "TAText2D" and _txt(a, "is_letter") in (True, "True"))
    texts = sorted(_plain(_txt(a, "text")) for a in kids
                   if a.tag == "TAText2D" and _txt(a, "is_letter") not in (True, "True"))
    text_fill = sorted(str(_txt(a, "fill_color")) for a in kids
                       if a.tag == "TAText2D" and _txt(a, "is_letter") not in (True, "True"))
    bars = sorted(_plain(_txt(a, "legend")) for a in kids if a.tag == "ScaleBar")
    rois = sorted(a.tag for a in kids if a.tag not in ("TAText2D", "ScaleBar", "Image2D"))
    fn = _txt(img, "filename")
    return {
        "name": os.path.basename(str(fn)) if fn and fn != "@template@" else fn,
        "text": img.findtext("isText") == "True",
        "crop": tuple(_num(img, k) for k in ("crop_left", "crop_right", "crop_top", "crop_bottom")),
        "theta": _num(img, "theta"),
        "luts": _txt(img, "LUTs"),
        "channels": _txt(img, "channels"),
        "projection": _txt(img, "projection"),
        "range": (_txt(img, "lower_values"), _txt(img, "upper_values")),
        "fill": _txt(img, "fill_color"),
        "script": bool(_txt(img, "custom_loading_script")),
        "series": _txt(img, "serie_to_open"),
        "letters": letters,
        "texts": texts,
        "text_fill": text_fill,
        "scale_bars": bars,
        "rois": rois,
        "insets": sum(1 for a in kids if a.tag == "Image2D"),
        "size": (round(float(img.findtext("width") or 0)), round(float(img.findtext("height") or 0))),
    }


def read_state(pyf) -> dict:
    """layout_rows + every panel's key properties + figure settings, read
    from a saved .pyf (what a user gets back when reopening it)."""
    from pyfigures.mcp_tools.core import _load, layout_rows
    _tree, root = _load(pyf, resolve=False)
    panels = []
    stack = [c for c in root if c.tag in ("Group", "Image2D")]
    while stack:
        el = stack.pop(0)
        if el.tag == "Image2D":
            panels.append(_panel_state(el))
            continue
        content = el.find("content")
        stack[0:0] = [c for c in (list(content) if content is not None else []) if c.tag in ("Group", "Image2D")]
    gp = root.find("SerializableGUIparameters")
    groups = [(_txt(g, "orientation"), _num(g, "space")) for g in root.iter("Group")]
    return {
        "rows": layout_rows(root),
        "panels": panels,
        "groups": groups,
        "background": _txt(gp, "background") if gp is not None else None,
        "space": _txt(gp, "space") if gp is not None else None,
    }


_SNAP = [0]


def snapshot(g, d) -> dict:
    """Save the CURRENT figure to a fresh .pyf in *d* and read it back."""
    g._flush_pending_checkpoints()
    _SNAP[0] += 1
    path = os.path.join(str(d), f"snap_{_SNAP[0]}.pyf")
    g._save_state_to_file(path)
    st = read_state(path)
    st["_file"] = path
    return st


def same(a, b, keys=("rows", "panels", "groups", "background", "space")):
    return {k: a[k] for k in keys} == {k: b[k] for k in keys}


def diff(a, b):
    out = []
    for k in ("rows", "groups", "background", "space"):
        if a[k] != b[k]:
            out.append(f"{k}: {a[k]} -> {b[k]}")
    pa, pb = a["panels"], b["panels"]
    if len(pa) != len(pb):
        out.append(f"panels: {len(pa)} -> {len(pb)}")
    for i, (x, y) in enumerate(zip(pa, pb)):
        for k in x:
            if x[k] != y.get(k):
                out.append(f"panel {i} {x['name']} {k}: {x[k]} -> {y.get(k)}")
    return "; ".join(out) or "(same)"


def check_invariants(qapp, g, d, before, after, undo=True, roundtrip=True):
    """After an action that turned *before* into *after*:
    undo gives *before* back, redo *after*, and a save / reopen keeps *after*."""
    if undo and not same(before, after):
        g.undo()
        settle(qapp, g)
        s = snapshot(g, d)
        assert same(s, before), "undo did not restore the figure: " + diff(before, s)
        g.redo()
        settle(qapp, g)
        s = snapshot(g, d)
        assert same(s, after), "redo did not re-apply the action: " + diff(after, s)
    if roundtrip:
        load(qapp, g, after["_file"])
        s = snapshot(g, d)
        assert same(s, after), "save / reopen changed the figure: " + diff(after, s)


# ---------------------------------------------------------------------------
# menus: capture instead of showing
# ---------------------------------------------------------------------------

def tree_of(menu):
    out = []
    for a in menu.actions():
        if a.isSeparator():             # plain separators and section titles
            continue
        if a.menu() is not None:
            out.append((a.text(), tree_of(a.menu())))
        else:
            out.append(a.text())
    return out


def leaves(tree, prefix=()):
    """Clickable entries as ' / '-joined paths (section titles excluded)."""
    for e in tree:
        if isinstance(e, tuple):
            yield from leaves(e[1], prefix + (e[0],))
        elif e:
            yield " / ".join(prefix + (e,))


class MenuPilot:
    """Replaces QMenu.exec: records the menu and triggers the entry at
    ``pick`` (a ' / '-joined path), or dismisses it (pick None)."""

    def __init__(self, monkeypatch):
        self.trees = []
        self.menus = []
        self.pick = None
        pilot = self

        def fake_exec(menu, *a, **k):
            pilot.trees.append(tree_of(menu))
            pilot.menus.append(menu)
            if pilot.pick is None:
                return None
            act = find_action(menu, pilot.pick)
            act.trigger()               # what a real click does before exec() returns
            return act
        monkeypatch.setattr(QMenu, "exec", fake_exec)
        monkeypatch.setattr(QMenu, "exec_", fake_exec, raising=False)

    @property
    def last(self):
        return list(leaves(self.trees[-1])) if self.trees else []


def find_action(menu, path):
    """The action at *path* ('Sub ▶ / Entry'; labels may contain ' / ' too)."""
    if not isinstance(path, str):
        path = " / ".join(path)

    def search(acts, rest):
        for a in acts:
            if a.isSeparator():
                continue
            if a.menu() is None and a.text() == rest:
                return a
            if a.menu() is not None and rest.startswith(a.text() + " / "):
                hit = search(a.menu().actions(), rest[len(a.text()) + 3:])
                if hit is not None:
                    return hit
        return None
    act = search(menu.actions(), path)
    assert act is not None, f"{path!r} not in {list(leaves(tree_of(menu)))}"
    return act


# ---------------------------------------------------------------------------
# menu bar + toolbar
# ---------------------------------------------------------------------------

def menu_actions(g):
    """[(key, QAction)] of every clickable menu-bar and toolbar entry.
    Keys look like 'menu: File > Export As > PNG' / 'toolbar: Undo'.
    (Wrappers are kept alive while walking: Python ids are reused once a
    temporary wrapper dies, which used to hide whole submenus.)"""
    seen, keep, out = set(), [], []

    def walk(actions, where, kind):
        for a in actions:
            keep.append(a)
            if id(a) in seen or a.isSeparator():
                continue
            seen.add(id(a))
            if a.menu() is not None:
                keep.append(a.menu())
                walk(a.menu().actions(), where + [a.text()], kind)
            elif isinstance(a, QWidgetAction) or not a.text() or a.text().startswith("—"):
                continue
            else:
                out.append((f"{kind}: " + " > ".join(where + [a.text().split(chr(9))[0]]), a))
    walk(g.menuBar.actions(), [], "menu")
    walk(g.mainToolBar.actions(), [], "toolbar")
    walk(g.page_background_button.menu().actions(), ["Background"], "toolbar")
    return out


_TOOLBAR_WIDGETS = ("size_spinbox", "unit_combobox", "main_space_spinner", "auto_lettering_checkbox",
                    "letter_line_edit", "page_bounds_checkbox")


def toolbar_widgets(g):
    """Every interactive widget of the toolbar, keyed 'toolbar-widget: <attribute>'.
    A widget with no known attribute name shows up as 'toolbar-widget: ?<class>'."""
    from qtpy.QtWidgets import QLabel
    by_id = {id(getattr(g, n)): n for n in dir(g) if not n.startswith("__")
             and n in _TOOLBAR_WIDGETS + ("page_background_button",)}
    out = []
    for a in g.mainToolBar.actions():
        w = g.mainToolBar.widgetForAction(a)
        if isinstance(a, QWidgetAction):
            w = a.defaultWidget()
        if w is None or isinstance(w, QLabel) or type(w).__name__ in ("QWidget", "QToolButton") and \
                not isinstance(a, QWidgetAction):
            continue
        name = by_id.get(id(w), "?" + type(w).__name__)
        out.append((f"toolbar-widget: {name}", w))
    return out


# ---------------------------------------------------------------------------
# canvas right-click
# ---------------------------------------------------------------------------

def centre(g, shape, dx=0.0, dy=0.0):
    p = panel(g)
    r = shape.boundingRect()
    return QPointF((r.x() + r.width() / 2 + dx) * p.scale, (r.y() + r.height() / 2 + dy) * p.scale)


def empty_point(g):
    p = panel(g)
    b = p.updateBounds()
    return QPointF((b.right() + 60) * p.scale, (b.bottom() + 60) * p.scale)


def mouse(g, kind, pos, button=Qt.MouseButton.LeftButton, modifiers=Qt.KeyboardModifier.NoModifier):
    p = panel(g)
    t = {"press": QEvent.Type.MouseButtonPress, "move": QEvent.Type.MouseMove,
         "release": QEvent.Type.MouseButtonRelease, "double": QEvent.Type.MouseButtonDblClick}[kind]
    btn = Qt.MouseButton.NoButton if kind == "move" else button
    held = button if kind in ("press", "move", "double") else Qt.MouseButton.NoButton
    ev = QMouseEvent(t, QPointF(pos), QPointF(p.mapToGlobal(QPointF(pos).toPoint())), btn, held, modifiers)
    {"press": p.mousePressEvent, "move": p.mouseMoveEvent, "release": p.mouseReleaseEvent,
     "double": p.mouseDoubleClickEvent}[kind](ev)


def right_click(g, menus, shape=None, pos=None, select=True, pick=None):
    """Select *shape* (as a left click would) and right-click it; returns the
    menu's entries. *pick* triggers that entry."""
    p = panel(g)
    if shape is not None and select:
        p.set_current_selection(shape)
    if pos is None:
        pos = centre(g, shape)
    menus.pick = pick
    n = len(menus.trees)
    mouse(g, "press", pos, Qt.MouseButton.RightButton)
    mouse(g, "release", pos, Qt.MouseButton.RightButton)
    for _ in range(4):
        QApplication.processEvents()
    assert len(menus.trees) == n + 1, "no menu popped up"
    menus.pick = None
    return menus.last


def drag(g, shape, to_point, steps=6, select=True):
    """Press on *shape*, move in steps, release at *to_point* (canvas coordinates)."""
    p = panel(g)
    if select:
        p.set_current_selection(shape)
    start = centre(g, shape)
    mouse(g, "press", start)
    for i in range(1, steps + 1):
        mouse(g, "move", QPointF(start.x() + (to_point.x() - start.x()) * i / steps,
                                 start.y() + (to_point.y() - start.y()) * i / steps))
    mouse(g, "release", to_point)
    for _ in range(4):
        QApplication.processEvents()


# ---------------------------------------------------------------------------
# external drops (files from the file manager)
# ---------------------------------------------------------------------------

def window_pos(g, canvas_point):
    return QPointF(panel(g).mapTo(g, QPointF(canvas_point).toPoint()))


def drop_files(g, paths, canvas_point=None):
    """dragEnter → dragMove → drop with file URLs at *canvas_point* (empty
    canvas below the figure when None). Returns True if the drag was accepted."""
    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(p) for p in paths])
    pos = window_pos(g, canvas_point if canvas_point is not None else empty_point(g))
    enter = QDragEnterEvent(pos.toPoint(), Qt.DropAction.CopyAction, mime,
                            Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
    g.dragEnterEvent(enter)
    if not enter.isAccepted():
        return False
    move = QDragMoveEvent(pos.toPoint(), Qt.DropAction.CopyAction, mime,
                          Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
    g.dragMoveEvent(move)
    assert move.isAccepted()
    ev = QDropEvent(pos, Qt.DropAction.CopyAction, mime, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
    g.dropEvent(ev)
    for _ in range(4):
        QApplication.processEvents()
    g._e2e_mime = mime            # QDropEvent does not own the mime data
    return True


def drop_menu(g):
    frames = [f for f in g.findChildren(QFrame) if f.isVisible() and f.parent() is g
              and f.findChildren(QPushButton)]
    return frames[-1] if frames else None


def drop_choices(g):
    m = drop_menu(g)
    return [b.text() for b in m.findChildren(QPushButton) if b.isEnabled()] if m else []


def click_drop_choice(g, label):
    m = drop_menu(g)
    assert m is not None, "no drop menu"
    btn = next((b for b in m.findChildren(QPushButton) if b.text() == label), None)
    assert btn is not None, (label, drop_choices(g))
    btn.click()
    QApplication.processEvents()


def dismiss_drop_menu(g):
    if drop_menu(g) is not None:
        click_drop_choice(g, "✕  Cancel")


# ---------------------------------------------------------------------------
# dialogs: real exec(), answered by clicking their buttons
# ---------------------------------------------------------------------------

class DialogPilot:
    """Answers modal dialogs that really run (exec / static QMessageBox):
    a timer finds the active modal widget, calls the next handler queued
    for it (fill fields, then accept) or, when none is queued, records it
    and closes it with Cancel / Escape.

    ``expect(match, handler)`` — *match* is a substring of the window title
    or the class name; *handler(dialog)* returns nothing (it accepts itself).
    """

    def __init__(self, interval=15):
        self.queue = []
        self.seen = []
        self.unexpected = []
        self._timer = QTimer()
        self._timer.setInterval(interval)
        self._timer.timeout.connect(self._tick)
        self._timer.start()

    def expect(self, match, handler=None):
        self.queue.append((match, handler or accept))
        return self

    def _tick(self):
        w = QApplication.activeModalWidget()
        if w is None or not w.isVisible() or getattr(w, "_e2e_handled", False):
            return
        w._e2e_handled = True
        title = w.windowTitle()
        cls = type(w).__name__
        self.seen.append(title or cls)
        for i, (match, handler) in enumerate(self.queue):
            if match in title or match == cls:
                del self.queue[i]
                QTimer.singleShot(0, lambda h=handler, d=w: h(d))
                return
        self.unexpected.append(title or cls)
        QTimer.singleShot(0, lambda d=w: reject(d))

    def stop(self):
        self._timer.stop()


def _buttons(d):
    from qtpy.QtWidgets import QAbstractButton
    return [b for b in d.findChildren(QAbstractButton) if b.isVisible() and b.isEnabled()]


def click_button(d, *texts):
    for t in texts:
        for b in _buttons(d):
            if b.text().replace("&", "").strip().lower() == t.lower():
                b.click()
                return True
    return False


def accept(d):
    from qtpy.QtWidgets import QDialogButtonBox
    if isinstance(d, QMessageBox):
        for role in (QMessageBox.ButtonRole.YesRole, QMessageBox.ButtonRole.AcceptRole):
            for b in d.buttons():
                if d.buttonRole(b) == role:
                    b.click()
                    return
    box = d.findChild(QDialogButtonBox)
    if box is not None and box.button(QDialogButtonBox.StandardButton.Ok) is not None:
        box.button(QDialogButtonBox.StandardButton.Ok).click()
        return
    if not click_button(d, "OK", "Ok", "Apply", "Yes", "Save", "Add", "Insert", "Create", "Done", "Close"):
        d.accept()


def reject(d):
    if isinstance(d, QMessageBox):
        for role in (QMessageBox.ButtonRole.RejectRole, QMessageBox.ButtonRole.NoRole):
            for b in d.buttons():
                if d.buttonRole(b) == role:
                    b.click()
                    return
    if not click_button(d, "Cancel", "No", "Close"):
        d.reject()


def widget_by(d, cls, name=None, label=None, index=0):
    """A child widget of *d* by class, objectName or the text of the QLabel
    in front of it (same layout row)."""
    found = d.findChildren(cls)
    if name is not None:
        found = [w for w in found if w.objectName() == name]
    if label is not None:
        from qtpy.QtWidgets import QFormLayout, QLabel
        hits = []
        for lab in d.findChildren(QLabel):
            if label.lower() in lab.text().lower() and lab.buddy() is not None and isinstance(lab.buddy(), cls):
                hits.append(lab.buddy())
        for lay in d.findChildren(QFormLayout):
            for r in range(lay.rowCount()):
                li = lay.itemAt(r, QFormLayout.ItemRole.LabelRole)
                fi = lay.itemAt(r, QFormLayout.ItemRole.FieldRole)
                if li and fi and li.widget() and isinstance(fi.widget(), cls) \
                        and label.lower() in getattr(li.widget(), "text", lambda: "")().lower():
                    hits.append(fi.widget())
        from qtpy.QtWidgets import QGridLayout
        for lay in d.findChildren(QGridLayout):
            for r in range(lay.rowCount()):
                cells = [lay.itemAtPosition(r, c) for c in range(lay.columnCount())]
                ws = [c.widget() for c in cells if c is not None and c.widget() is not None]
                for i, w in enumerate(ws[:-1]):
                    if isinstance(w, QLabel) and label.lower() in w.text().lower() and isinstance(ws[i + 1], cls):
                        hits.append(ws[i + 1])
        own = [w for w in found if label.lower() in str(getattr(w, "text", lambda: "")()).lower()]
        found = hits or own or [w for w in found if label.lower() in (w.toolTip() + w.objectName()).lower()]
    assert len(found) > index, f"no {cls.__name__} name={name} label={label} in {type(d).__name__}"
    return found[index]


@contextmanager
def dialogs():
    pilot = DialogPilot()
    try:
        yield pilot
    finally:
        pilot.stop()


# ---------------------------------------------------------------------------
# every entry a user can reach
# ---------------------------------------------------------------------------

SELECTION_KINDS = ("nothing", "image", "standalone image", "several images", "row", "text row",
                   "equation", "inset", "template slot", "rgb image", "z stack")

DROP_SITUATIONS = ("one image on empty canvas", "several images on empty canvas", "onto an image",
                   "onto a group", "onto a template slot", "one time stack", "one z stack", ".pyf",
                   ".tex", "csv", "folder", "unsupported file", "multi-series file", "video")

DRAG_SITUATIONS = ("image onto image of another row", "row onto row",
                   "loose image onto loose image", "row onto loose image", "image to empty space",
                   "loose image onto image in row")


def select_kind(qapp, g, kind):
    """Select (as the user would) a shape of *kind*; returns (shape, point
    to right-click, select flag)."""
    p = panel(g)
    if kind == "nothing":
        p.set_current_selection(None)
        return None, empty_point(g), False
    if kind == "image":
        return by_name(g, "gray8"), None, True
    if kind == "inset":
        img = by_name(g, "gray8")
        r = img.boundingRect()
        return img, QPointF((r.right() - 4) * p.scale, (r.top() + 4) * p.scale), True
    if kind == "rgb image":
        return by_name(g, "rgb"), None, True
    if kind == "z stack":
        return by_name(g, "zstack"), None, True
    if kind == "row":
        return rows(g)[0], None, True
    if kind == "several images":
        sel = [by_name(g, "gray8"), by_name(g, "cells")]
        p.set_current_selection(sel)
        return sel[0], None, False
    if kind == "text row":
        tr = next(s for s in p.shapes_to_draw if getattr(s, "isText", False))
        t = images(tr)[0]
        return t, None, True
    if kind == "equation":
        from pyfigures.equations import is_equation
        return next(i for i in images(g) if is_equation(getattr(i, "filename", None))), None, True
    if kind == "standalone image":
        return next(s for s in p.shapes_to_draw if type(s).__name__ == "Image2D"), None, True
    if kind == "template slot":
        return next(i for i in images(g) if i.filename == "@template@"), None, True
    raise ValueError(kind)


def prepare_selection_figure(qapp, g, d, files):
    """Load the base figure and add, through the GUI's own code, a label
    row above row 1, a standalone image and a template slot."""
    from pyfigures import mcp_server as M
    pyf = base_figure(d, files)
    M.add_equation(pyf, [1], r"\alpha + \beta")
    load(qapp, g, pyf)
    p = panel(g)
    p.set_current_selection(rows(g)[0])
    p.associate_text_row(sensitivity="below")
    g.all_images_directly([files["tif16"], files["png2"]])
    settle(qapp, g, lambda: len(images(g)) >= 9)
    loose = [s for s in p.shapes_to_draw if type(s).__name__ == "Image2D"]
    p.templatify(loose[-1])
    p.set_current_selection(None)
    settle(qapp, g)
    return pyf


def context_menu_entries(qapp, g, menus):
    """{kind: [entry path, ...]} of the canvas right-click menu."""
    out = {}
    for kind in SELECTION_KINDS:
        shape, pos, select = select_kind(qapp, g, kind)
        out[kind] = right_click(g, menus, shape, pos=pos, select=select)
    return out


def all_menu_keys(g):
    return [k for k, _a in menu_actions(g)] + [k for k, _w in toolbar_widgets(g)]


def ctx_key(entry):
    return f"right-click: {entry}"


def drop_key(situation, choice):
    return f"drop [{situation}]: {choice}"


def drag_key(situation, choice):
    return f"drag [{situation}]: {choice}"


def norm(text):
    return re.sub(r"\s+", " ", text).strip()


# ---------------------------------------------------------------------------
# pytest fixtures (import them into a test module to use them)
# ---------------------------------------------------------------------------

import pytest  # noqa: E402


@pytest.fixture(scope="session")
def e2e_files(tmp_path_factory):
    return make_files(tmp_path_factory.mktemp("e2e_inputs"))


@pytest.fixture(scope="module")
def e2e_gui(qapp):
    g = new_gui(qapp)
    yield g
    close_gui(qapp, g)


@pytest.fixture
def menus(monkeypatch):
    return MenuPilot(monkeypatch)


@pytest.fixture
def watch():
    with Watch() as w:
        yield w


@pytest.fixture
def no_file_dialogs(monkeypatch):
    """File pickers are native OS dialogs: tests answer them through this
    dict ({'open': path, 'open_many': [paths], 'save': path, 'dir': path})."""
    from qtpy.QtWidgets import QFileDialog
    from pyfigures.gui import pfgui
    ans = {"open": None, "open_many": None, "save": None, "dir": None}
    monkeypatch.setattr(pfgui, "openFileNameDialog", lambda *a, **k: ans["open"])
    monkeypatch.setattr(pfgui, "openFileNamesDialog", lambda *a, **k: ans["open_many"])
    monkeypatch.setattr(pfgui, "saveFileDialog", lambda *a, **k: ans["save"])
    monkeypatch.setattr(QFileDialog, "getOpenFileName", staticmethod(lambda *a, **k: (ans["open"] or "", "")))
    monkeypatch.setattr(QFileDialog, "getOpenFileNames", staticmethod(lambda *a, **k: (ans["open_many"] or [], "")))
    monkeypatch.setattr(QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: (ans["save"] or "", "")))
    monkeypatch.setattr(QFileDialog, "getExistingDirectory", staticmethod(lambda *a, **k: ans["dir"] or ""))
    import webbrowser
    opened = ans.setdefault("browser", [])
    monkeypatch.setattr(webbrowser, "open", lambda url, *a, **k: opened.append(url) or True)
    from qtpy.QtGui import QDesktopServices
    monkeypatch.setattr(QDesktopServices, "openUrl", staticmethod(lambda url: opened.append(url.toString()) or True))
    return ans


RECORD = bool(os.environ.get("PYF_E2E_RECORD"))


def expect_rows(after, expected, what=""):
    """Compare layout rows; patterns may use '*' for any characters."""
    got = after["rows"]
    if RECORD:
        print(f"\n[RECORD] {what}: {got}")
        return
    ok = len(got) == len(expected) and all(
        re.fullmatch(re.escape(e).replace(r"\*", ".*"), x) for e, x in zip(expected, got))
    assert ok, f"{what}: rows {got} != expected {expected}"
