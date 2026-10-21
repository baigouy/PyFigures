"""Help → Debug → Record a bug: turns a few minutes of a user's clicking into
a regression test.

While recording, every step is logged at the level a test can replay — menu
and toolbar actions (by their menu path), right-click and drag-menu choices
(and on which panel), external drops (files, target panel) and the drop-menu
choice, dialogs (title, values, the button pressed), file pickers (the path
chosen), double-clicks and drags on the canvas — with, after each step, the
figure's structure (rows, panels, letters) and a small screenshot, and any
Python exception. Stopping (or quitting while recording) asks what went wrong
and what was expected.

A recording is a folder in the user's own data directory (never in a source
checkout, it can be large): recording.json, start.pyf (the figure when the
recording started), files/ (copies of its source images, large ones only
referenced) and shots/. ``python -m pyfigures.gui.bug_recorder make-test``
turns it into a small regression test (tests/recordings/, replayed by
tests/test_recordings.py) with tiny stand-in images.

CLI:  python -m pyfigures.gui.bug_recorder list | show <dir> | make-test <dir> <out_dir>
MCP:  list_bug_recordings, read_bug_recording
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import time
import traceback

RECORDING_VERSION = 1
MAX_COPIED_SOURCE_MB = 25          # bigger source images are only referenced
SHOT_WIDTH = 480


def recordings_dir() -> str:
    """Per-user folder holding the recordings (outside any source tree)."""
    if sys.platform.startswith("win"):
        base = os.environ.get("LOCALAPPDATA") or os.path.join(os.path.expanduser("~"), "AppData", "Local")
    elif sys.platform == "darwin":
        base = os.path.join(os.path.expanduser("~"), "Library", "Application Support")
    else:
        base = os.environ.get("XDG_DATA_HOME") or os.path.join(os.path.expanduser("~"), ".local", "share")
    return os.path.join(base, "PyFigures", "recordings")


# ---------------------------------------------------------------------------
# figure structure (what each step changed)
# ---------------------------------------------------------------------------
def figure_summary(pyf_path: str) -> dict:
    """{'rows': layout rows, 'panels': [{name, letters, projection}]} of a saved figure."""
    import xml.etree.ElementTree as ET
    from pyfigures.mcp_tools.core import _child_text, _html_to_plain, _iter_panel_elements, layout_rows
    root = ET.parse(pyf_path).getroot()
    panels = []
    for img in _iter_panel_elements(root):
        fn = _child_text(img, "filename")
        annots = img.find("annotations")
        letters = [_html_to_plain(_child_text(a, "text") or "") for a in (annots if annots is not None else [])
                   if a.tag == "TAText2D" and _child_text(a, "is_letter") == "True"]
        panels.append({"name": os.path.basename(str(fn)) if fn not in (None, "None") else None,
                       "letters": letters, "projection": _child_text(img, "projection")})
    return {"rows": layout_rows(root), "panels": panels}


# ---------------------------------------------------------------------------
# helpers on widgets
# ---------------------------------------------------------------------------
def _label_of(w):
    """Text of the QLabel in front of *w* (buddy, form row or grid row), or ''."""
    from qtpy.QtWidgets import QFormLayout, QGridLayout, QLabel
    parent = w.parentWidget()
    if parent is None:
        return ""
    for lab in parent.findChildren(QLabel):
        if lab.buddy() is w:
            return lab.text()
    lay = parent.layout()
    if isinstance(lay, QFormLayout):
        for r in range(lay.rowCount()):
            fi = lay.itemAt(r, QFormLayout.ItemRole.FieldRole)
            li = lay.itemAt(r, QFormLayout.ItemRole.LabelRole)
            if fi is not None and fi.widget() is w and li is not None and isinstance(li.widget(), QLabel):
                return li.widget().text()
    if isinstance(lay, QGridLayout):
        idx = lay.indexOf(w)
        if idx >= 0:
            row, col, _, _ = lay.getItemPosition(idx)
            if col > 0:
                item = lay.itemAtPosition(row, col - 1)
                if item is not None and isinstance(item.widget(), QLabel):
                    return item.widget().text()
    return ""


def dialog_values(dlg) -> list:
    """[{type, label, value}] of the editable fields of *dlg*, in widget order."""
    from qtpy.QtWidgets import (QAbstractSpinBox, QCheckBox, QComboBox, QDoubleSpinBox, QLineEdit,
                                QPlainTextEdit, QRadioButton, QSpinBox, QTextEdit)
    out = []
    for w in dlg.findChildren(object):
        try:
            if not hasattr(w, "isVisible") or not w.isVisible():
                continue
            if isinstance(w, QLineEdit) and not isinstance(w.parent(), (QAbstractSpinBox, QComboBox)):
                out.append({"type": "line", "label": _label_of(w), "value": w.text()})
            elif isinstance(w, (QSpinBox, QDoubleSpinBox)):
                out.append({"type": "spin", "label": _label_of(w), "value": w.value()})
            elif isinstance(w, QComboBox):
                out.append({"type": "combo", "label": _label_of(w), "value": w.currentText()})
            elif isinstance(w, (QCheckBox, QRadioButton)):
                out.append({"type": "check", "label": w.text(), "value": w.isChecked()})
            elif isinstance(w, (QTextEdit, QPlainTextEdit)) and not w.isReadOnly():
                out.append({"type": "text", "label": _label_of(w), "value": w.toPlainText()})
        except RuntimeError:
            continue
    return out


def _menu_path(menu, action):
    """(root menu title or '', [submenu titles…, action text]) of *action*."""
    parts = [action.text().split("\t")[0]]
    m = menu
    while m is not None:
        parent = m.parentWidget()
        from qtpy.QtWidgets import QMenu
        if isinstance(parent, QMenu) and m.menuAction() in parent.actions():
            parts.insert(0, m.title())
            m = parent
            continue
        return m.title(), parts
    return "", parts


# ---------------------------------------------------------------------------
# the recorder
# ---------------------------------------------------------------------------
class BugRecorder:
    """Records the steps of a user in the figure editor *gui* (an EZFIG_GUI)."""

    def __init__(self, gui):
        self.gui = gui
        self.folder = None
        self.steps = []
        self.active = False
        self._filter = None
        self._timer = None
        self._press = None
        self._saved = {}
        self._asking = False

    # -- start / stop -------------------------------------------------------
    def start(self, folder=None):
        from qtpy.QtCore import QTimer
        from qtpy.QtWidgets import QApplication, QLabel
        stamp = time.strftime("%Y%m%d-%H%M%S")
        self.folder = folder or os.path.join(recordings_dir(), stamp)
        os.makedirs(os.path.join(self.folder, "shots"), exist_ok=True)
        self.steps = []
        self.t0 = time.time()
        start_pyf = os.path.join(self.folder, "start.pyf")
        self.gui._save_state_to_file(start_pyf)
        self.sources = self._copy_sources(start_pyf)
        self.active = True
        self._filter = _Filter(self)
        QApplication.instance().installEventFilter(self._filter)
        self._timer = QTimer()
        self._timer.setSingleShot(True)
        self._timer.setInterval(400)
        self._timer.timeout.connect(self._snapshot)
        self._hook_file_dialogs()
        self._saved["excepthook"] = sys.excepthook
        sys.excepthook = self._excepthook
        self._badge = QLabel("● REC")
        self._badge.setStyleSheet("color: #d00; font-weight: bold; padding: 0 6px;")
        self._badge.setToolTip("Recording a bug report: Help → Debug → Stop recording")
        self.gui.statusBar().addPermanentWidget(self._badge)
        self.add("start", figure="start.pyf", current_file=getattr(self.gui, "current_file", None),
                 window=[self.gui.width(), self.gui.height()])
        return self.folder

    def stop(self, ask=True):
        """Stop recording; with *ask*, the 'What went wrong?' dialog. Returns
        the recording folder, or None when the user discarded it."""
        if not self.active:
            return None
        from qtpy.QtWidgets import QApplication
        self.active = False
        try:
            QApplication.instance().removeEventFilter(self._filter)
        except RuntimeError:
            pass
        self._timer.stop()
        self._unhook_file_dialogs()
        sys.excepthook = self._saved.pop("excepthook", sys.__excepthook__)
        try:
            self.gui.statusBar().removeWidget(self._badge)
            self._badge.deleteLater()
        except RuntimeError:
            pass
        self._snapshot()
        notes = {"what_went_wrong": "", "expected": "", "bad_steps": []}
        if ask:
            notes = ask_report(self.gui, self) if not self._asking else notes
            if notes is None:
                shutil.rmtree(self.folder, ignore_errors=True)
                return None
        self.save(notes)
        return self.folder

    def save(self, notes):
        try:
            from pyfigures.version import __VERSION__ as version
        except Exception:
            version = None
        data = {"format": "pyfigures-bug-recording", "version": RECORDING_VERSION,
                "pyfigures": version, "platform": sys.platform,
                "recorded": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(self.t0)),
                "sources": self.sources, "steps": self.steps, "notes": notes,
                "status": "open", "checks": []}
        path = os.path.join(self.folder, "recording.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=1)
        return path

    # -- steps ------------------------------------------------------------------
    def add(self, kind, **data):
        if not self.active and kind != "start":
            return None
        step = {"n": len(self.steps) + 1, "t": round(time.time() - self.t0, 2), "kind": kind}
        step.update(data)
        self.steps.append(step)
        if self._timer is not None:
            self._timer.start()               # state + screenshot once things settle
        return step

    def _snapshot(self):
        """The figure's structure and a screenshot, on the last step."""
        if not self.steps or "state" in self.steps[-1]:
            return
        step = self.steps[-1]
        tmp = os.path.join(self.folder, "_state.pyf")
        try:
            self.gui._save_state_to_file(tmp)
            step["state"] = figure_summary(tmp)
        except Exception as e:
            step["state"] = {"error": f"{type(e).__name__}: {e}"}
        finally:
            try:
                os.remove(tmp)
            except OSError:
                pass
        try:
            from qtpy.QtCore import Qt
            pix = self.gui.grab()
            if pix.width() > SHOT_WIDTH:
                pix = pix.scaledToWidth(SHOT_WIDTH, Qt.TransformationMode.SmoothTransformation)
            name = "shots/step_%03d.png" % step["n"]
            pix.save(os.path.join(self.folder, name))
            step["screenshot"] = name
        except Exception:
            pass

    def _excepthook(self, etype, value, tb):
        self.add("exception", error=f"{etype.__name__}: {value}",
                 traceback="".join(traceback.format_exception(etype, value, tb))[-4000:])
        hook = self._saved.get("excepthook") or sys.__excepthook__
        hook(etype, value, tb)

    # -- what is under the mouse ---------------------------------------------------
    def panel_at(self, canvas_point):
        """'name.tif' or 'name.tif#2' (2nd panel of that file) under a canvas point."""
        from batoolset.drawings.shapes.image2d import Image2D
        pane = self.gui.paint.EZFIG_panel
        x = canvas_point.x() / (pane.scale or 1)
        y = canvas_point.y() / (pane.scale or 1)
        best, best_area, names = None, None, {}
        stack = list(pane.shapes_to_draw)
        while stack:
            s = stack.pop(0)
            stack[0:0] = list(getattr(s, "content", None) or [])
            if not isinstance(s, Image2D):
                continue
            name = os.path.basename(str(s.filename or "")) or ("text" if s.isText else "?")
            names[name] = names.get(name, 0) + 1
            try:
                r = s.getRect(all=True)
            except TypeError:
                r = s.boundingRect()
            if r.contains(x, y) and (best_area is None or r.width() * r.height() < best_area):
                best = name if names[name] == 1 else f"{name}#{names[name]}"
                best_area = r.width() * r.height()
        return best

    def selected_name(self):
        from batoolset.drawings.shapes.image2d import Image2D
        sel = self.gui.paint.EZFIG_panel.selected_shape
        if isinstance(sel, list) and len(sel) == 1:
            sel = sel[0]
        if isinstance(sel, Image2D):
            return os.path.basename(str(sel.filename or "")) or "text"
        if sel is not None and not isinstance(sel, list):
            imgs = []
            stack = [sel]
            while stack:
                s = stack.pop(0)
                stack[0:0] = list(getattr(s, "content", None) or [])
                if isinstance(s, Image2D):
                    imgs.append(os.path.basename(str(s.filename or "")))
            return {"group_of": imgs}
        return None

    # -- source images -------------------------------------------------------------
    def _copy_sources(self, start_pyf):
        """{original path: copied name or None (too big / missing)} of the
        start figure's source images."""
        import xml.etree.ElementTree as ET
        from pyfigures.mcp_tools.core import _child_text, _iter_panel_elements
        out = {}
        try:
            root = ET.parse(start_pyf).getroot()
        except Exception:
            return out
        os.makedirs(os.path.join(self.folder, "files"), exist_ok=True)
        for img in _iter_panel_elements(root):
            fn = _child_text(img, "filename")
            if not fn or fn in ("None", "@template@") or fn in out:
                continue
            out[fn] = self._copy_file(fn)
        return out

    def _copy_file(self, path):
        try:
            if not os.path.isfile(path) or os.path.getsize(path) > MAX_COPIED_SOURCE_MB * 1e6:
                return None
            name = os.path.basename(path)
            dest = os.path.join(self.folder, "files", name)
            k = 1
            while os.path.exists(dest):
                k += 1
                dest = os.path.join(self.folder, "files", f"{k}_{name}")
            shutil.copy2(path, dest)
            return os.path.relpath(dest, self.folder).replace("\\", "/")
        except OSError:
            return None

    def note_file(self, path):
        """Copy a file used during the recording (a dropped / opened image)."""
        if path and path not in self.sources:
            self.sources[path] = self._copy_file(path)

    # -- file pickers ------------------------------------------------------------------
    _PICKERS = ("openFileNameDialog", "openFileNamesDialog", "saveFileDialog", "openDirectoryDialog")

    def _hook_file_dialogs(self):
        from pyfigures.gui import pfgui
        for name in self._PICKERS:
            orig = getattr(pfgui, name, None)
            if orig is None:
                continue
            self._saved[name] = orig

            def wrapped(*a, _orig=orig, _name=name, **k):
                res = _orig(*a, **k)
                self.add("file_dialog", picker=_name, result=res)
                if _name.startswith("open"):
                    for p in (res if isinstance(res, (list, tuple)) else [res]):
                        if isinstance(p, str) and os.path.isfile(p):
                            self.note_file(p)
                return res
            setattr(pfgui, name, wrapped)

    def _unhook_file_dialogs(self):
        from pyfigures.gui import pfgui
        for name in self._PICKERS:
            if name in self._saved:
                setattr(pfgui, name, self._saved.pop(name))


