"""“Show me where to click”: the chat (or Help → Find in menus…) teaches the
GUI instead of clicking for the user.

ClickGuide highlights EVERY entry on the given routes at once (menu bar menus,
the canvas right-click menu, the panel editor's tabs and buttons), opens the
menus down to the point where the routes split, and lets the user follow
whichever route they like and try things. As soon as the figure changes (any
route succeeded, Undo-able), every highlight is removed. Nothing here edits
the figure or clicks for the user.

A route is a list of entry titles, e.g. ["Edit", "Arrange all images in rows…"]
in the menu bar, ["Crop & size", "Reset crop only"] in the right-click menu.
Menu-bar routes are checked against the live menus before anything is shown;
right-click entries are checked when that menu opens (it is built from the
selection) and reported as missing then.
"""
from __future__ import annotations

from qtpy.QtCore import QEvent, QObject, QPoint, Qt, QTimer
from qtpy.QtWidgets import QAbstractButton, QApplication, QFrame, QLabel, QMenu, QTabWidget

HIGHLIGHT = "background: rgba(249, 115, 22, 40); border: 3px solid #f97316; border-radius: 4px;"


def action_title(text) -> str:
    """What a QAction / button / tab shows: '&&' is a literal '&', a single '&'
    marks the mnemonic, a shortcut after a tab is dropped."""
    return str(text).split("\t")[0].replace("&&", "\x00").replace("&", "").replace("\x00", "&")


def clean(title) -> str:
    """A displayed title, comparable: '...' == '…', spaces and case ignored."""
    return " ".join(str(title).replace("...", "…").split()).casefold()


def same(action_text, title) -> bool:
    """Does a QAction text (with its '&' marks) show *title* (as the user reads it)?"""
    return clean(action_title(action_text)) == clean(title)


def menubar_routes_problem(win, routes):
    """None when every menu-bar route exists, else the first missing entry and
    what that level offers (the chat corrects itself instead of guessing)."""
    for route in routes:
        container = win.menuBar
        for depth, title in enumerate(route):
            match = next((a for a in container.actions() if same(a.text(), title)), None)
            if match is None:
                offered = [action_title(a.text()) for a in container.actions()
                           if a.text() and not a.isSeparator()]
                return {"missing": title, "route": route, "offered_here": offered}
            if depth < len(route) - 1:
                container = match.menu()
                if container is None:
                    return {"missing": route[depth + 1], "route": route,
                            "offered_here": [], "note": f"{title!r} is not a submenu"}
    return None


