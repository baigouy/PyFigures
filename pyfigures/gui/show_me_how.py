"""GUI side of “Show me how” (registry and client: pyfigures/guides.py).

GuideRunner turns an authored guide into TutorialSteps on the window's own
TutorialController: the real menu actions are looked up live and outlined one
level at a time, the canvas is spotlit for selection / right-click steps, and
the bubble's close button ends the guide. Nothing here edits the figure: each
step only watches for what the user did (a menu opened, a dialog opened, a
split row appeared, the LUTs of the selected image changed…).

GuideMailbox is the window's end of the local request folder that the MCP
tools and the command line write to (see pyfigures.guides).
"""
from __future__ import annotations

import json
import os
import time
import uuid

from qtpy.QtCore import QObject, Qt, QTimer
from qtpy.QtWidgets import QApplication, QFrame

from pyfigures import guides as _guides
from pyfigures.gui.tutorial import TutorialStep, _image_stack, _is_channel_panel


def _clean(text: str) -> str:
    return " ".join(str(text).replace("&", "").replace("...", "…").split()).casefold()


def find_action(menu, title):
    """The QAction called *title* in *menu* (a QMenu or the QMenuBar), or
    LookupError: a guide never invents a route the GUI does not have."""
    want = _clean(title)
    for action in menu.actions():
        if _clean(action.text()) == want:
            return action
    raise LookupError(f"menu entry not found: {title!r}")


def resolve_menu_path(win, path):
    """[(container, action), ...] for a menu path such as
    ['Annotations', 'Stack views', 'Channel split (each channel + merge)…']."""
    out = []
    container = win.menuBar
    for i, title in enumerate(path):
        action = find_action(container, title)
        out.append((container, action))
        if i < len(path) - 1:
            container = action.menu()
            if container is None:
                raise LookupError(f"{title!r} is not a submenu")
    return out


def _selected(win):
    sel = win.paint.EZFIG_panel.selected_shape
    if isinstance(sel, list):
        sel = sel[0] if len(sel) == 1 else None
    return sel


def _selected_image(win, channel=False):
    from batoolset.drawings.shapes.image2d import Image2D
    sel = _selected(win)
    if not isinstance(sel, Image2D):
        return None
    if channel:
        try:
            if not (isinstance(sel.filename, str) and os.path.isfile(sel.filename)
                    and _is_channel_panel(sel)):
                return None
        except Exception:
            return None
    return sel


def _modal_open():
    return QApplication.activeModalWidget() is not None