def _make_filter_class():
    from qtpy.QtCore import QEvent, QObject, Qt
    from qtpy.QtWidgets import QAbstractButton, QApplication, QDialog, QMenu, QMessageBox, QToolButton

    class Filter(QObject):
        """Application-wide event filter: sees a click before the widget acts
        on it, so a step is logged before the dialog it opens."""

        def __init__(self, rec):
            super().__init__()
            self.rec = rec

        def eventFilter(self, obj, ev):
            try:
                self._look(obj, ev)
            except Exception:
                pass                              # never break the GUI being recorded
            return False

        def _look(self, obj, ev):
            rec = self.rec
            if not rec.active:
                return
            t = ev.type()
            gui = rec.gui
            pane = gui.paint.EZFIG_panel
            if t == QEvent.Type.MouseButtonRelease and isinstance(obj, QMenu):
                act = obj.actionAt(ev.position().toPoint())
                if act is not None and act.isEnabled() and act.menu() is None and not act.isSeparator():
                    self._menu_choice(obj, act)
            elif t == QEvent.Type.KeyPress and isinstance(obj, QMenu) \
                    and ev.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                act = obj.activeAction()
                if act is not None and act.menu() is None:
                    self._menu_choice(obj, act)
            elif t == QEvent.Type.Shortcut and type(obj).__name__ == "QAction":
                rec.add("shortcut", key=ev.key().toString(), action=obj.text().split("\t")[0])
            elif t == QEvent.Type.MouseButtonRelease and isinstance(obj, QToolButton) \
                    and obj.defaultAction() is not None and obj.window() is gui:
                rec.add("action", key="toolbar: " + obj.defaultAction().text().split("\t")[0])
            elif t == QEvent.Type.MouseButtonRelease and isinstance(obj, QAbstractButton) \
                    and obj.rect().contains(ev.position().toPoint()):
                menu = getattr(gui, "_dnd_menu", None)
                if menu is not None and obj.parent() is menu:
                    rec.add("drop_choice", label=obj.text())
                elif isinstance(obj.window(), (QDialog, QMessageBox)) and obj.window() is not gui:
                    rec.add("button", dialog=obj.window().windowTitle(), text=obj.text().replace("&", ""))
            elif t == QEvent.Type.Drop and obj is gui:
                paths = [u.toLocalFile() for u in ev.mimeData().urls()]
                for p in paths:
                    if os.path.isfile(p):
                        rec.note_file(p)
                pos = pane.mapFrom(gui, ev.position().toPoint())
                rec.add("drop", files=paths, onto=rec.panel_at(pos))
            elif obj is pane and t == QEvent.Type.MouseButtonDblClick:
                rec.add("double_click", panel=rec.panel_at(ev.position()))
            elif obj is pane and t == QEvent.Type.MouseButtonPress:
                rec._press = (ev.position(), rec.panel_at(ev.position()), ev.button())
            elif obj is pane and t == QEvent.Type.MouseButtonRelease and rec._press is not None:
                p0, name, button = rec._press
                rec._press = None
                p1 = ev.position()
                if button == Qt.MouseButton.LeftButton and name \
                        and abs(p1.x() - p0.x()) + abs(p1.y() - p0.y()) > 6:
                    s = pane.scale or 1
                    rec.add("drag", panel=name, onto=rec.panel_at(p1),
                            to=[round(p1.x() / s, 1), round(p1.y() / s, 1)])
            elif obj is pane and t == QEvent.Type.KeyPress and not ev.modifiers() & (
                    Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.MetaModifier):
                from qtpy.QtGui import QKeySequence
                if ev.key() not in (Qt.Key.Key_Shift, Qt.Key.Key_Control, Qt.Key.Key_Alt, Qt.Key.Key_Meta):
                    rec.add("key", key=QKeySequence(ev.key()).toString(), selected=rec.selected_name())
            elif t == QEvent.Type.Show and isinstance(obj, (QDialog, QMessageBox)) and obj.isWindow() \
                    and not getattr(obj, "_pyf_report", False):
                rec.add("dialog_open", title=obj.windowTitle(), cls=type(obj).__name__,
                        text=obj.text() if isinstance(obj, QMessageBox) else None)
            elif t == QEvent.Type.Hide and isinstance(obj, (QDialog, QMessageBox)) and obj.isWindow() \
                    and not getattr(obj, "_pyf_report", False):
                button = None
                if isinstance(obj, QMessageBox) and obj.clickedButton() is not None:
                    button = obj.clickedButton().text().replace("&", "")
                elif getattr(obj, "selected_option", None):
                    button = obj.selected_option
                rec.add("dialog_close", title=obj.windowTitle(), cls=type(obj).__name__,
                        result=int(obj.result()), button=button, values=dialog_values(obj))

        def _menu_choice(self, menu, act):
            rec = self.rec
            root, parts = _menu_path(menu, act)
            bar = rec.gui.menuBar
            if root and any(a.menu() is not None and a.menu().title() == root for a in bar.actions()):
                rec.add("action", key="menu: " + " > ".join([root] + parts))
            else:
                prev = rec.steps[-1]["kind"] if rec.steps else None
                rec.add("drag_choice" if prev == "drag" else "context", path=parts,
                        selected=rec.selected_name())

    return Filter