class ClickGuide(QObject):
    """One guidance at a time on a PyFigures window."""

    def __init__(self, win):
        super().__init__(win)
        self.win = win
        self.routes = []
        self.where = None
        self.controls = []
        self.editor_tab = None
        self.open_menus = False
        self.state = "idle"
        self.missing = []
        self._frames = []
        self._depths = {}          # id(QMenu) -> (depth, route indices)
        self._connected = []
        self._fingerprint0 = None
        self._hint = None
        self._timer = QTimer(self)
        self._timer.setInterval(300)
        self._timer.timeout.connect(self._watch)

    # ---- public ---------------------------------------------------------
    def start(self, routes, where="menu", controls=None, editor_tab=None, note=None, open_menus=False):
        """Highlight *routes* (lists of titles) in the menu bar (where='menu'),
        the canvas right-click menu ('context', opened on the current selection)
        or the panel editor ('editor': *editor_tab* and *controls* button titles,
        highlighted when the editor is open). Never moves the mouse pointer; menus
        are opened for the user only with *open_menus* ("show me the right-click
        menu"), otherwise the user opens them and the highlights follow."""
        self.stop()
        routes = [list(r) for r in (routes or []) if r]
        if where not in ("menu", "context", "editor"):
            raise ValueError("where must be 'menu', 'context' or 'editor'")
        if where != "editor" and not routes:
            raise ValueError("give at least one route (a list of menu entry titles)")
        if where == "menu":
            problem = menubar_routes_problem(self.win, routes)
            if problem:
                return {"status": "route_not_found", **problem, "operation_executed": False}
        self.routes = routes
        self.where = where
        self.controls = [c for c in (controls or []) if c]
        self.editor_tab = editor_tab
        self.open_menus = bool(open_menus)
        self.missing = []
        self.state = "guidance_shown"
        self._fingerprint0 = self._fingerprint()
        QApplication.instance().installEventFilter(self)
        self._timer.start()
        self._show_hint(note or self._default_note())
        if where == "menu":
            self._decorate_menubar(open_menus)
        elif where == "context" and open_menus:
            QTimer.singleShot(0, self._open_context_menu)
        elif where == "editor":
            QTimer.singleShot(0, self._decorate_open_windows)
        return self.status()

    def stop(self, state="cancelled"):
        if self.state == "guidance_shown":
            self.state = state
        QApplication.instance().removeEventFilter(self)
        self._timer.stop()
        for frame in self._frames:
            try:
                frame.hide()
                frame.deleteLater()
            except RuntimeError:
                pass
        self._frames = []
        self._depths = {}
        for signal, slot in self._connected:
            try:
                signal.disconnect(slot)
            except (TypeError, RuntimeError):
                pass
        self._connected = []
        if self._hint is not None:
            try:
                self.win.statusBar().clearMessage()
            except Exception:
                pass
            try:
                self._hint.hide()
                self._hint.deleteLater()
            except RuntimeError:
                pass
            self._hint = None

    def status(self):
        return {"status": self.state, "where": self.where, "routes": self.routes,
                "controls": self.controls, "highlighted": len([f for f in self._frames if _alive(f)]),
                "missing_entries": self.missing, "operation_executed": False}

    # ---- success: the figure changed ------------------------------------
    def _fingerprint(self):
        w = self.win
        return (len(getattr(w, "undo_stack", []) or []), getattr(w, "current_index", None),
                getattr(w, "_dirty", None))

    def _watch(self):
        if self.state != "guidance_shown":
            return
        if self._fingerprint() != self._fingerprint0:
            self._succeeded()
            return
        if self.where == "editor":
            # outlines follow the editor's layout, and an editor opened later
            # (by the user, or by the chat) gets them too
            self._decorate_open_windows()

    def _succeeded(self):
        if self.state != "guidance_shown":
            return
        self.stop(state="completed")
        try:
            self.win.statusBar().showMessage("Done: guidance cleared.", 5000)
        except Exception:
            pass

    # ---- highlights -----------------------------------------------------
    def _frame(self, parent, rect, key=None):
        """One outline per thing: shown again (a window laid out twice, a menu
        reopened), the existing outline just follows its new geometry."""
        # the key is stored ON the outline: PyQt may hand back a new Python wrapper
        # for the same tab bar, so id() of a widget is no identity
        key = str(key or (rect.x(), rect.y(), rect.width(), rect.height()))
        old = next((f for f in parent.findChildren(QFrame, "clickGuideHighlight", Qt.FindDirectChildrenOnly)
                    if f.property("clickGuideKey") == key), None)
        if old is not None and _alive(old):
            old.setGeometry(rect.adjusted(-1, -1, 1, 1))
            old.show()
            old.raise_()
            return old
        frame = QFrame(parent)
        frame.setProperty("clickGuideKey", key)
        frame.setObjectName("clickGuideHighlight")
        frame.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        frame.setStyleSheet(HIGHLIGHT)
        frame.setGeometry(rect.adjusted(-1, -1, 1, 1))
        frame.show()
        frame.raise_()
        self._frames.append(frame)
        return frame

    def _connect(self, signal, slot):
        signal.connect(slot)
        self._connected.append((signal, slot))

    def _decorate_menubar(self, open_menus):
        bar = self.win.menuBar
        firsts = {clean(r[0]) for r in self.routes}
        chosen = []
        for action in bar.actions():
            if clean(action_title(action.text())) in firsts:
                self._frame(bar, bar.actionGeometry(action))
                menu = action.menu()
                if menu is not None:
                    idx = {i for i, r in enumerate(self.routes) if same(action.text(), r[0])}
                    self._depths[id(menu)] = (1, idx)
                chosen.append(action)
        if open_menus and len(chosen) == 1 and chosen[0].menu() is not None:
            # one way in: open it, the next level shows its highlights
            menu = chosen[0].menu()
            rect = bar.actionGeometry(chosen[0])
            QTimer.singleShot(0, lambda: self.state == "guidance_shown" and menu.popup(
                bar.mapToGlobal(rect.bottomLeft())))

    def _open_context_menu(self):
        """The canvas's real right-click menu on the current selection."""
        if self.state != "guidance_shown":
            return
        from qtpy.QtGui import QMouseEvent
        canvas = self.win.paint.EZFIG_panel
        sel = canvas.selected_shape
        if isinstance(sel, list):
            sel = sel[0] if sel else None
        if sel is None:
            self._show_hint("Select the object first (click it: a yellow outline appears), then right-click it.")
            return
        point = sel.getRect(all=True).center()
        event = QMouseEvent(QEvent.Type.MouseButtonRelease, point * float(canvas.scale),
                            Qt.MouseButton.RightButton, Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier)
        canvas.update_context_menu_according_to_selection(event, point)

    def eventFilter(self, obj, event):
        if self.state == "guidance_shown" and event.type() == QEvent.Type.Show:
            if isinstance(obj, QMenu):
                QTimer.singleShot(0, lambda m=obj: _alive(m) and self._decorate_menu(m))
            elif self.where == "editor" and obj.isWidgetType() and obj.isWindow():
                QTimer.singleShot(0, lambda w=obj: _alive(w) and self._decorate_window(w))
        return False

    def _decorate_menu(self, menu):
        if self.state != "guidance_shown" or not menu.isVisible():
            return
        known = self._depths.get(id(menu))
        if known is None:
            if self.where == "context" and not self._is_submenu(menu):
                known = (0, set(range(len(self.routes))))       # the right-click menu itself
            else:
                return
        depth, idx = known
        found = {}
        for action in menu.actions():
            if action.isSeparator() or not action.text():
                continue
            here = {i for i in idx if depth < len(self.routes[i]) and same(action.text(), self.routes[i][depth])}
            if not here:
                continue
            found[action] = here
            self._frame(menu, menu.actionGeometry(action))
            sub = action.menu()
            if sub is not None:
                self._depths[id(sub)] = (depth + 1, {i for i in here if depth + 1 < len(self.routes[i])})
        wanted = {clean(self.routes[i][depth]) for i in idx if depth < len(self.routes[i])}
        seen = {clean(action_title(a.text())) for a in found}
        for title in wanted - seen:
            orig = next(self.routes[i][depth] for i in idx
                        if depth < len(self.routes[i]) and clean(self.routes[i][depth]) == title)
            if orig not in self.missing:
                self.missing.append(orig)
        # one way on: open the submenu so the user lands where the routes split
        subs = [a for a in found if a.menu() is not None]
        if self.open_menus and len(found) == 1 and len(subs) == 1:
            action = subs[0]
            menu.setActiveAction(action)
            rect = menu.actionGeometry(action)
            sub = action.menu()
            QTimer.singleShot(0, lambda: self.state == "guidance_shown" and _alive(menu) and menu.isVisible()
                              and sub.popup(menu.mapToGlobal(QPoint(rect.right(), rect.top()))))

    def _is_submenu(self, menu):
        owner = menu.menuAction()
        for widget in (owner.associatedObjects() if hasattr(owner, "associatedObjects") else owner.associatedWidgets()):
            if isinstance(widget, QMenu) and widget is not menu:
                return True
        return menu.parent() is self.win.menuBar or isinstance(menu.parent(), QMenu)

    def _decorate_open_windows(self):
        for w in QApplication.topLevelWidgets():
            if w.isVisible() and w is not self.win:
                self._decorate_window(w)

    def _decorate_window(self, window):
        """The panel editor: its tab and the buttons to use."""
        if self.state != "guidance_shown":
            return
        if self.editor_tab:
            for tabs in window.findChildren(QTabWidget):
                bar = tabs.tabBar()
                for i in range(tabs.count()):
                    if same(tabs.tabText(i), self.editor_tab):
                        self._frame(bar, bar.tabRect(i), key=("tab", i))
        wanted = {clean(c) for c in self.controls}
        for button in window.findChildren(QAbstractButton):
            if clean(action_title(button.text())) in wanted:
                self._frame(button.parentWidget(), button.geometry(), key=("button", button.text()))

    def _default_note(self):
        if self.where == "context":
            return ("Right-click inside the yellow outline: the menu entries to use are outlined in orange. "
                    "Follow any of them; the highlights disappear once it worked.")
        if self.where == "editor":
            return ("Double-click the panel (yellow outline) to open its editor: the tab and buttons to use are "
                    "outlined in orange. The highlights disappear once it worked.")
        return "The menu entries to use are outlined in orange. Follow any of them; the highlights disappear once it worked."

    def _show_hint(self, text):
        try:
            self.win.statusBar().showMessage(text, 0)
        except Exception:
            pass
        if self._hint is None:
            self._hint = QLabel(self.win)
            self._hint.setObjectName("clickGuideHint")
            self._hint.setWordWrap(True)
            self._hint.setStyleSheet("background:#fff7ed;color:#7c2d12;border:2px solid #f97316;"
                                     "border-radius:6px;padding:6px;")
        self._hint.setText("👉 " + text)
        self._hint.setFixedWidth(min(420, max(240, self.win.width() // 3)))
        self._hint.adjustSize()
        self._hint.move(self.win.width() - self._hint.width() - 24, 70)
        self._hint.show()
        self._hint.raise_()


def _alive(obj):
    try:
        obj.objectName()
        return True
    except RuntimeError:
        return False