class GuideRunner:
    """Runs one guide at a time on the window's TutorialController."""

    def __init__(self, win):
        self.win = win
        self.controller = win._tutorial
        self.guide_id = None
        self.steps = None
        self.completed = False
        self.cancelled = False
        self._anchors = []
        self._target_image = None
        self._baseline = None
        self._saw_dialog = False
        self._image_state0 = None

    # ---- results the guides watch for -----------------------------------
    def _snapshot(self):
        imgs = list(_image_stack(self.win))
        insets = 0
        bars = set()
        from batoolset.drawings.shapes.scalebar import ScaleBar
        from batoolset.drawings.shapes.image2d import Image2D
        for img in imgs:
            for ann in (img.annotations or []):
                if isinstance(ann, ScaleBar):
                    bars.add(id(ann))     # new or replaced bars are new objects
                elif isinstance(ann, Image2D) and getattr(
                        ann, "fraction_of_parent_image_width_if_image_is_inset", None):
                    insets += 1
        splits = sum(1 for i in imgs if "channel split of" in str(getattr(i, "user_comments", "")))
        return {"images": len(imgs), "insets": insets, "bars": bars, "splits": splits}

    def _image_state(self, img):
        if img is None:
            return None
        return (repr(getattr(img, "LUTs", None)),
                tuple(getattr(img, a, 0) or 0 for a in
                      ("crop_left", "crop_right", "crop_top", "crop_bottom", "theta")))

    def _done(self, kind):
        b = self._baseline or {}
        now = self._snapshot()
        if kind == "split_created":
            return now["splits"] >= b.get("splits", 0) + 2
        if kind == "scalebar_added":
            return bool(now["bars"]) and now["bars"] != b.get("bars", set())
        if kind == "inset_added":
            return now["insets"] > b.get("insets", 0)
        if kind == "panel_added":
            return now["images"] > b.get("images", 0)
        if kind in ("lut_changed", "crop_changed"):
            img = self._target_image
            if img is None or self._image_state0 is None:
                return False
            k = 0 if kind == "lut_changed" else 1
            return self._image_state(img)[k] != self._image_state0[k]
        if kind == "dialog_closed":
            if _modal_open():
                self._saw_dialog = True
                return False
            return self._saw_dialog
        return False

    # ---- highlight helpers -----------------------------------------------
    def _anchor(self, container, action, fallback):
        frame = QFrame(container)
        frame.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        frame.setStyleSheet("background: transparent; border: 2px solid #38bdf8; border-radius: 3px;")
        frame.hide()
        self._anchors.append(frame)

        def target(win):
            rect = container.actionGeometry(action)
            if not container.isVisible() or rect.isEmpty():
                return fallback(win)
            frame.setGeometry(rect.adjusted(0, 0, -1, -1))
            frame.show()
            frame.raise_()
            return frame
        return target

    def _menu_steps(self, path, final_check):
        chain = resolve_menu_path(self.win, path)
        steps = []
        prev_target = lambda w: w.menuBar
        for i, (container, action) in enumerate(chain):
            last = i == len(chain) - 1
            target = self._anchor(container, action, prev_target)
            label = action.text().replace("&", "")
            if last:
                check = final_check
                msg = f"Click <b>{label}</b>."
            else:
                sub = action.menu()
                check = (lambda w, m=sub: m.isVisible())
                msg = (f"Click <b>{label}</b> in the menu bar." if i == 0
                       else f"Open <b>{label}</b>.")
            steps.append(TutorialStep(label, msg, get_target=target,
                                      completion_check=check, auto_advance=True))
            prev_target = target
        return steps

    # ---- public API ------------------------------------------------------
    def start(self, guide_id):
        g = _guides.GUIDES[guide_id]
        self.stop()
        self.controller.stop()      # a guide replaces any tutorial that was running
        done_kind = g["done"]
        self.guide_id = guide_id
        self.completed = False
        self.cancelled = False
        self._saw_dialog = False
        self._target_image = None
        self._image_state0 = None
        self._baseline = self._snapshot()
        canvas = lambda w: w.paint.EZFIG_panel

        def done_check(w):
            if self.completed:
                return True
            ok = self._done(done_kind)
            if ok:
                self.completed = True
                # the user may have taken a shortcut (another menu, a key):
                # whatever step is showing, the guide ends shortly after
                QTimer.singleShot(1500, self._finish_if_active)
            return ok

        steps = []
        for spec in g["steps"]:
            if "select" in spec:
                channel = spec["select"] == "channel_image"

                def select_check(w, channel=channel):
                    img = _selected_image(w, channel)
                    if img is None:
                        return False
                    if self._target_image is not img:
                        self._target_image = img
                        self._image_state0 = self._image_state(img)
                    return True
                steps.append(TutorialStep("Select the image", spec["text"], get_target=canvas,
                                          completion_check=select_check, auto_advance=True))
            elif "menu" in spec:
                steps.extend(self._menu_steps(
                    spec["menu"], lambda w: _modal_open() or done_check(w)))
            elif "context" in spec:
                steps.append(TutorialStep("Open it from the image", spec["context"],
                                          get_target=canvas,
                                          completion_check=lambda w: _modal_open() or done_check(w),
                                          auto_advance=True))
            elif "dialog" in spec:
                steps.append(TutorialStep(
                    "Finish in the dialog", spec["dialog"],
                    get_target=lambda w: QApplication.activeModalWidget() or w.paint.EZFIG_panel,
                    completion_check=done_check, auto_advance=True))
        for s in steps:
            s.title = f"{g['title']}: {s.title}"
            own = s.completion_check
            if own is not done_check:      # the result also completes every step
                s.completion_check = (lambda w, own=own: done_check(w) or bool(own and own(w)))
        self.steps = steps
        bubble = self.controller._bubble
        try:
            bubble.skip_requested.disconnect(self._on_close_clicked)
        except (TypeError, RuntimeError):
            pass
        bubble.skip_requested.connect(self._on_close_clicked)
        self.controller.start(steps)
        return self.status()

    def _finish_if_active(self):
        if self.active() and self.completed:
            self.controller.stop()
            self._cleanup()

    def _on_close_clicked(self):
        if self.active():
            self.cancelled = True
        self._cleanup()

    def active(self):
        return self.steps is not None and self.controller._steps is self.steps

    def stop(self):
        if self.active():
            self.cancelled = not self.completed
            self.controller.stop()
        self._cleanup()

    def _cleanup(self):
        for a in self._anchors:
            a.hide()
            a.deleteLater()
        self._anchors = []
        bubble = self.controller._bubble
        try:
            bubble.skip_requested.disconnect(self._on_close_clicked)
        except (TypeError, RuntimeError):
            pass

    def status(self):
        visible = self.active() and self.controller._bubble.isVisible()
        if self.guide_id is None:
            state = "no_guide"
        elif self.completed:
            state = "completed"
        elif visible:
            state = "guidance_shown"
        elif self.cancelled:
            state = "cancelled"
        else:
            state = "guidance_closed"
        if not visible and self.steps is not None and not self.active():
            self._cleanup()
        return {"status": state, "guide": self.guide_id,
                "title": _guides.GUIDES[self.guide_id]["title"] if self.guide_id else None,
                "step": self.controller._index + 1 if visible else None,
                "steps": len(self.steps or []),
                "step_title": (self.controller._steps[self.controller._index].title
                               if visible else None),
                "user_result_detected": bool(self.completed),
                "operation_executed": False}