_FILTER_CLASS = None


def _Filter(rec):
    global _FILTER_CLASS
    if _FILTER_CLASS is None:
        _FILTER_CLASS = _make_filter_class()
    return _FILTER_CLASS(rec)


# ---------------------------------------------------------------------------
# 'What went wrong?'
# ---------------------------------------------------------------------------
def _describe(step):
    k = step["kind"]
    if k == "action":
        return step["key"]
    if k in ("context", "drag_choice"):
        sel = step.get("selected")
        return ("right-click" if k == "context" else "drag menu") + f" on {sel}: " + " / ".join(step["path"])
    if k == "drop":
        return "drop " + ", ".join(os.path.basename(p) for p in step["files"]) + \
            (f" onto {step['onto']}" if step.get("onto") else "")
    if k == "drop_choice":
        return "drop menu: " + step["label"]
    if k in ("dialog_open", "dialog_close"):
        return ("opened " if k == "dialog_open" else "closed ") + f"dialog '{step['title']}'" + \
            (f" ({step['button']})" if step.get("button") else "")
    if k == "button":
        return f"clicked '{step['text']}' in '{step['dialog']}'"
    if k == "file_dialog":
        return f"{step['picker']}: {step['result']}"
    if k == "double_click":
        return f"double-click {step.get('panel')}"
    if k == "drag":
        return f"drag {step['panel']} to {step.get('onto') or step['to']}"
    if k == "exception":
        return "ERROR " + step["error"]
    return k + " " + ", ".join(f"{a}={b}" for a, b in step.items() if a not in ("n", "t", "kind", "state",
                                                                                    "screenshot"))


def _make_report_dialog():
    from qtpy.QtCore import QSize, Qt
    from qtpy.QtGui import QIcon, QPixmap
    from qtpy.QtWidgets import (QDialog, QDialogButtonBox, QLabel, QListWidget, QListWidgetItem,
                                QPlainTextEdit, QVBoxLayout)

    class _ReportDialog(QDialog):
        """Steps (tick the wrong ones), what went wrong, what was expected."""

        _pyf_report = True                       # not a step of the recording

        def __init__(self, parent, rec):
            super().__init__(parent)
            self.setWindowTitle("Describe the bug")
            lay = QVBoxLayout(self)
            lay.addWidget(QLabel(f"<b>{len(rec.steps)} steps recorded.</b> Tick the step(s) where "
                                 "something went wrong (hover for details).", self))
            self.steps = QListWidget(self)
            self.steps.setIconSize(QSize(160, 100))
            for step in rec.steps:
                item = QListWidgetItem(f"{step['n']}. {_describe(step)}")
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(Qt.CheckState.Checked if step["kind"] == "exception"
                                   else Qt.CheckState.Unchecked)
                if step.get("screenshot"):
                    item.setIcon(QIcon(QPixmap(os.path.join(rec.folder, step["screenshot"]))))
                rows = (step.get("state") or {}).get("rows")
                if rows:
                    item.setToolTip("\n".join(rows))
                self.steps.addItem(item)
            lay.addWidget(self.steps, 1)
            lay.addWidget(QLabel("What went wrong?", self))
            self.wrong = QPlainTextEdit(self)
            self.wrong.setPlaceholderText("e.g. the montage group has only one letter and looks empty")
            lay.addWidget(self.wrong)
            lay.addWidget(QLabel("What did you expect?", self))
            self.expected = QPlainTextEdit(self)
            self.expected.setPlaceholderText("e.g. one letter for the montage, its frames inside the group")
            lay.addWidget(self.expected)
            lay.addWidget(QLabel(f"Saved in {rec.folder}", self))
            box = QDialogButtonBox(self)
            box.addButton("Save the report", QDialogButtonBox.ButtonRole.AcceptRole)
            box.addButton("Discard the recording", QDialogButtonBox.ButtonRole.RejectRole)
            box.accepted.connect(self.accept)
            box.rejected.connect(self.reject)
            lay.addWidget(box)
            self.resize(720, 640)

        def notes(self):
            bad = [i + 1 for i in range(self.steps.count())
                   if self.steps.item(i).checkState() == Qt.CheckState.Checked]
            return {"what_went_wrong": self.wrong.toPlainText().strip(),
                    "expected": self.expected.toPlainText().strip(), "bad_steps": bad}

        @classmethod
        def ask(cls, parent, rec):
            rec._asking = True
            try:
                dlg = cls(parent, rec)
                if dlg.exec() != QDialog.DialogCode.Accepted:
                    return None
                return dlg.notes()
            finally:
                rec._asking = False

    return _ReportDialog