class GuideMailbox(QObject):
    """The window's end of ~/.pyfigures/gui_sessions/<pid>_<token>/. Polled on
    the Qt thread; a request can only name a registry guide."""

    MAX_REQUEST_BYTES = 16384

    def __init__(self, win, root=None):
        super().__init__(win)
        self.win = win
        self.runner = GuideRunner(win)
        self.token = uuid.uuid4().hex
        root = root or _guides.sessions_root()
        self.folder = os.path.join(root, f"{os.getpid()}_{self.token[:8]}")
        os.makedirs(self.folder, exist_ok=True)
        self._figure = None
        self._write_session()
        self.timer = QTimer(self)
        self.timer.setInterval(250)
        self.timer.timeout.connect(self.poll)
        self.timer.start()

    def _write_session(self):
        from pyfigures.atomic_io import write_atomic
        self._figure = getattr(self.win, "current_file", None) or ""
        write_atomic(os.path.join(self.folder, "session.json"), json.dumps(
            {"version": 1, "pid": os.getpid(), "token": self.token, "created": time.time(),
             "figure": self._figure}))

    def poll(self):
        if (getattr(self.win, "current_file", None) or "") != self._figure:
            try:
                self._write_session()
            except OSError:
                pass
        try:
            names = sorted(n for n in os.listdir(self.folder) if n.endswith(".request.json"))
        except OSError:
            return
        for name in names:
            path = os.path.join(self.folder, name)
            try:
                if os.path.getsize(path) > self.MAX_REQUEST_BYTES:
                    raise ValueError("request too large")
                with open(path, encoding="utf-8") as f:
                    req = json.load(f)
                if req.get("token") != self.token:
                    raise ValueError("wrong GUI session")
                if abs(time.time() - float(req.get("created", 0))) > 30:
                    raise ValueError("expired request")
                response = self.handle(req.get("action"), req.get("topic"))
            except Exception as e:      # noqa: BLE001 - every failure is answered
                response = {"status": "error", "error": str(e), "operation_executed": False}
            try:
                from pyfigures.atomic_io import write_atomic
                write_atomic(path.replace(".request.json", ".response.json"),
                             json.dumps(response, ensure_ascii=False))
            except OSError:
                pass
            finally:
                try:
                    os.remove(path)
                except OSError:
                    pass

    def handle(self, action, topic=None):
        if action == "show":
            if topic not in _guides.GUIDES:
                return {"status": "unknown_operation", "available": list(_guides.GUIDES),
                        "operation_executed": False}
            try:
                return self.runner.start(topic)
            except LookupError as e:
                return {"status": "target_unavailable", "error": str(e), "guide": topic,
                        "operation_executed": False}
        if action == "status":
            return self.runner.status()
        if action == "close":
            self.runner.stop()
            return self.runner.status()
        raise ValueError(f"unsupported action {action!r}")

    def close(self):
        self.timer.stop()
        self.runner.stop()
        import shutil
        shutil.rmtree(self.folder, ignore_errors=True)