_REPORT_DIALOG = None


def ask_report(parent, rec):
    """The 'Describe the bug' dialog (class built on first use); None = discard."""
    global _REPORT_DIALOG
    if _REPORT_DIALOG is None:
        _REPORT_DIALOG = _make_report_dialog()
    return _REPORT_DIALOG.ask(parent, rec)


# ---------------------------------------------------------------------------
# reading recordings (MCP / CLI) and making a test of one
# ---------------------------------------------------------------------------
def list_recordings(folder=None) -> list:
    """[{path, recorded, steps, errors, what_went_wrong, status}] newest first."""
    folder = folder or recordings_dir()
    out = []
    if not os.path.isdir(folder):
        return out
    for name in sorted(os.listdir(folder), reverse=True):
        path = os.path.join(folder, name, "recording.json")
        if not os.path.isfile(path):
            continue
        try:
            with open(path, encoding="utf-8") as f:
                d = json.load(f)
        except (OSError, ValueError):
            continue
        out.append({"path": os.path.dirname(path), "recorded": d.get("recorded"),
                    "steps": len(d.get("steps", [])),
                    "errors": sum(1 for s in d.get("steps", []) if s["kind"] == "exception"),
                    "what_went_wrong": d.get("notes", {}).get("what_went_wrong", ""),
                    "status": d.get("status")})
    return out


def read_recording(path) -> dict:
    """The recording at *path* (folder or recording.json), each step with a
    one-line description; screenshots as absolute paths."""
    folder = path if os.path.isdir(path) else os.path.dirname(path)
    with open(os.path.join(folder, "recording.json"), encoding="utf-8") as f:
        d = json.load(f)
    for s in d.get("steps", []):
        s["describe"] = _describe(s)
        if s.get("screenshot"):
            s["screenshot"] = os.path.join(folder, s["screenshot"])
    d["folder"] = folder
    return d


def _small_copy(src, dest, max_side=256):
    """A small stand-in of an image (same dimensions order and dtype) for a
    regression test; other files are copied when small, else skipped."""
    try:
        from batoolset.img import Img
        import numpy as np
        img = Img(src)
        arr = np.asarray(img)
        dims = getattr(img, "metadata", {}).get("dimensions") or None
        hi = dims.index("h") if dims and "h" in dims else arr.ndim - 2
        step = max(1, int(np.ceil(max(arr.shape[hi], arr.shape[hi + 1]) / max_side)))
        sl = [slice(None)] * arr.ndim
        sl[hi] = slice(None, None, step)
        sl[hi + 1] = slice(None, None, step)
        Img(np.ascontiguousarray(arr[tuple(sl)]), dimensions=dims).save(dest)
        return True
    except Exception:
        if os.path.getsize(src) < 2e6:
            shutil.copy2(src, dest)
            return True
        return False


def make_test(rec_folder, out_folder) -> str:
    """Copy a recording into a regression-test folder (tests/recordings/<name>):
    recording.json without screenshots, start.pyf, and small stand-ins of the
    source images. Returns the new recording.json path."""
    d = read_recording(rec_folder)
    os.makedirs(os.path.join(out_folder, "files"), exist_ok=True)
    sources = {}
    for orig, copied in (d.get("sources") or {}).items():
        src = os.path.join(rec_folder, copied) if copied else orig
        if not os.path.isfile(src):
            sources[orig] = None
            continue
        name = "files/" + os.path.basename(copied or orig)
        sources[orig] = name if _small_copy(src, os.path.join(out_folder, name)) else None
    d["sources"] = sources
    for s in d["steps"]:
        s.pop("screenshot", None)
        s.pop("describe", None)
    d.pop("folder", None)
    shutil.copy2(os.path.join(rec_folder, "start.pyf"), os.path.join(out_folder, "start.pyf"))
    path = os.path.join(out_folder, "recording.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=1)
    return path


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(prog="python -m pyfigures.gui.bug_recorder",
                                 description="PyFigures bug recordings (Help > Debug > Record a bug)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list", help="list the recordings, newest first")
    show = sub.add_parser("show", help="print one recording, step by step")
    show.add_argument("path")
    mk = sub.add_parser("make-test", help="turn a recording into a regression test folder")
    mk.add_argument("path")
    mk.add_argument("out")
    a = ap.parse_args(argv)
    if a.cmd == "list":
        for r in list_recordings():
            print(f"{r['path']}  {r['recorded']}  {r['steps']} steps  {r['errors']} errors  "
                  f"{r['what_went_wrong'][:60]}")
    elif a.cmd == "show":
        d = read_recording(a.path)
        print("What went wrong:", d["notes"].get("what_went_wrong"))
        print("Expected:", d["notes"].get("expected"))
        for s in d["steps"]:
            mark = " <-- " if s["n"] in d["notes"].get("bad_steps", []) else "     "
            print(f"{s['n']:3d}{mark}{s['describe']}")
    else:
        print(make_test(a.path, a.out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
