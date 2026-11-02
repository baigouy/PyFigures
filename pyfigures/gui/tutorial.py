"""
Interactive tutorial system for PyFigures.

Components
----------
TutorialStep        dataclass for one step (title, message, target, completion check)
TutorialOverlay     full-window transparent QWidget: dim mask + spotlight + pulse ring
HintBubble          floating instruction card with Prev / Next / Skip
TutorialController  drives the sequence, polls for completion, coordinates everything

Built-in tutorials (Help menu)
------------------------------
beginner_steps()     drop images → row → selection → resize → scale bar → lettering → save
medium_steps()       DnD combine → arrow keys → labels → text → template → export
advanced_steps()     shapes, insets, crop/rotate, LUTs, scripted images, consolidate
publication_steps()  batch annotations, the QC menu, caption, submission exports
sharing_steps()      consolidate, review round trip, merge, remap, colour blindness, theme
stacks_steps()       projection, channel split, montage, kymograph, orthogonal views, merge, video
automation_steps()   draft from folder, recipes, library, compare, copy style, alt text, review
poster_steps()       the poster window; album=True the photo album window (PosterWindow)

Steps that need what an earlier step built declare it (``requires``); when
the user skipped that step the bubble says so and "Set it up for me" creates
it from generated sample images (``prepare``).
"""

from batoolset.settings.global_settings import set_UI
set_UI()

from qtpy.QtWidgets import (
    QWidget, QFrame, QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
    QGraphicsDropShadowEffect, QSizePolicy, QApplication, QDialog,
)
from qtpy.QtCore import Qt, QTimer, QRect, QRectF, QPoint, QPointF, QSize, Signal, QObject, QEvent
from qtpy.QtGui import QPainter, QColor, QPen, QBrush, QPixmap, QFont, QPainterPath


# ── helpers ────────────────────────────────────────────────────────────────

def _widget_rect_in(widget, ancestor) -> QRect:
    """Return widget's geometry in ancestor's coordinate space."""
    tl = widget.mapTo(ancestor, QPoint(0, 0))
    return QRect(tl, widget.size())


def _has_group_with_multiple_images(win) -> bool:
    from batoolset.drawings.shapes.group import Group
    from batoolset.drawings.shapes.image2d import Image2D
    for s in win.paint.EZFIG_panel.shapes_to_draw:
        if isinstance(s, Group):
            images = [c for c in s.content if isinstance(c, Image2D)]
            if len(images) >= 2:
                return True
    return False


def _has_scalebar(win) -> bool:
    from batoolset.drawings.shapes.scalebar import ScaleBar
    from batoolset.drawings.shapes.image2d import Image2D
    stack = list(win.paint.EZFIG_panel.shapes_to_draw)
    while stack:
        obj = stack.pop()
        if isinstance(obj, Image2D):
            for ann in (obj.annotations or []):
                if isinstance(ann, ScaleBar):
                    return True
        if hasattr(obj, 'content') and obj.content:
            stack.extend(obj.content)
    return False


def _has_text_annotation(win) -> bool:
    from batoolset.drawings.shapes.txt2d import TAText2D
    from batoolset.drawings.shapes.image2d import Image2D
    stack = list(win.paint.EZFIG_panel.shapes_to_draw)
    while stack:
        obj = stack.pop()
        if isinstance(obj, Image2D):
            for ann in (obj.annotations or []):
                if isinstance(ann, TAText2D) and not ann.is_letter:
                    return True
        if hasattr(obj, 'content') and obj.content:
            stack.extend(obj.content)
    return False


def _has_text_row(win) -> bool:
    """True if any Group with isText exists (labels above/below a row)."""
    from batoolset.drawings.shapes.group import Group
    for s in win.paint.EZFIG_panel.shapes_to_draw:
        if isinstance(s, Group) and s.isText:
            return True
    return False


def _figure_is_template(win) -> bool:
    from batoolset.drawings.shapes.image2d import Image2D
    images = []
    stack = list(win.paint.EZFIG_panel.shapes_to_draw)
    while stack:
        obj = stack.pop()
        if isinstance(obj, Image2D):
            images.append(obj)
        if hasattr(obj, 'content') and obj.content:
            stack.extend(obj.content)
    return bool(images) and all(
        (img.filename is None or img.filename == '@template@') for img in images
    )


def _count_scalebars(win) -> int:
    """Number of image panels carrying a scale bar (walks groups recursively)."""
    from batoolset.drawings.shapes.scalebar import ScaleBar
    from batoolset.drawings.shapes.image2d import Image2D
    n = 0
    stack = list(win.paint.EZFIG_panel.shapes_to_draw)
    while stack:
        obj = stack.pop()
        if isinstance(obj, Image2D):
            if any(isinstance(a, ScaleBar) for a in (obj.annotations or [])):
                n += 1
        if hasattr(obj, 'content') and obj.content:
            stack.extend(obj.content)
    return n


def _has_caption_sidecar(win) -> bool:
    """True once a figure caption has been stored (File → Figure caption)."""
    import os
    f = getattr(win, 'current_file', None)
    if not f:
        return False
    return os.path.isfile(os.path.splitext(f)[0] + '.caption.json')


# ══════════════════════════════════════════════════════════════════════════════
# TutorialStep
# ══════════════════════════════════════════════════════════════════════════════

class TutorialStep:
    """One step in a tutorial sequence.

    Parameters
    ----------
    title           Short bold heading shown in the hint bubble.
    message         Full instruction text (HTML allowed).
    get_target      callable(win) → QWidget or None.  Widget to spotlight.
    completion_check  callable(win) → bool.  Returns True when step is done.
                    If None the user must click Next manually. A check that
                    remembers a starting value exposes .reset(), called each
                    time the step is entered.
    auto_advance    If True, step advances automatically 1 s after completion.
    requires        callable(win) → bool: what the step needs on the canvas
                    (usually made by an earlier step). When it is False — the
                    user skipped that step — the bubble says so (requires_text)
                    and, if *prepare* is given, offers "Set it up for me".
    prepare         callable(win) that creates what *requires* checks for.
    samples         callable(win) → HTML: for a step whose dialog asks for
                    files the user may not have (a CSV, another figure, a
                    reviewed copy…), writes sample ones and says where they
                    are; offered as "Give me sample files".
    """

    def __init__(self, title, message, get_target=None,
                 completion_check=None, auto_advance=True, on_show=None,
                 requires=None, requires_text='', prepare=None, samples=None):
        self.title = title
        self.message = message
        self.get_target = get_target
        self.completion_check = completion_check
        self.auto_advance = auto_advance
        self.on_show = on_show  # optional callable(win) invoked when step becomes current
        self.requires = requires
        self.requires_text = requires_text
        self.prepare = prepare
        self.samples = samples


# ══════════════════════════════════════════════════════════════════════════════
# TutorialOverlay
# ══════════════════════════════════════════════════════════════════════════════

class TutorialOverlay(QWidget):
    """Transparent full-window widget that draws the dim mask, spotlight and pulse."""

    def __init__(self, parent):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self.setWindowFlags(Qt.SubWindow)
        self._target_rect: QRect | None = None
        self._pulse = 0.0          # 0.0 → 1.0, drives ring animation
        self._done = False         # green tint when step complete

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(40)      # ~25 fps

    def set_target(self, rect: QRect | None, done: bool = False):
        self._target_rect = rect
        self._done = done
        self.update()

    def _tick(self):
        self._pulse = (self._pulse + 0.025) % 1.0
        if self._target_rect:
            self.update()

    # ── painting ────────────────────────────────────────────────────────────

    def paintEvent(self, event):
        if not self.isVisible():
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        if self._target_rect is None:
            # No target: gentle full-screen tint only
            painter.fillRect(self.rect(), QColor(0, 0, 0, 80))
            painter.end()
            return

        # ── Step 1: dim mask with spotlight hole via QPixmap ──────────────
        px = QPixmap(self.size())
        px.fill(QColor(0, 0, 0, 0))

        pp = QPainter(px)
        pp.setRenderHint(QPainter.Antialiasing)
        pp.fillRect(px.rect(), QColor(0, 0, 0, 140))

        margin = 12
        spotlight = QRectF(self._target_rect).adjusted(-margin, -margin, margin, margin)

        pp.setCompositionMode(QPainter.CompositionMode_Clear)
        pp.setBrush(QBrush(Qt.transparent))
        pp.setPen(Qt.NoPen)
        pp.drawRoundedRect(spotlight, 10, 10)
        pp.end()

        painter.drawPixmap(0, 0, px)

        # ── Step 2: spotlight border ──────────────────────────────────────
        border_color = QColor('#4ade80') if self._done else QColor('#6c9fff')
        painter.setPen(QPen(border_color, 2.5))
        painter.setBrush(Qt.NoBrush)
        painter.drawRoundedRect(spotlight, 10, 10)

        # ── Step 3: animated pulse rings ─────────────────────────────────
        if not self._done:
            ring_color = QColor('#6c9fff')
            center = QPointF(self._target_rect.center())
            base_r = max(self._target_rect.width(), self._target_rect.height()) / 2 + margin
            for i in range(3):
                phase = (self._pulse + i / 3.0) % 1.0
                r = base_r + phase * 30
                alpha = int(200 * (1.0 - phase))
                ring_color.setAlpha(alpha)
                painter.setPen(QPen(ring_color, 1.5))
                painter.drawEllipse(center, r, r)
        else:
            # Done checkmark circle
            center = QPointF(self._target_rect.center())
            base_r = max(self._target_rect.width(), self._target_rect.height()) / 2 + margin
            pulse_r = base_r + 8 + 4 * abs(0.5 - (self._pulse % 1.0)) * 2
            painter.setPen(QPen(QColor('#4ade80'), 2))
            painter.drawEllipse(center, pulse_r, pulse_r)

        painter.end()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update()


# ══════════════════════════════════════════════════════════════════════════════
# HintBubble
# ══════════════════════════════════════════════════════════════════════════════

class HintBubble(QFrame):
    """Floating instruction card."""

    next_requested = Signal()
    prev_requested = Signal()
    skip_requested = Signal()
    prepare_requested = Signal()
    samples_requested = Signal()

    _STYLE = """
        QLabel#needs_label {
            color: #fbbf24;
            font-size: 12px;
        }
        QPushButton#btn_prepare {
            background: #92400e;
            color: #fef3c7;
            border: none;
            border-radius: 6px;
            padding: 5px 12px;
            font-size: 12px;
        }
        QPushButton#btn_prepare:hover { background: #b45309; }
        HintBubble {
            background: #1e293b;
            border: 1px solid #334155;
            border-radius: 12px;
        }
        QLabel#step_counter {
            color: #64748b;
            font-size: 12px;
        }
        QLabel#title {
            color: #f1f5f9;
            font-size: 15px;
            font-weight: bold;
        }
        QLabel#message {
            color: #cbd5e1;
            font-size: 13px;
        }
        QLabel#done_label {
            color: #4ade80;
            font-size: 13px;
            font-weight: bold;
        }
        QPushButton#btn_next {
            background: #3b82f6;
            color: white;
            border: none;
            border-radius: 6px;
            padding: 6px 18px;
            font-size: 13px;
            font-weight: bold;
        }
        QPushButton#btn_next:hover { background: #2563eb; }
        QPushButton#btn_prev {
            background: #334155;
            color: #94a3b8;
            border: none;
            border-radius: 6px;
            padding: 6px 12px;
            font-size: 13px;
        }
        QPushButton#btn_prev:hover { background: #475569; color: #f1f5f9; }
        QPushButton#btn_skip {
            background: transparent;
            color: #475569;
            border: none;
            font-size: 12px;
        }
        QPushButton#btn_skip:hover { color: #94a3b8; }
    """

    def __init__(self, parent):
        super().__init__(parent)
        # Use SubWindow (child widget) instead of Qt.Window so that move() works
        # in parent-relative coordinates and the WM never overrides our position.
        self.setWindowFlags(Qt.SubWindow)
        self.setFixedWidth(440)
        self.setStyleSheet(self._STYLE)
        self._drag_pos = None

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(24)
        shadow.setOffset(0, 4)
        shadow.setColor(QColor(0, 0, 0, 160))
        self.setGraphicsEffect(shadow)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(6)

        self._counter = QLabel()
        self._counter.setObjectName('step_counter')
        layout.addWidget(self._counter)

        self._title = QLabel()
        self._title.setObjectName('title')
        self._title.setWordWrap(True)
        layout.addWidget(self._title)

        self._message = QLabel()
        self._message.setObjectName('message')
        self._message.setWordWrap(True)
        self._message.setTextFormat(Qt.RichText)
        layout.addWidget(self._message)

        self._done_label = QLabel('✓  Done!  Click Next to continue.')
        self._done_label.setObjectName('done_label')
        self._done_label.hide()
        layout.addWidget(self._done_label)

        # shown when the step needs something an earlier (skipped) step makes
        self._needs_label = QLabel()
        self._needs_label.setObjectName('needs_label')
        self._needs_label.setWordWrap(True)
        self._needs_label.setTextFormat(Qt.RichText)
        self._needs_label.hide()
        layout.addWidget(self._needs_label)
        self._btn_prepare = QPushButton('Set it up for me')
        self._btn_prepare.setObjectName('btn_prepare')
        self._btn_prepare.setToolTip('Creates what this step needs (with small sample images if '
                                     'required), so you can carry on even after skipping a step.')
        self._btn_prepare.clicked.connect(self.prepare_requested)
        self._btn_prepare.hide()
        layout.addWidget(self._btn_prepare, 0, Qt.AlignLeft)

        # steps whose dialog asks for files the user may not have
        self._btn_samples = QPushButton('Give me sample files')
        self._btn_samples.setObjectName('btn_prepare')
        self._btn_samples.setToolTip('Writes small sample files for this step and says where they are.')
        self._btn_samples.clicked.connect(self.samples_requested)
        self._btn_samples.hide()
        layout.addWidget(self._btn_samples, 0, Qt.AlignLeft)
        self._samples_label = QLabel()
        self._samples_label.setObjectName('needs_label')
        self._samples_label.setWordWrap(True)
        self._samples_label.setTextFormat(Qt.RichText)
        self._samples_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self._samples_label.hide()
        layout.addWidget(self._samples_label)

        # ── dots ──
        dots_row = QHBoxLayout()
        dots_row.setSpacing(5)
        self._dots: list[QLabel] = []
        for _ in range(16):        # max steps; extras hidden
            d = QLabel('●')
            d.setStyleSheet('color: #334155; font-size: 8px;')
            d.hide()
            dots_row.addWidget(d)
        dots_row.addStretch()
        layout.addLayout(dots_row)

        # ── buttons ──
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        self._btn_prev = QPushButton('← Prev')
        self._btn_prev.setObjectName('btn_prev')
        self._btn_prev.clicked.connect(self.prev_requested)
        self._btn_next = QPushButton('Next →')
        self._btn_next.setObjectName('btn_next')
        self._btn_next.clicked.connect(self.next_requested)
        self._btn_skip = QPushButton('Exit tutorial')
        self._btn_skip.setObjectName('btn_skip')
        self._btn_skip.clicked.connect(self.skip_requested)
        btn_row.addWidget(self._btn_prev)
        btn_row.addWidget(self._btn_next)
        btn_row.addStretch()
        btn_row.addWidget(self._btn_skip)
        layout.addLayout(btn_row)

        self.adjustSize()
        self._install_drag_filter()

    def _install_drag_filter(self):
        """Forward mouse events from non-interactive children so the bubble is
        draggable everywhere.  Top-level Qt windows do not propagate child mouse
        events to the parent frame, so we need an explicit event filter."""
        for child in self.findChildren(QWidget):
            if not isinstance(child, QPushButton):
                child.installEventFilter(self)
                child.setCursor(Qt.SizeAllCursor)

    def eventFilter(self, obj, event):
        t = event.type()
        if t == QEvent.MouseButtonPress:
            if event.button() == Qt.LeftButton:
                try:
                    self._drag_pos = event.globalPos() - self.pos()
                except AttributeError:
                    self._drag_pos = event.globalPosition().toPoint() - self.pos()
        elif t == QEvent.MouseMove:
            if event.buttons() == Qt.LeftButton and self._drag_pos is not None:
                try:
                    self.move(event.globalPos() - self._drag_pos)
                except AttributeError:
                    self.move(event.globalPosition().toPoint() - self._drag_pos)
                self.raise_()
        elif t == QEvent.MouseButtonRelease:
            self._drag_pos = None
        return False  # don't consume; buttons etc. still receive the event

    def update_step(self, index: int, total: int, step: TutorialStep, done: bool, missing: bool = False,
                    samples_text: str = ''):
        self._counter.setText(f'Step {index + 1} of {total}')
        self._title.setText(step.title)
        self._message.setText(step.message)
        self._done_label.setVisible(done and step.completion_check is not None)
        show_needs = missing and not done
        self._needs_label.setText('⚠  ' + (step.requires_text or 'This step needs the result of an earlier step.'))
        self._needs_label.setVisible(show_needs)
        self._btn_prepare.setVisible(show_needs and step.prepare is not None)
        self._btn_samples.setVisible(step.samples is not None and not show_needs)
        self._samples_label.setVisible(bool(samples_text) and step.samples is not None)
        self._samples_label.setText(samples_text)
        self._btn_prev.setEnabled(index > 0)
        self._btn_next.setText('Finish' if index == total - 1 else 'Next →')

        # update dots
        for i, d in enumerate(self._dots):
            if i < total:
                d.show()
                if i < index:
                    d.setStyleSheet('color: #4ade80; font-size: 8px;')  # done
                elif i == index:
                    d.setStyleSheet('color: #3b82f6; font-size: 10px;')  # current
                else:
                    d.setStyleSheet('color: #334155; font-size: 8px;')  # future
            else:
                d.hide()

        self.adjustSize()

    def reposition(self, target_rect: QRect | None, main_window):
        """Place the bubble at the bottom-right of the main window."""
        w, h = self.width(), self.height()
        margin = 16
        x = max(margin, main_window.width() - w - margin)
        y = max(margin, main_window.height() - h - margin)
        self.move(x, y)
        self.raise_()

    # ── drag to move ─────────────────────────────────────────────────────────

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            try:
                self._drag_pos = event.globalPos() - self.pos()
            except AttributeError:
                self._drag_pos = event.globalPosition().toPoint() - self.pos()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton and self._drag_pos is not None:
            try:
                self.move(event.globalPos() - self._drag_pos)
            except AttributeError:
                self.move(event.globalPosition().toPoint() - self._drag_pos)
            self.raise_()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._drag_pos = None
        super().mouseReleaseEvent(event)


# ══════════════════════════════════════════════════════════════════════════════
# _InDialogHint + _DialogInjector — tutorial panel embedded inside modal dialogs
# ══════════════════════════════════════════════════════════════════════════════

class _InDialogHint(QFrame):
    """Compact tutorial step panel injected as a child widget of modal dialogs.

    X11 WMs refuse to raise any window above a modal dialog regardless of
    WindowStaysOnTopHint, so embedding a child widget is the only reliable
    way to keep tutorial instructions visible inside the annotation editor.
    The panel is draggable and uses a scroll area so no content is cut off.
    """

    _STYLE = """
        _InDialogHint {
            background: #1e293b;
            border: 1.5px solid #3b82f6;
            border-radius: 8px;
        }
        QLabel#dhtitle { color: #f1f5f9; font-size: 12px; font-weight: bold; }
        QLabel#dhmsg   { color: #cbd5e1; font-size: 11px; background: transparent; }
        QScrollArea    { background: transparent; border: none; }
        QWidget#scroll_contents { background: transparent; }
        QScrollBar:vertical { width: 6px; background: #0f172a; border-radius: 3px; }
        QScrollBar::handle:vertical { background: #475569; border-radius: 3px; }
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
    """
    _W = 340  # inner content width

    def __init__(self, step, parent_dialog):
        from qtpy.QtWidgets import QScrollArea
        super().__init__(parent_dialog)
        self.setWindowFlags(Qt.SubWindow)
        self.setStyleSheet(self._STYLE)
        self._drag_pos = None

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(16)
        shadow.setOffset(0, 3)
        shadow.setColor(QColor(0, 0, 0, 160))
        self.setGraphicsEffect(shadow)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(10, 8, 10, 8)
        outer.setSpacing(4)

        title_lbl = QLabel('☰  ' + step.title)
        title_lbl.setObjectName('dhtitle')
        title_lbl.setWordWrap(True)
        title_lbl.setCursor(Qt.SizeAllCursor)   # drag handle only on title row
        title_lbl.installEventFilter(self)
        outer.addWidget(title_lbl)

        # Message in a scroll area so content is never truncated
        msg_lbl = QLabel(step.message)
        msg_lbl.setObjectName('dhmsg')
        msg_lbl.setWordWrap(True)
        msg_lbl.setTextFormat(Qt.RichText)
        msg_lbl.setFixedWidth(self._W)

        # Use QTextDocument to compute the exact wrapped height for HTML content.
        # heightForWidth() is unreliable for rich text on unshown widgets.
        from qtpy.QtGui import QTextDocument
        _doc = QTextDocument()
        _doc.setHtml(step.message)
        _doc.setTextWidth(self._W)
        natural_h = int(_doc.size().height()) + 4
        max_h = min(natural_h, 280)

        contents = QWidget()
        contents.setObjectName('scroll_contents')
        cl = QVBoxLayout(contents)
        cl.setContentsMargins(0, 0, 0, 0)
        cl.addWidget(msg_lbl)

        scroll = QScrollArea()
        scroll.setWidget(contents)
        scroll.setWidgetResizable(True)
        scroll.setFixedHeight(max_h + 4)
        scroll.setFixedWidth(self._W + 16)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        outer.addWidget(scroll)

        self.setFixedWidth(self._W + 36)
        self.adjustSize()

    def reposition(self, dialog):
        """Position at bottom-right corner to keep dialog toolbar clear."""
        margin = 12
        x = max(margin, dialog.width() - self.width() - margin)
        y = max(margin, dialog.height() - self.height() - margin)
        self.move(x, y)

    # ── drag via title label (event filter installed on title_lbl) ────────────

    def eventFilter(self, obj, event):
        t = event.type()
        if t == QEvent.MouseButtonPress:
            if event.button() == Qt.LeftButton:
                try:
                    self._drag_pos = event.globalPos() - self.pos()
                except AttributeError:
                    self._drag_pos = event.globalPosition().toPoint() - self.pos()
        elif t == QEvent.MouseMove:
            if event.buttons() == Qt.LeftButton and self._drag_pos is not None:
                try:
                    new_pos = event.globalPos() - self._drag_pos
                except AttributeError:
                    new_pos = event.globalPosition().toPoint() - self._drag_pos
                p = self.parent()
                if p:
                    new_pos.setX(max(0, min(new_pos.x(), p.width() - self.width())))
                    new_pos.setY(max(0, min(new_pos.y(), p.height() - self.height())))
                self.move(new_pos)
        elif t == QEvent.MouseButtonRelease:
            self._drag_pos = None
        return False


class _DialogInjector(QObject):
    """App-level event filter: embeds _InDialogHint into every QDialog that
    opens while a tutorial is running."""

    def __init__(self, controller):
        super().__init__()
        self._ctrl = controller
        self._hints: dict = {}   # id(dialog) → _InDialogHint

    @staticmethod
    def _still_open(dialog) -> bool:
        """True while *dialog* is a live top-level window. A dialog Qt made
        itself is not tracked by sip: its wrapper survives the C++ object and
        isdeleted() says False (touching it: access violation, seen during
        Review → Import comments). Comparing identities with the live windows
        never touches the dialog itself."""
        return any(w is dialog for w in QApplication.topLevelWidgets())

    def eventFilter(self, obj, event):
        if not hasattr(self, '_hints'):
            return False       # a filter left behind by a controller being torn down
        if isinstance(obj, QDialog):
            t = event.type()
            if t == QEvent.Show:
                QTimer.singleShot(150, lambda d=obj: self._inject(d) if self._still_open(d) else None)
            elif t in (QEvent.Hide, QEvent.Close):
                self._remove(obj)
            elif t == QEvent.Resize:
                hint = self._hints.get(id(obj))
                if hint is not None:
                    hint.reposition(obj)
        return False

    @staticmethod
    def _is_annotation_editor_dialog(dialog):
        """Return True only for the CustomDialog that wraps the annotation editor.

        We deliberately exclude small utility dialogs (LUT selector, script
        warnings, etc.) so the injected hint does not hide their controls.
        """
        mw = getattr(dialog, 'main_widget', None)
        if mw is None:
            return False
        try:
            from pyfigures.gui.annotation_editor import MainWindow
            return isinstance(mw, MainWindow)
        except Exception:
            return False

    def _inject(self, dialog):
        # runs 150 ms after the dialog showed: a quick QInputDialog / QMessageBox
        # may be closed AND deleted by then — touching it raised in this timer
        # slot, which aborts a PyQt6 app
        try:
            from PyQt6 import sip
        except ImportError:
            sip = None
        if sip is not None and sip.isdeleted(dialog):
            return
        try:
            if not dialog.isVisible():
                return
        except RuntimeError:
            return
        key = id(dialog)
        if key in self._hints:
            return
        if not self._ctrl._bubble.isVisible():
            return
        if not self._is_annotation_editor_dialog(dialog):
            return
        step = self._ctrl._current_step()
        hint = _InDialogHint(step, dialog)
        hint.reposition(dialog)
        hint.show()
        hint.raise_()
        self._hints[key] = hint

    def _remove(self, dialog):
        hint = self._hints.pop(id(dialog), None)
        if hint is not None:
            hint.hide()
            hint.setParent(None)
            hint.deleteLater()


# ══════════════════════════════════════════════════════════════════════════════
# TutorialController
# ══════════════════════════════════════════════════════════════════════════════

class TutorialController:
    """Drives a tutorial sequence attached to a main window (EZFIG_GUI)."""

    def __init__(self, win):
        self._win = win
        self._steps: list[TutorialStep] = []
        self._index = 0
        self._done_flag = False        # current step completion state
        self._auto_advance_pending = False

        self._overlay = TutorialOverlay(win)
        self._bubble = HintBubble(win)

        self._bubble.next_requested.connect(self._next)
        self._bubble.prev_requested.connect(self._prev)
        self._bubble.skip_requested.connect(self.stop)
        self._bubble.prepare_requested.connect(self._prepare)
        self._bubble.samples_requested.connect(self._make_samples)
        self._missing = False          # current step's prerequisite is absent
        self._samples_text = {}        # step index → where its sample files are

        # Completion-polling timer
        self._poll = QTimer(win)
        self._poll.setInterval(400)
        self._poll.timeout.connect(self._check_completion)

        # Auto-advance timer (fires once 1.2 s after step complete)
        self._auto_timer = QTimer(win)
        self._auto_timer.setSingleShot(True)
        self._auto_timer.setInterval(1200)
        self._auto_timer.timeout.connect(self._next)

        # Inject a compact hint into every QDialog that opens during the tutorial.
        # X11 WMs block raise_() above modal dialogs, so embedding is the only
        # reliable approach.
        self._dialog_injector = _DialogInjector(self)
        app = QApplication.instance()
        if app is not None:
            app.installEventFilter(self._dialog_injector)

        self._hide()

    # ── public API ──────────────────────────────────────────────────────────

    def start(self, steps: list[TutorialStep]):
        self._steps = steps
        self._index = 0
        self._samples_text = {}
        self._done_flag = False
        self._auto_advance_pending = False
        self._show()
        self._skip_if_already_done()
        self._update_ui(step_changed=True)
        self._poll.start()

    def stop(self):
        self._poll.stop()
        self._auto_timer.stop()
        self._hide()

    # ── internal ────────────────────────────────────────────────────────────

    def _show(self):
        win = self._win
        self._overlay.resize(win.size())
        self._overlay.raise_()
        self._overlay.show()
        self._bubble.show()
        self._bubble.raise_()

    def _hide(self):
        self._overlay.hide()
        self._bubble.hide()

    def _current_step(self) -> TutorialStep:
        return self._steps[self._index]

    def _target_rect(self) -> QRect | None:
        step = self._current_step()
        if step.get_target is None:
            return None
        try:
            widget = step.get_target(self._win)
            if widget is None:
                return None
            return _widget_rect_in(widget, self._win)
        except Exception:
            return None     # a target that is gone must not break the tutorial (slot abort)

    def _requirement_missing(self) -> bool:
        step = self._current_step()
        if step.requires is None:
            return False
        try:
            return not step.requires(self._win)
        except Exception:
            return True

    def _prepare(self):
        """"Set it up for me": build what the current step needs."""
        step = self._current_step()
        if step.prepare is None:
            return
        try:
            step.prepare(self._win)
        except Exception:
            import traceback
            traceback.print_exc()
        self._update_ui()

    def _make_samples(self):
        """"Give me sample files": write the inputs the step's dialog asks for."""
        step = self._current_step()
        if step.samples is None:
            return
        try:
            text = step.samples(self._win)
        except Exception as e:
            import traceback
            traceback.print_exc()
            text = f'Could not write the sample files: {e}'
        self._samples_text[self._index] = text
        self._update_ui()

    def _update_ui(self, step_changed: bool = False):
        win = self._win
        self._overlay.resize(win.size())

        step = self._current_step()
        if step_changed:
            reset = getattr(step.completion_check, 'reset', None)
            if reset is not None:
                reset()      # a re-entered step starts from the current state

        rect = self._target_rect()
        self._overlay.set_target(rect, self._done_flag)

        self._missing = self._requirement_missing()
        self._bubble.update_step(self._index, len(self._steps), step, self._done_flag, self._missing,
                                 self._samples_text.get(self._index, ''))
        self._bubble.reposition(rect, win)

        if step_changed and step.on_show is not None:
            try:
                step.on_show(win)
            except Exception:
                pass

    def _check_completion(self):
        step = self._current_step()
        if self._requirement_missing() != self._missing:
            self._update_ui()                  # prerequisite appeared / vanished
        if step.completion_check is None:
            return
        try:
            completed = step.completion_check(self._win)
        except Exception:
            return

        if completed and not self._done_flag:
            self._done_flag = True
            self._update_ui()
            if step.auto_advance and not self._auto_advance_pending:
                self._auto_advance_pending = True
                self._auto_timer.start()

    def _skip_if_already_done(self):
        """Silently advance past steps whose completion check is already True on entry."""
        while self._index < len(self._steps) - 1:
            step = self._current_step()
            if step.completion_check is None or not step.auto_advance:
                break
            try:
                already_done = step.completion_check(self._win)
            except Exception:
                break
            if not already_done:
                break
            self._index += 1

    def _next(self):
        self._auto_timer.stop()
        self._auto_advance_pending = False
        if self._index >= len(self._steps) - 1:
            self.stop()
            return
        self._index += 1
        self._done_flag = False
        self._skip_if_already_done()
        self._update_ui(step_changed=True)

    def _prev(self):
        self._auto_timer.stop()
        self._auto_advance_pending = False
        if self._index > 0:
            self._index -= 1
            self._done_flag = False
            self._update_ui(step_changed=True)

    def handle_resize(self):
        """Call from the main window's resizeEvent."""
        if self._overlay.isVisible():
            self._overlay.resize(self._win.size())
            self._update_ui()


# ══════════════════════════════════════════════════════════════════════════════
# Tutorial definitions
# ══════════════════════════════════════════════════════════════════════════════

def _selected_shape(win):
    """Return the currently selected shape on the canvas, or None."""
    try:
        return win.paint.EZFIG_panel.selected_shape
    except Exception:
        return None


def _is_any_selected(win) -> bool:
    return _selected_shape(win) is not None


def _is_none_selected(win) -> bool:
    return _selected_shape(win) is None


def _is_group_selected(win) -> bool:
    from batoolset.drawings.shapes.group import Group
    s = _selected_shape(win)
    return isinstance(s, Group)


def _is_image_in_group_selected(win) -> bool:
    """True when the selection is an Image2D that lives inside a Group (nested selection)."""
    from batoolset.drawings.shapes.image2d import Image2D
    from batoolset.drawings.shapes.group import Group
    s = _selected_shape(win)
    if s is None or isinstance(s, Group):
        return False
    return isinstance(s, Image2D)


def _has_two_single_images(win) -> bool:
    """True when at least 2 Image2D objects sit at the top level (not inside a Group)."""
    from batoolset.drawings.shapes.image2d import Image2D
    from batoolset.drawings.shapes.group import Group
    singles = [s for s in win.paint.EZFIG_panel.shapes_to_draw
               if isinstance(s, Image2D) and not isinstance(s, Group)]
    return len(singles) >= 2


def _has_group_with_3_or_more_images(win) -> bool:
    from batoolset.drawings.shapes.group import Group
    from batoolset.drawings.shapes.image2d import Image2D
    for s in win.paint.EZFIG_panel.shapes_to_draw:
        if isinstance(s, Group):
            if len([c for c in s.content if isinstance(c, Image2D)]) >= 3:
                return True
    return False


def _make_arrow_key_check(required_presses=2):
    """Returns a check that becomes True after N arrow-key shortcut activations.

    Arrow keys are handled via QShortcut (ApplicationShortcut context) so they
    never appear as QEvent.KeyPress on any widget.  We connect directly to the
    shortcuts' activated signals instead.
    """
    count = [0]
    connected = [False]

    def _increment():
        count[0] += 1

    def check(win):
        if not connected[0]:
            for attr in ('_up_shortcut', '_down_shortcut',
                         '_left_shortcut', '_right_shortcut'):
                sc = getattr(win, attr, None)
                if sc is not None:
                    sc.activated.connect(_increment)
            connected[0] = True
        return count[0] >= required_presses

    def reset():
        count[0] = 0

    check.reset = reset
    return check


def _make_count_increase_check(counter):
    """True once counter(win) grows past its value when the step was entered
    (e.g. a split / montage added panels)."""
    initial = [None]

    def check(win):
        current = counter(win)
        if initial[0] is None:
            initial[0] = current
            return False
        return current > initial[0]

    def reset():
        initial[0] = None

    check.reset = reset
    return check


def _make_label_edited_check():
    """Returns True once any text-row label has changed from its initial content.

    Text-row structure: Group(isText) → [Image2D(isText)] → annotations[0] = TAText2D
    """
    initial = [None]

    def _collect(win):
        from batoolset.drawings.shapes.group import Group
        from batoolset.drawings.shapes.image2d import Image2D
        from batoolset.drawings.shapes.txt2d import TAText2D
        texts = []
        for s in win.paint.EZFIG_panel.shapes_to_draw:
            if isinstance(s, Group) and getattr(s, 'isText', False):
                for c in s.content:
                    if isinstance(c, Image2D) and getattr(c, 'isText', False):
                        if c.annotations:
                            ann = c.annotations[0]
                            if isinstance(ann, TAText2D):
                                try:
                                    texts.append(ann.doc.toPlainText())
                                except Exception:
                                    pass
        return texts

    def check(win):
        current = _collect(win)
        if initial[0] is None:
            initial[0] = list(current)
            return False
        return current != initial[0]

    def reset():
        initial[0] = None

    check.reset = reset
    return check


def _image_stack(win):
    """Yield every leaf Image2D on the canvas (skips Groups)."""
    from batoolset.drawings.shapes.image2d import Image2D
    from batoolset.drawings.shapes.group import Group
    stack = list(win.paint.EZFIG_panel.shapes_to_draw)
    while stack:
        obj = stack.pop()
        if isinstance(obj, Image2D) and not isinstance(obj, Group):
            yield obj
        if hasattr(obj, 'content') and obj.content:
            stack.extend(obj.content)


def _has_shape_annotation(win) -> bool:
    """True when any image carries a non-text, non-scalebar, non-inset annotation."""
    from batoolset.drawings.shapes.txt2d import TAText2D
    from batoolset.drawings.shapes.scalebar import ScaleBar
    from batoolset.drawings.shapes.image2d import Image2D
    for img in _image_stack(win):
        for ann in (img.annotations or []):
            if not isinstance(ann, (TAText2D, ScaleBar, Image2D)):
                return True
    return False


def _has_inset(win) -> bool:
    """True when any image carries an inset annotation (Image2D with non-zero fraction)."""
    from batoolset.drawings.shapes.image2d import Image2D
    for img in _image_stack(win):
        for ann in (img.annotations or []):
            if isinstance(ann, Image2D) and getattr(ann, 'fraction_of_parent_image_width_if_image_is_inset', None):
                return True
    return False


def _has_cropped_or_rotated_image(win) -> bool:
    """True when any image has a non-zero crop or a non-zero rotation."""
    for img in _image_stack(win):
        for attr in ('crop_left', 'crop_right', 'crop_top', 'crop_bottom'):
            val = getattr(img, attr, None)
            if val is not None and val != 0:
                return True
        theta = getattr(img, 'theta', None)
        if theta is not None and theta != 0:
            return True
    return False


def _has_scripted_image(win) -> bool:
    """True when any image has a custom loading script attached."""
    for img in _image_stack(win):
        if getattr(img, 'custom_loading_script', None):
            return True
    return False


def _make_script_changed_check():
    """Returns True once the script of any image changes from the value it had when the step was entered."""
    initial = [None]

    def _collect(win):
        return [getattr(img, 'custom_loading_script', None) or ''
                for img in _image_stack(win)]

    def check(win):
        current = _collect(win)
        if initial[0] is None:
            initial[0] = list(current)
            return False
        return current != initial[0]

    def reset():
        initial[0] = None

    check.reset = reset
    return check


def _has_lut(win) -> bool:
    """True when any image has a user-defined LUT applied (LUTs attribute is non-empty)."""
    for img in _image_stack(win):
        luts = getattr(img, 'LUTs', None)
        if luts:  # non-None, non-empty list
            return True
    return False


def _has_empty_image(win) -> bool:
    """True when any non-text Image2D with no filename and no script exists (empty placeholder)."""
    from batoolset.drawings.shapes.image2d import Image2D
    from batoolset.drawings.shapes.group import Group
    stack = list(win.paint.EZFIG_panel.shapes_to_draw)
    while stack:
        obj = stack.pop()
        if isinstance(obj, Image2D) and not isinstance(obj, Group):
            if (not getattr(obj, 'isText', False)
                    and getattr(obj, 'filename', None) is None
                    and not getattr(obj, 'custom_loading_script', None)):
                return True
        if hasattr(obj, 'content') and obj.content:
            stack.extend(obj.content)
    return False


_MATPLOTLIB_SCRIPT = (
    'import numpy as np\n'
    'import matplotlib\n'
    'matplotlib.use("Agg")\n'
    'import matplotlib.pyplot as plt\n\n'
    'fig, ax = plt.subplots(figsize=(4, 3), dpi=100)\n'
    'x = np.linspace(0, 2 * np.pi, 200)\n'
    'ax.plot(x, np.sin(x), color="steelblue", label="sin(x)")\n'
    'ax.plot(x, np.cos(x), color="tomato",    label="cos(x)")\n'
    'ax.legend()\n'
    'ax.set_title("Scripted image")\n'
    'fig.tight_layout()\n'
    'fig.canvas.draw()\n'
    'buf = fig.canvas.buffer_rgba()\n'
    'w, h = fig.canvas.get_width_height()\n'
    'self.img = np.frombuffer(buf, dtype=np.uint8).reshape(h, w, 4)[..., :3].copy()\n'
    'plt.close(fig)\n'
)


def _on_show_copy_script(win):
    """Copy the matplotlib example script to the clipboard when the step is shown."""
    try:
        from qtpy.QtWidgets import QApplication
        QApplication.clipboard().setText(_MATPLOTLIB_SCRIPT)
    except Exception:
        pass


def _make_size_change_check():
    """Returns a completion check that becomes True once the figure-width spinner value changes."""
    initial = [None]
    def check(win):
        try:
            current = win.size_spinbox.value()
        except Exception:
            return False
        if initial[0] is None:
            initial[0] = current
            return False
        return current != initial[0]

    def reset():
        initial[0] = None

    check.reset = reset
    return check


def _auto_lettering_off(win) -> bool:
    try:
        return not win.auto_lettering_checkbox.isChecked()
    except Exception:
        return False


def _auto_lettering_on(win) -> bool:
    try:
        return win.auto_lettering_checkbox.isChecked()
    except Exception:
        return False


# ── "Set it up for me": sample content for steps whose prerequisite is missing ──
#
# A tutorial step often needs what an earlier step built (a row, a label row, a
# template…). If the user skipped that step, the bubble names what is missing
# and offers to create it — with small generated sample images, so the
# tutorial never dead-ends and never needs the user's own data.

_DEMO_DIR = [None]
_DEMO_COUNTER = [0]


def _demo_dir():
    import os
    import tempfile
    if _DEMO_DIR[0] is None or not os.path.isdir(_DEMO_DIR[0]):
        _DEMO_DIR[0] = tempfile.mkdtemp(prefix='pyfigures_tutorial_')
    return _DEMO_DIR[0]


def _demo_plane(seed, h=240, w=320):
    """A cell-like test image: bright blobs on a soft gradient (uint8)."""
    import numpy as np
    rng = np.random.default_rng(seed)
    yy, xx = np.mgrid[0:h, 0:w]
    img = 20.0 + 30.0 * xx / float(w)
    for _ in range(12):
        cy = rng.uniform(15, h - 15)
        cx = rng.uniform(15, w - 15)
        r = rng.uniform(6, 18)
        img = img + 170.0 * np.exp(-((yy - cy) ** 2 + (xx - cx) ** 2) / (2.0 * r * r))
    return np.clip(img, 0, 255).astype(np.uint8)


def _demo_image_paths(n, ext='.png'):
    """Write *n* new sample images and return their paths."""
    import os
    from batoolset.img import Img
    paths = []
    for _ in range(n):
        _DEMO_COUNTER[0] += 1
        k = _DEMO_COUNTER[0]
        path = os.path.join(_demo_dir(), f'sample_{k:02d}{ext}')
        Img(_demo_plane(k), dimensions='hw').save(path)
        paths.append(path)
    return paths


def _demo_stack_paths():
    """A 3-channel image and a z-stack — for the stacks tutorial."""
    import os
    import numpy as np
    from batoolset.img import Img
    _DEMO_COUNTER[0] += 1
    k = _DEMO_COUNTER[0]
    channels = np.stack([_demo_plane(k * 10 + c) for c in range(3)], axis=-1)
    c_path = os.path.join(_demo_dir(), f'sample_channels_{k:02d}.tif')
    Img(channels, dimensions='hwc').save(c_path)
    z = np.stack([_demo_plane(k * 10 + 5 + i) for i in range(5)])
    z_path = os.path.join(_demo_dir(), f'sample_zstack_{k:02d}.tif')
    Img(z, dimensions='dhw').save(z_path)
    return [c_path, z_path]


def _demo_movie_path():
    """A 12-frame time-lapse (blobs drifting right)."""
    import os
    import numpy as np
    import tifffile
    _DEMO_COUNTER[0] += 1
    plane = _demo_plane(_DEMO_COUNTER[0])
    frames = np.stack([np.roll(plane, 6 * t, axis=1) for t in range(12)])
    path = os.path.join(_demo_dir(), f'sample_movie_{_DEMO_COUNTER[0]:02d}.tif')
    tifffile.imwrite(path, frames, imagej=True, metadata={'axes': 'TYX'})
    return path


def _when(win, cond, action, timeout_ms=20000):
    """Run action(win) once cond(win) is true (images load in the background)."""
    timer = QTimer(win)
    timer.setInterval(100)
    waited = [0]

    def _tick():
        waited[0] += 100
        try:
            ready = cond(win)
        except Exception:
            ready = False
        if ready or waited[0] >= timeout_ms:
            timer.stop()
            timer.deleteLater()
            if ready:
                try:
                    action(win)
                except Exception:
                    import traceback
                    traceback.print_exc()
    timer.timeout.connect(_tick)
    timer.start()
    return timer


def _groups(win):
    from batoolset.drawings.shapes.group import Group
    return [s for s in win.paint.EZFIG_panel.shapes_to_draw
            if isinstance(s, Group) and not getattr(s, 'isText', False)]


def _has_any_shape(win) -> bool:
    return len(win.paint.EZFIG_panel.shapes_to_draw) > 0


def _has_real_image(win) -> bool:
    """At least one picture panel (not a label, not an empty slot)."""
    return any(not getattr(i, 'isText', False) and i.filename and i.filename != '@template@'
               for i in _image_stack(win))


def _n_images(win) -> int:
    return sum(1 for i in _image_stack(win) if not getattr(i, 'isText', False))


def _has_two_rows(win) -> bool:
    return len([g for g in _groups(win) if len(g.content) >= 2]) >= 2


def _is_saved(win) -> bool:
    return bool(getattr(win, 'current_file', None))


def _prep_images(n=1):
    def prepare(win):
        win.all_images_directly(_demo_image_paths(n))
    return prepare


def _prep_row(n=2):
    def prepare(win):
        win.add_images_to_new_row(_demo_image_paths(n))
    return prepare


def _lone_image(win):
    """The last picture dropped on its own (not in a row), or None."""
    from batoolset.drawings.shapes.image2d import Image2D
    for s in reversed(win.paint.EZFIG_panel.shapes_to_draw):
        if isinstance(s, Image2D) and not getattr(s, 'isText', False):
            return s
    return None


def _prep_row_reusing(n=2):
    """Build the row from the image the previous step dropped plus samples,
    so that image is not left alone beside a separate sample row."""
    def prepare(win):
        target = _lone_image(win)
        if target is None:
            win.add_images_to_new_row(_demo_image_paths(n))
        else:
            win.add_images_combined_with_target(_demo_image_paths(n - 1), target)
    return prepare


# ── "Give me sample files": inputs a step's dialog asks for ──────────────────

def _sample_subdir(name):
    """A new, empty folder for one step's sample files."""
    import os
    _DEMO_COUNTER[0] += 1
    path = os.path.join(_demo_dir(), f'{name}_{_DEMO_COUNTER[0]:02d}')
    os.makedirs(path, exist_ok=True)
    return path


def _where(what, path, then=''):
    import html
    return (f'📁 {what}:<br><code>{html.escape(path)}</code>'
            + (f'<br>{then}' if then else ''))


def _write_sample_csv(path):
    """Measurements per group, one column per group (the layout the plot
    dialog and recipes read)."""
    import numpy as np
    rng = np.random.default_rng(7)
    groups = {'Control': rng.normal(10, 2, 12), 'Mutant A': rng.normal(14, 2, 12),
              'Mutant B': rng.normal(10.5, 2, 12)}
    with open(path, 'w', encoding='utf-8') as f:
        f.write(','.join(groups) + '\n')
        for row in zip(*groups.values()):
            f.write(','.join(f'{v:.2f}' for v in row) + '\n')
    return path


def _copy_images_to(folder, n):
    import os
    import shutil
    out = []
    for p in _demo_image_paths(n):
        dst = os.path.join(folder, os.path.basename(p))
        shutil.copyfile(p, dst)
        out.append(dst)
    return out


def _build_sample_figure(folder, name, caption, n=2):
    """A small saved figure (.pyf) built from a recipe, beside its images."""
    import os
    from pyfigures.recipe import build_figure_from_recipe
    images = [os.path.basename(p) for p in _copy_images_to(folder, n)]
    recipe = os.path.join(folder, f'{name}.yaml')
    with open(recipe, 'w', encoding='utf-8') as f:
        f.write(f'output: {name}.pyf\n')
        f.write(f'caption: "{caption}"\n')
        f.write('label_background: black\n')
        f.write('rows:\n')
        f.write('  - [' + ', '.join(images) + ']\n')
    build_figure_from_recipe(recipe)
    return os.path.join(folder, f'{name}.pyf')


def _samples_csv(win):
    import os
    path = _write_sample_csv(os.path.join(_sample_subdir('csv'), 'cells_per_field.csv'))
    return _where('Sample CSV (three groups of measurements)', path, 'Pick it in the dialog.')


def _samples_channel_files(win):
    import os
    import shutil
    d = _sample_subdir('channels')
    for name, p in zip(('DAPI', 'GFP', 'RFP'), _demo_image_paths(3)):
        shutil.copyfile(p, os.path.join(d, f'cells_{name}.png'))
    return _where('Three channel files (cells_DAPI / _GFP / _RFP.png)', d,
                  'Pick one file per channel.')


def _samples_results_folder(win):
    import os
    d = _sample_subdir('results')
    _copy_images_to(d, 4)
    _write_sample_csv(os.path.join(d, 'cells_per_field.csv'))
    return _where('A results folder (4 images and a CSV)', d, 'Pick this folder in the dialog.')


def _samples_recipe(win):
    import os
    d = _sample_subdir('recipe')
    images = [os.path.basename(p) for p in _copy_images_to(d, 3)]
    _write_sample_csv(os.path.join(d, 'cells_per_field.csv'))
    recipe = os.path.join(d, 'sample_recipe.yaml')
    with open(recipe, 'w', encoding='utf-8') as f:
        f.write('# A sample recipe: open it in a text editor, change a setting and rebuild.\n')
        f.write('output: sample_figure.pyf\n')
        f.write('defaults:\n')
        f.write('  px_to_unit: 0.1                  # micrometres per pixel\n')
        f.write('  scale_bar: {units: 10, unit: "µm"}\n')
        f.write('rows:\n')
        f.write(f'  - [{images[0]}, {images[1]}, {images[2]}]\n')
        f.write('  - - {image: ' + images[0] + ', lut: green}\n')
        f.write('    - {plot: cells_per_field.csv, kind: box, ylabel: "cells / field"}\n')
    return _where('A sample recipe', recipe, 'Pick it in the dialog.')


def _samples_library(win):
    d = _sample_subdir('library')
    _build_sample_figure(d, 'actin_staining', 'Actin staining in wild-type guts.')
    _build_sample_figure(d, 'gfp_timelapse', 'GFP time-lapse of dividing cells.')
    return _where('A small figure library (two figures)', d,
                  'Point the dialog at this folder and search for <b>actin</b> or <b>GFP</b>.')


def _samples_other_figure(win):
    path = _build_sample_figure(_sample_subdir('other_figure'), 'other_figure',
                                'Another figure, white letters on black.')
    return _where('Another figure', path, 'Pick it in the dialog.')


def _samples_older_version(win):
    import os
    dst = os.path.join(_sample_subdir('versions'), 'older_version.pyf')
    win._save_state_to_file(dst)
    return _where('A copy of the figure as it is now', dst,
                  'Change something first (delete a panel, change a LUT…), then compare with this copy.')


def _samples_review(win):
    import os
    from pyfigures.gui.review.html_export import build_review_html
    d = _sample_subdir('review')
    png = os.path.join(d, 'figure.png')
    win._render_png_without_prompt(png)
    comments = [
        {'x': 0.2, 'y': 0.3, 'text': 'Add a scale bar here.', 'author': 'Co-author', 'ts': ''},
        {'x': 0.7, 'y': 0.5, 'w': 0.2, 'h': 0.2, 'text': 'Could this panel be brighter?',
         'author': 'Co-author', 'ts': ''},
    ]
    stem = os.path.splitext(os.path.basename(win.current_file or 'figure'))[0]
    out = os.path.join(d, f'{stem}_reviewed.html')
    with open(out, 'w', encoding='utf-8') as f:
        f.write(build_review_html(png, source_name=stem, comments=comments, author='Co-author'))
    return _where('A reviewed copy, as a co-author would send it back (two comments)', out,
                  'Pick it in the dialog.')


def _samples_moved_images(win):
    import os
    import shutil
    files = sorted({i.filename for i in _image_stack(win)
                    if isinstance(getattr(i, 'filename', None), str) and os.path.isfile(i.filename)})
    if not files:
        return 'The figure has no image files on disk to move.'
    old = os.path.commonpath([os.path.dirname(f) for f in files])
    new = _sample_subdir('moved_images')
    for f in files:
        dst = os.path.join(new, os.path.relpath(f, old))
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copyfile(f, dst)
    import html
    return (f'📁 The figure\'s images were copied to a new folder, as if moved.<br>'
            f'Old path prefix: <code>{html.escape(old)}</code><br>'
            f'New path prefix: <code>{html.escape(new)}</code>')


def _prep_row_if_missing(win, then=None):
    """Make sure a row of 2+ images exists, then run then(win)."""
    if not _has_group_with_multiple_images(win):
        win.add_images_to_new_row(_demo_image_paths(2))
    if then is not None:
        _when(win, _has_group_with_multiple_images, then)


def _select_first_row(win):
    rows = [g for g in _groups(win) if len(g.content) >= 2]
    if rows:
        win.paint.EZFIG_panel.set_current_selection(rows[0])
        win.paint.EZFIG_panel.update()


def _prep_select_row(win):
    _prep_row_if_missing(win, then=_select_first_row)


def _select_image_in_row(win):
    from batoolset.drawings.shapes.image2d import Image2D
    for g in _groups(win):
        imgs = [c for c in g.content if isinstance(c, Image2D)]
        if len(imgs) >= 2:
            win.paint.EZFIG_panel.set_current_selection(imgs[-1])
            win.paint.EZFIG_panel.update()
            return


def _prep_select_image_in_row(win):
    _prep_row_if_missing(win, then=_select_image_in_row)


def _prep_two_rows(win):
    missing = 2 - len([g for g in _groups(win) if len(g.content) >= 2])
    for _ in range(max(0, missing)):
        win.add_images_to_new_row(_demo_image_paths(2))


def _prep_text_row(win):
    def _add(w):
        _select_first_row(w)
        w.paint.EZFIG_panel.associate_text_row(sensitivity='below')
    _prep_row_if_missing(win, then=_add)


def _template_slots(win):
    return [i for i in _image_stack(win)
            if not getattr(i, 'isText', False) and (i.filename is None or i.filename == '@template@')
            and not getattr(i, 'custom_loading_script', None)]


def _has_template_slot(win) -> bool:
    return bool(_template_slots(win))


def _make_template_filled_check():
    """Done once a slot that was empty on entry has received an image (so a
    figure that never was a template does not count as "filled")."""
    initial = [None]

    def check(win):
        current = len(_template_slots(win))
        if initial[0] is None:
            initial[0] = current
            return False
        if current > initial[0]:
            initial[0] = current         # new slots appeared ("Set it up for me")
            return False
        return current < initial[0]

    def reset():
        initial[0] = None

    check.reset = reset
    return check


def _prep_template(win):
    if _has_real_image(win):
        win.templatify_figure()
    else:
        win.add_images_to_new_row(_demo_image_paths(2))
        _when(win, _has_real_image, lambda w: w.templatify_figure())


def _prep_empty_image(win):
    def _add(w):
        from batoolset.drawings.shapes.image2d import Image2D
        panel = w.paint.EZFIG_panel
        rows = [g for g in _groups(w) if len(g.content) >= 2]
        row = rows[0]
        row.content.append(Image2D(None, width=512, height=512))
        panel.set_current_selection(row)
        panel.update_letters_required.emit()
        panel.force_update_size_of_parent.emit(row)
        panel.update()
        panel.undo_redo_save_required.emit()
    _prep_row_if_missing(win, then=_add)


def _prep_save(win):
    win.save_pyfigures()


def _prep_stacks(win):
    win.all_images_directly(_demo_stack_paths())


def _prep_movie(win):
    win.all_images_directly([_demo_movie_path()])


def _has_multichannel_image(win) -> bool:
    for img in _image_stack(win):
        arr = getattr(img, 'img', None)
        if getattr(arr, 'ndim', 0) == 3 and arr.shape[-1] in (2, 3, 4) and not getattr(img, 'isText', False):
            return True
    return False


def _has_stack_image(win) -> bool:
    """A panel with planes beyond one 2-D (+ colour) image: Z, time, channels."""
    for img in _image_stack(win):
        arr = getattr(img, 'img', None)
        if getattr(arr, 'ndim', 0) >= 3 and not getattr(img, 'isText', False):
            return True
    return False


def _has_z_stack(win) -> bool:
    from batoolset.img import guess_dimensions
    for img in _image_stack(win):
        arr = getattr(img, 'img', None)
        if getattr(arr, 'ndim', 0) >= 3:
            dims = guess_dimensions(arr) or ''
            if 'd' in dims or 't' in dims:
                return True
    return False


def _has_projection(win) -> bool:
    return any(getattr(img, 'projection', None) for img in _image_stack(win))


def _has_time_stack(win) -> bool:
    try:
        return bool(win.paint.EZFIG_panel._collect_time_stacks())
    except Exception:
        return False


def beginner_steps() -> list[TutorialStep]:
    return [
        # ── Welcome ───────────────────────────────────────────────────────────
        TutorialStep(
            title='Welcome to PyFigures!',
            message=(
                'Build your first scientific figure in ~10 minutes.<br><br>'
                'You will learn: <b>drop images</b>, <b>selection</b>, '
                '<b>row layout</b>, <b>scale bar</b>, <b>auto-lettering</b>, <b>save</b>.<br><br>'
                'Click <b>Next</b> to begin, or <b>Exit tutorial</b> at any time.'
            ),
            get_target=None,
            completion_check=None,
            auto_advance=False,
        ),

        # ── Drop first image ──────────────────────────────────────────────────
        TutorialStep(
            title='Step 1 — Drop your first image',
            message=(
                'Drag <b>one image file</b> (TIFF, PNG, JPG, CZI…) from your file '
                'manager and <b>drop it onto the canvas</b>.<br><br>'
                'From the pop-up menu choose <b>"➕ As single image(s)"</b>.'
            ),
            get_target=lambda win: win.paint,
            completion_check=_has_any_shape,
            auto_advance=True,
            requires=_has_any_shape,
            requires_text='No image to hand? Use a sample image instead.',
            prepare=_prep_images(1),
        ),

        # # ── Click outside to deselect ─────────────────────────────────────────
        # TutorialStep(
        #     title='Step 2 — Click outside to deselect',
        #     message=(
        #         'The image was auto-selected. '
        #         '<b>Click on an empty area</b> of the canvas to deselect.<br><br>'
        #         '<b>No selection = whole figure</b>: toolbar changes then apply '
        #         'to everything at once — key rule to remember.'
        #     ),
        #     get_target=lambda win: win.paint,
        #     completion_check=_is_none_selected,
        #     auto_advance=True,
        # ),

        # ── Build a row ───────────────────────────────────────────────────────
        TutorialStep(
            title='Step 2 — Build a row',
            message=(
                'A row needs <b>at least two images</b>.<br><br>'
                'Drag <b>one more image</b> and drop it <b>onto your first image</b>, '
                'or drop <b>two or more</b> new images on an empty area of the canvas.<br><br>'
                'From the pop-up menu choose <b>"↔ To row"</b>.<br>'
                'The images are grouped side-by-side into a row.'
            ),
            get_target=lambda win: win.paint,
            completion_check=_has_group_with_multiple_images,
            auto_advance=True,
            requires=_has_group_with_multiple_images,
            requires_text='No second image to hand? Make the row from your image and a sample image.',
            prepare=_prep_row_reusing(2),
        ),

        # ── Click once → select group ─────────────────────────────────────────
        TutorialStep(
            title='Step 3 — Select the whole row',
            message=(
                '<b>Click once</b> on any image in the row.<br>'
                'The <b>entire row</b> is selected — toolbar changes apply to all images.<br><br>'
                'Try the <b>arrow keys</b> to move the whole row up or down among the rows.'
            ),
            get_target=lambda win: win.paint,
            completion_check=_is_group_selected,
            auto_advance=True,
            requires=_has_group_with_multiple_images,
            requires_text='This step needs a row of images (Step 2).',
            prepare=lambda win: _prep_row_if_missing(win),
        ),

        # ── Click again → select individual image ─────────────────────────────
        TutorialStep(
            title='Step 4 — Focus on a single image',
            message=(
                'With the row selected, <b>click again</b> on one image.<br>'
                'Only <b>that image</b> is now selected.<br><br>'
                'Use the <b>arrow keys</b> to move it left or right within its row '
                '(with the whole row selected they move the row instead).<br><br>'
                'Click <b>outside</b> to return to no selection.'
            ),
            get_target=lambda win: win.paint,
            completion_check=_is_image_in_group_selected,
            auto_advance=True,
            requires=_has_group_with_multiple_images,
            requires_text='This step needs a row of images (Step 2).',
            prepare=lambda win: _prep_row_if_missing(win),
        ),

        # ── Click outside → nothing selected ─────────────────────────────────
        TutorialStep(
            title='Step 5 — No selection = everything',
            message=(
                '<b>Click outside</b> all images.<br><br>'
                'With <b>nothing selected</b>, any toolbar change affects the '
                '<b>entire figure</b>. This is the same as "select all".<br>'
                'If an image or row were selected, only that element would change.'
            ),
            get_target=lambda win: win.paint,
            completion_check=_is_none_selected,
            auto_advance=True,
            requires=_has_any_shape,
            requires_text='This step needs something on the canvas (Steps 1–2).',
            prepare=_prep_row(2),
        ),

        # ── Resize whole figure ───────────────────────────────────────────────
        TutorialStep(
            title='Step 6 — Resize the whole figure',
            message=(
                'Type a new value in the <b>Figure width</b> spinner (toolbar) '
                'and press <b>Enter</b>.<br><br>'
                'Because nothing is selected, every element resizes together.'
            ),
            get_target=lambda win: win.size_spinbox,
            completion_check=_make_size_change_check(),
            auto_advance=True,
            requires=_has_any_shape,
            requires_text='This step needs something on the canvas (Steps 1–2).',
            prepare=_prep_row(2),
        ),

        # ── Scale bar (via Edit Image dialog) ─────────────────────────────────
        TutorialStep(
            title='Step 7 — Add a scale bar',
            message=(
                'Scale bars are added via <b>Edit Image</b>.<br><br>'
                '1. <b>Click</b> once on the <b>row</b>, then <b>click</b> again on one <b>image</b> '
                '<i>(or double-click the image directly)</i>.<br>'
                '2. <b>Right-click</b> the image → <b>"Edit Image"</b>.<br>'
                '3. In the <b>Annotations</b> tab click the <b>"ScaleBar"</b> button.<br>'
                '4. Set bar size and legend, click Ok.'
            ),
            get_target=lambda win: win.paint,
            completion_check=_has_scalebar,
            auto_advance=True,
            requires=_has_real_image,
            requires_text='This step needs an image on the canvas (Step 1).',
            prepare=_prep_images(1),
        ),

        # ── Lettering: uncheck ────────────────────────────────────────────────
        TutorialStep(
            title='Step 8 — Toggle auto-lettering off',
            message=(
                '<b>Uncheck</b> the <b>Letters</b> checkbox in the toolbar.<br><br>'
                'Panel letters (a, b, c…) disappear — see the figure without labels.'
            ),
            get_target=lambda win: win.auto_lettering_checkbox,
            completion_check=_auto_lettering_off,
            auto_advance=True,
        ),

        # ── Lettering: recheck ────────────────────────────────────────────────
        TutorialStep(
            title='Step 9 — Toggle auto-lettering back on',
            message=(
                '<b>Check</b> the <b>Letters</b> checkbox again.<br><br>'
                'Letters reappear. Use the text field next to it to change '
                'the starting letter (e.g. <b>b</b>).'
            ),
            get_target=lambda win: win.auto_lettering_checkbox,
            completion_check=_auto_lettering_on,
            auto_advance=True,
        ),

        # ── Save ──────────────────────────────────────────────────────────────
        TutorialStep(
            title='Step 10 — Save your figure',
            message=(
                'Press <b>Ctrl+S</b> or click the Save button in the toolbar.<br><br>'
                'The figure is saved as a <code>.pyf</code> file. '
                'Reload it any time by dropping it back onto the canvas.'
            ),
            get_target=lambda win: win.mainToolBar.widgetForAction(win.save_in_bar),
            completion_check=_is_saved,
            auto_advance=True,
            requires=_has_any_shape,
            requires_text='There is nothing to save yet (Steps 1–2).',
            prepare=_prep_row(2),
        ),

        # ── Done ──────────────────────────────────────────────────────────────
        TutorialStep(
            title='Beginner tutorial complete!',
            message=(
                'Well done — figure built and saved!<br><br>'
                'Explore next:<br>'
                '• <b>File</b> menu → Export as SVG, PDF, or TIFF<br>'
                '• <b>Right-click</b> a row for more layout options<br>'
                '• <b>Help</b> menu → Medium Tutorial'
            ),
            get_target=None,
            completion_check=None,
            auto_advance=False,
        ),
    ]


def advanced_steps() -> list[TutorialStep]:
    return [
        # ── Welcome ───────────────────────────────────────────────────────────
        TutorialStep(
            title='Advanced tutorial',
            message=(
                'This tutorial covers <b>image annotation</b> (shapes, arrows), '
                '<b>insets</b>, <b>crop &amp; rotation</b>, <b>LUTs</b>, '
                '<b>scripted images</b>, and <b>Save &amp; Consolidate</b>.<br><br>'
                'Complete the Beginner and Medium tutorials first.<br><br>'
                'Click <b>Next</b> — start from a blank canvas.'
            ),
            get_target=None,
            completion_check=None,
            auto_advance=False,
        ),

        # ── Drop one image ────────────────────────────────────────────────────
        TutorialStep(
            title='Step 1 — Drop one image',
            message=(
                'Drag <b>one image</b> from your file manager and drop it onto the canvas.<br><br>'
                'Choose <b>"➕ As single image(s)"</b>.'
            ),
            get_target=lambda win: win.paint,
            completion_check=_has_real_image,
            auto_advance=True,
            requires=_has_real_image,
            requires_text='No image to hand? Use a sample image instead.',
            prepare=_prep_images(1),
        ),

        # ── Draw shapes on the image ──────────────────────────────────────────
        TutorialStep(
            title='Step 2 — Draw shapes on the image',
            message=(
                '<b>Double-click</b> the image (or right-click → <b>"Edit Image"</b>) '
                'to open the annotation editor.<br><br>'
                'Click the <b>Annotations</b> tab, then select a drawing tool '
                '(<b>Rectangle, Arrow, Ellipse…</b>) and draw it on the image.<br>'
                'Click <b>Ok</b> to confirm.<br><br>'
                '<i>The tutorial hint appears at the bottom-right of the editor.</i>'
            ),
            get_target=lambda win: win.paint,
            completion_check=_has_shape_annotation,
            auto_advance=True,
            requires=_has_real_image,
            requires_text='This step needs an image on the canvas (Step 1).',
            prepare=_prep_images(1),
        ),

        # ── Create an inset ───────────────────────────────────────────────────
        TutorialStep(
            title='Step 3 — Create a zoom-in inset',
            message=(
                'Open <b>Edit Image</b> again and go to the <b>Annotations</b> tab.<br><br>'
                '1. Select the <b>Rectangle</b> tool and draw a box over a region of interest.<br>'
                '2. Click <b>"Rect ROI --&gt; Inset"</b>.<br>'
                '3. Set the inset size and border width, then confirm.<br>'
                '4. Click <b>Ok</b>.<br><br>'
                'A zoomed-in copy appears as an overlay on the image.'
            ),
            get_target=lambda win: win.paint,
            completion_check=_has_inset,
            auto_advance=True,
            requires=_has_real_image,
            requires_text='This step needs an image on the canvas (Step 1).',
            prepare=_prep_images(1),
        ),

        # ── Crop and rotate ───────────────────────────────────────────────────
        TutorialStep(
            title='Step 4 — Crop or rotate the image',
            message=(
                'Open <b>Edit Image</b> once more.<br><br>'
                'In the <b>Rotate + Crop</b> tab set a non-zero crop value '
                '(trim edges) or a rotation angle.<br><br>'
                'Click <b>Ok</b> — the canvas updates.'
            ),
            get_target=lambda win: win.paint,
            completion_check=_has_cropped_or_rotated_image,
            auto_advance=True,
            requires=_has_real_image,
            requires_text='This step needs an image on the canvas (Step 1).',
            prepare=_prep_images(1),
        ),

        # ── Set LUTs ─────────────────────────────────────────────────────────
        TutorialStep(
            title='Step 5 — Apply Look-Up Tables (LUTs)',
            message=(
                '<b>Right-click</b> the image and choose <b>Appearance ▶ → "Set LUT(s)"</b>.<br><br>'
                'Assign a colour palette to each channel. LUTs work on single-channel '
                'images too — a grey image can be shown in any colour.<br><br>'
                'Click <b>Ok</b> to apply. Appearance ▶ → <b>"Reset LUT(s)"</b> reverts it.<br><br>'
                '<i>Tip: see <b>QC → Show color-blind assistant</b> for accessible palettes.</i>'
            ),
            get_target=lambda win: win.paint,
            completion_check=_has_lut,
            auto_advance=True,
            requires=_has_real_image,
            requires_text='This step needs an image on the canvas (Step 1).',
            prepare=_prep_images(1),
        ),

        # ── Build a row (needed for empty image) ──────────────────────────────
        TutorialStep(
            title='Step 6 — Build a row',
            message=(
                'You need a <b>row</b> to add a scripted empty image.<br><br>'
                'Right-click the image → <b>"Duplicate Selection"</b>. '
                'Then drag the duplicate onto the original and choose <b>"To row"</b>.<br><br>'
                'You now have a 2-image row.'
            ),
            get_target=lambda win: win.paint,
            completion_check=_has_group_with_multiple_images,
            auto_advance=True,
            requires=_has_group_with_multiple_images,
            requires_text='Short of time? Make the row from your image and a sample image.',
            prepare=_prep_row_reusing(2),
        ),

        # ── Add empty image ───────────────────────────────────────────────────
        TutorialStep(
            title='Step 7 — Add an empty image slot',
            message=(
                '<b>Right-click</b> the row and choose '
                '<b>"Add Empty Image"</b>.<br><br>'
                'Set the desired width and height and click <b>Ok</b>.<br><br>'
                'A grey empty placeholder appears in the row — '
                'it will be filled by a Python script in the next step.'
            ),
            get_target=lambda win: win.paint,
            completion_check=_has_empty_image,
            auto_advance=True,
            requires=_has_group_with_multiple_images,
            requires_text='This step needs a row of images (Step 6).',
            prepare=lambda win: _prep_row_if_missing(win),
        ),

        # ── Script the empty image ────────────────────────────────────────────
        TutorialStep(
            title='Step 8 — Script the empty image',
            message=(
                '<b>Double-click</b> the grey empty image → open the <b>"Script"</b> tab.<br><br>'
                'The example script has been <b>copied to your clipboard</b> — '
                'paste it (<b>Ctrl+V</b>) into the script editor.<br><br>'
                'The script assigns a matplotlib plot to <code>self.img</code>. '
                'See the Help/doc for the full <code>self.img</code> API.<br><br>'
                'Click <b>"Add and Execute"</b>, confirm the warning, then click <b>Ok</b>.'
            ),
            get_target=lambda win: win.paint,
            completion_check=_has_scripted_image,
            auto_advance=True,
            on_show=_on_show_copy_script,
            requires=lambda win: _has_empty_image(win) or _has_scripted_image(win),
            requires_text='This step needs an empty image slot (Step 7).',
            prepare=_prep_empty_image,
        ),

        # ── Edit the script ───────────────────────────────────────────────────
        TutorialStep(
            title='Step 9 — Edit the script',
            message=(
                'Open <b>Edit Image</b> on the scripted image — the script is still there.<br><br>'
                'Modify it (change colours, add a label, use different data) '
                'and click <b>"Add and Execute"</b> again, then <b>Ok</b>.<br><br>'
                'Scripts are saved inside the <code>.pyf</code> file — '
                'collaborators get the exact same result when they open it.'
            ),
            get_target=lambda win: win.paint,
            completion_check=_make_script_changed_check(),
            auto_advance=True,
            requires=_has_scripted_image,
            requires_text='This step needs a scripted image — click <b>Prev</b> and do Step 8 first.',
        ),

        # ── Save and Consolidate ──────────────────────────────────────────────
        TutorialStep(
            title='Step 10 — Save and Consolidate',
            message=(
                'Go to <b>File → Save And Consolidate…</b>.<br><br>'
                'This writes the <code>.pyf</code> plus a <code>.files</code> folder '
                'holding a copy of every image it uses — a portable bundle.<br><br>'
                'Send it to a colleague or archive it — everything needed to '
                'reproduce the figure is inside.<br><br>'
                'Click <b>Next</b> when done.'
            ),
            get_target=None,
            completion_check=None,
            auto_advance=False,
        ),

        # ── Done ──────────────────────────────────────────────────────────────
        TutorialStep(
            title='Advanced tutorial complete!',
            message=(
                'You have explored the full depth of PyFigures.<br><br>'
                'More to discover:<br>'
                '• <b>Annotations → Remove</b> — bulk-remove shapes, scale bars, or insets<br>'
                '• <b>Right-click a row → Crop &amp; size ▶ → Force same width and height</b><br>'
                '• <b>Help → Stacks, Channels &amp; Movies</b> tutorial — channel split, projections, video<br>'
                '• <b>File → Export As</b> (PDF, TIFF, PNG…) — for submission or presentations'
            ),
            get_target=None,
            completion_check=None,
            auto_advance=False,
        ),
    ]

def medium_steps() -> list[TutorialStep]:
    return [
        # ── Welcome ───────────────────────────────────────────────────────────
        TutorialStep(
            title='Medium tutorial',
            message=(
                'This tutorial covers <b>combining layouts by drag-and-drop</b>, '
                '<b>reordering with arrow keys</b>, <b>labels &amp; annotations</b>, '
                '<b>templates</b>, and <b>export</b>.<br><br>'
                'Complete the Beginner tutorial first if you have not already.<br><br>'
                'Click <b>Next</b> — we build from scratch.'
            ),
            get_target=None,
            completion_check=None,
            auto_advance=False,
        ),

        # ── Drop 2 images as single images ────────────────────────────────────
        TutorialStep(
            title='Step 1 — Drop two images as singles',
            message=(
                'Select <b>two images</b> in your file manager, drag them together '
                'and drop them onto the canvas.<br><br>'
                'From the pop-up menu choose <b>"➕ As single image(s)"</b>.<br><br>'
                'Both images land separately on the canvas (not combined into a row).'
            ),
            get_target=lambda win: win.paint,
            completion_check=_has_two_single_images,
            auto_advance=True,
            requires=_has_two_single_images,
            requires_text='No images to hand? Use two sample images.',
            prepare=_prep_images(2),
        ),

        # ── Combine by DnD one onto the other ────────────────────────────────
        TutorialStep(
            title='Step 2 — Combine into a row by drag-and-drop',
            message=(
                'Drag <b>one image</b> and drop it <b>directly onto the other</b>.<br><br>'
                'From the pop-up menu choose <b>"To row"</b>.<br><br>'
                'The two images merge into a single row — this gesture works for '
                'images, rows, and columns alike.'
            ),
            get_target=lambda win: win.paint,
            completion_check=_has_group_with_multiple_images,
            auto_advance=True,
            requires=lambda win: _has_two_single_images(win) or _has_group_with_multiple_images(win),
            requires_text='This step needs two separate images on the canvas (Step 1).',
            prepare=_prep_images(2),
        ),

        # ── Select the whole row ──────────────────────────────────────────────
        TutorialStep(
            title='Step 3 — Select the whole row',
            message=(
                '<b>Click once</b> on the row to select it as a whole.<br><br>'
                'The entire row is highlighted — the step will advance automatically.'
            ),
            get_target=lambda win: win.paint,
            completion_check=_is_group_selected,
            auto_advance=True,
            requires=_has_group_with_multiple_images,
            requires_text='This step needs a row of images (Step 2).',
            prepare=lambda win: _prep_row_if_missing(win),
        ),

        # ── Reorder within row with arrow keys ────────────────────────────────
        TutorialStep(
            title='Step 4 — Reorder images within the row',
            message=(
                'With the row selected, <b>click again</b> on one image to select it '
                'individually.<br><br>'
                'Press <b>← →</b> to move that image left or right within the row.<br><br>'
                'Press at least twice — the step advances automatically.'
            ),
            get_target=lambda win: win.paint,
            completion_check=_make_arrow_key_check(2),
            auto_advance=True,
            requires=_has_group_with_multiple_images,
            requires_text='This step needs a row of images (Step 2).',
            prepare=_prep_select_image_in_row,
        ),

        # ── Create a 3-image row at once ──────────────────────────────────────
        TutorialStep(
            title='Step 5 — Create a 3-image row at once',
            message=(
                'Select <b>three images</b> in your file manager, drag them all '
                'and drop onto an <b>empty area</b> of the canvas.<br><br>'
                'Choose <b>"↔ To row"</b> — all three land in one row in a single step.<br><br>'
                'You now have two rows on the canvas.'
            ),
            get_target=lambda win: win.paint,
            completion_check=_has_group_with_3_or_more_images,
            auto_advance=True,
            requires=_has_group_with_3_or_more_images,
            requires_text='No images to hand? Make the row from three sample images.',
            prepare=_prep_row(3),
        ),

        # ── Select a row to rearrange ─────────────────────────────────────────
        TutorialStep(
            title='Step 6 — Select a row',
            message=(
                '<b>Click once</b> on one of the rows to select it.<br><br>'
                'The step advances automatically once a row is selected.'
            ),
            get_target=lambda win: win.paint,
            completion_check=_is_group_selected,
            auto_advance=True,
            requires=_has_group_with_multiple_images,
            requires_text='This step needs a row of images (Step 5).',
            prepare=lambda win: _prep_row_if_missing(win),
        ),

        # ── Rearrange rows with arrow keys ────────────────────────────────────
        TutorialStep(
            title='Step 7 — Rearrange rows with arrow keys',
            message=(
                'With a row selected, press <b>↑ ↓</b> to move it up or down '
                'relative to the other rows.<br><br>'
                'Press at least twice — the step advances automatically.'
            ),
            get_target=lambda win: win.paint,
            completion_check=_make_arrow_key_check(2),
            auto_advance=True,
            requires=_has_two_rows,
            requires_text='This step needs two rows to swap (Steps 2 and 5).',
            prepare=lambda win: (_prep_two_rows(win), _when(win, _has_two_rows, _select_first_row)),
        ),

        # ── Add labels above a row ────────────────────────────────────────────
        TutorialStep(
            title='Step 8 — Add labels above a row',
            message=(
                '<b>Right-click</b> one of the rows.<br>'
                'Choose <b>Add labels ▶ → "Above the row"</b>.<br><br>'
                'Default labels appear above each image.'
            ),
            get_target=lambda win: win.paint,
            completion_check=_has_text_row,
            auto_advance=True,
            requires=_has_group_with_multiple_images,
            requires_text='This step needs a row of images (Step 2).',
            prepare=lambda win: _prep_row_if_missing(win),
        ),

        # ── Edit label by double-click ─────────────────────────────────────────
        TutorialStep(
            title='Step 9 — Edit a label',
            message=(
                '<b>Double-click</b> one of the label texts above the row.<br><br>'
                'An editor opens — type your own text and confirm.<br><br>'
                'The step advances automatically when a label changes.'
            ),
            get_target=lambda win: win.paint,
            completion_check=_make_label_edited_check(),
            auto_advance=True,
            requires=_has_text_row,
            requires_text='This step needs a row of labels (Step 8).',
            prepare=_prep_text_row,
        ),

        # ── Text annotation on an image ───────────────────────────────────────
        TutorialStep(
            title='Step 10 — Text annotation on an image',
            message=(
                '<b>Double-click</b> an image (or right-click → <b>"Edit Image"</b>).<br>'
                'In the <b>Annotations</b> tab click the <b>T</b> button '
                '(<i>Floating txt</i>), click on the image where the text should go, '
                'then <b>double-click</b> the text to type your own. Click <b>Ok</b>.<br><br>'
                'Text annotations are stored with the image and rescale with it.'
            ),
            get_target=lambda win: win.paint,
            completion_check=_has_text_annotation,
            auto_advance=True,
            requires=_has_real_image,
            requires_text='This step needs an image on the canvas (Step 1).',
            prepare=_prep_images(1),
        ),

        # ── Convert to template ───────────────────────────────────────────────
        TutorialStep(
            title='Step 11 — Convert to template',
            message=(
                'Go to <b>File → Convert figure to template</b>.<br><br>'
                'Images become grey placeholders — layout, annotations, '
                'scale bars, and LUTs are all preserved.<br><br>'
                'Templates let you reuse the same layout with new images.'
            ),
            get_target=lambda win: win.menuBar,
            completion_check=_figure_is_template,
            auto_advance=True,
            requires=lambda win: _has_real_image(win) or _figure_is_template(win),
            requires_text='This step needs a figure with images (Steps 1–5).',
            prepare=_prep_row(2),
        ),

        # ── Fill the template ─────────────────────────────────────────────────
        TutorialStep(
            title='Step 12 — Fill the template',
            message=(
                'Drop an <b>image onto a grey placeholder slot</b>.<br><br>'
                'Choose <b>"⬜ Assign to template slot"</b>.<br>'
                'The slot is replaced by your image; all annotations stay in place.'
            ),
            get_target=lambda win: win.paint,
            completion_check=_make_template_filled_check(),
            auto_advance=True,
            requires=lambda win: _figure_is_template(win) or _has_template_slot(win),
            requires_text='This step needs a template (Step 11).',
            prepare=_prep_template,
        ),

        # ── Export as SVG ─────────────────────────────────────────────────────
        TutorialStep(
            title='Step 13 — Export as SVG',
            message=(
                'Go to <b>File → Export As → SVG</b>.<br><br>'
                'SVG can be edited in <b>Inkscape</b> or <b>Illustrator</b> '
                'for final polish before submission.'
            ),
            get_target=None,
            completion_check=None,
            auto_advance=False,
        ),

        # ── Done ──────────────────────────────────────────────────────────────
        TutorialStep(
            title='Medium tutorial complete!',
            message=(
                'Great work — you know the full PyFigures workflow.<br><br>'
                'Also worth exploring:<br>'
                '• <b>Save And Consolidate</b> — portable archive of figure + images<br>'
                '• <b>Color-blind assistant</b> — QC menu<br>'
                '• <b>Set LUTs</b> — right-click a group for channel colors<br>'
                '• <b>Annotations → Panel letters (A, B, C…)</b> — font, size, case<br>'
                '• <b>Help</b> menu → Advanced Tutorial'
            ),
            get_target=None,
            completion_check=None,
            auto_advance=False,
        ),
    ]


def publication_steps() -> list[TutorialStep]:
    """Take a finished figure to submission-ready: the Annotations batch tools,
    the whole QC menu, a caption, and the professional export formats."""
    return _require_figure([
        # ── Welcome ───────────────────────────────────────────────────────────
        TutorialStep(
            title='Publication &amp; QC tutorial',
            message=(
                'You have a figure — now make it <b>journal-ready</b>.<br><br>'
                'This tour covers the <b>Annotations</b> batch tools, the entire '
                '<b>QC</b> menu (audit, resolution, fonts, compliance, integrity, '
                'provenance), a <b>caption</b>, and the pro <b>export</b> formats '
                '(PDF, PDF+LaTeX, print-ready CMYK).<br><br>'
                'Most steps open a <b>report dialog</b> — read it, close it, then '
                'click <b>Next</b>. Do the Beginner/Medium tutorials first.'
            ),
            get_target=None,
            completion_check=None,
            auto_advance=False,
        ),

        # ── Have a figure ─────────────────────────────────────────────────────
        TutorialStep(
            title='Step 1 — Start from a multi-panel figure',
            message=(
                'Drop a few <b>images</b> (or an existing <code>.pyf</code>) onto '
                'the canvas and arrange them into a row or two.<br><br>'
                'A figure with several panels makes the QC checks meaningful.'
            ),
            get_target=lambda win: win.paint,
            completion_check=lambda win: len(win.paint.EZFIG_panel.shapes_to_draw) > 0,
            auto_advance=True,
        ),

        # ── Scale bar on all panels ───────────────────────────────────────────
        TutorialStep(
            title='Step 2 — Scale bar on every panel',
            message=(
                'Open <b>Annotations → "Add scale bar to all panels…"</b>.<br><br>'
                'Set the physical bar length once and it is applied to every '
                'micrograph in the figure — no need to edit each image.<br><br>'
                'The step advances when two or more panels carry a scale bar.'
            ),
            get_target=lambda win: win.menuBar,
            completion_check=lambda win: _count_scalebars(win) >= 2,
            auto_advance=True,
        ),

        # ── Tidy typography ───────────────────────────────────────────────────
        TutorialStep(
            title='Step 3 — Tidy text typography',
            message=(
                'Open <b>Annotations → "Tidy text typography (×, °, units, ranges…)"</b>.<br><br>'
                'It fixes the small things reviewers notice, in every label: '
                '<code>2*3</code>→<b>2×3</b>, <code>37 degrees C</code>→<b>37 °C</b>, '
                '<code>10µm</code>→<b>10 µm</b>, <code>10-20</code>→<b>10–20</b> and '
                '<code>-5</code>→<b>−5</b> (true minus).<br><br>'
                'Read the summary, then click <b>Next</b>.'
            ),
            get_target=lambda win: win.menuBar,
            completion_check=None,
            auto_advance=False,
        ),

        # ── LUT colour bar ────────────────────────────────────────────────────
        TutorialStep(
            title='Step 4 — Add a LUT colour bar',
            message=(
                'For an intensity-coded (pseudocolour) panel, open '
                '<b>Insert → "LUT colour bar…"</b>.<br><br>'
                'A calibrated colour scale is generated and placed next to the '
                'figure so readers can map colour back to intensity.<br><br>'
                'Click <b>Next</b> when done.'
            ),
            get_target=lambda win: win.menuBar,
            completion_check=None,
            auto_advance=False,
        ),

        # ── Data-plot panel from a CSV ────────────────────────────────────────
        TutorialStep(
            title='Step 5 — Add a data plot from a CSV',
            message=(
                'Quantification belongs in the same figure as the images. Open '
                '<b>Insert → "Data plot from CSV…"</b>.<br><br>'
                'Pick a <b>CSV</b> of measurements and a plot type '
                '(<b>bar / box / violin / scatter / grouped</b>). PyFigures runs '
                'the right statistical test automatically — Welch <i>t</i> / '
                'Mann-Whitney for two groups, ANOVA+Tukey / Kruskal+Dunn for more '
                '— and draws the <b>significance brackets</b> for you. The chosen '
                'test and p-values are stored for the Methods section.<br><br>'
                '(Needs the <code>staplot</code> package.) Click <b>Next</b> when done.'
            ),
            get_target=lambda win: win.menuBar,
            completion_check=None,
            auto_advance=False,
            samples=_samples_csv,
        ),

        # ── Audit ─────────────────────────────────────────────────────────────
        TutorialStep(
            title='Step 6 — Audit the figure',
            message=(
                'Open <b>QC → "Audit figure (missing scale bars / labels)"</b>.<br><br>'
                'It inventories every panel and flags the ones missing a scale bar '
                'or a letter — a quick completeness pass before you go further.<br><br>'
                'Read the report, then click <b>Next</b>.'
            ),
            get_target=lambda win: win.menuBar,
            completion_check=None,
            auto_advance=False,
        ),

        # ── Print resolution ──────────────────────────────────────────────────
        TutorialStep(
            title='Step 7 — Check print resolution',
            message=(
                'Open <b>QC → "Check print resolution…"</b>.<br><br>'
                'Enter the target column width; PyFigures tells you the effective '
                'DPI of each panel and warns if any would print blurry (&lt; 300 DPI).<br><br>'
                'Click <b>Next</b> when you have read it.'
            ),
            get_target=lambda win: win.menuBar,
            completion_check=None,
            auto_advance=False,
        ),

        # ── Enforce font size ─────────────────────────────────────────────────
        TutorialStep(
            title='Step 8 — Enforce a minimum font size',
            message=(
                'Open <b>QC → "Enforce minimum font size…"</b>.<br><br>'
                'Journals reject sub-5&nbsp;pt text. Give the minimum (e.g. 7&nbsp;pt) '
                'and every smaller label is bumped up in one go.<br><br>'
                'Click <b>Next</b>.'
            ),
            get_target=lambda win: win.menuBar,
            completion_check=None,
            auto_advance=False,
        ),

        # ── Journal compliance / guidelines ───────────────────────────────────
        TutorialStep(
            title='Step 9 — Journal compliance',
            message=(
                'Open <b>QC → "Check journal compliance…"</b> and pick a journal '
                '(Nature, Science, Cell…).<br><br>'
                'It checks column width, DPI and fonts against that journal\'s spec. '
                '<b>"Apply journal guidelines…"</b> can resize and reformat to match '
                'in one shot.<br><br>'
                'Click <b>Next</b>.'
            ),
            get_target=lambda win: win.menuBar,
            completion_check=None,
            auto_advance=False,
        ),

        # ── Image integrity ───────────────────────────────────────────────────
        TutorialStep(
            title='Step 10 — Image-integrity screen',
            message=(
                'Open <b>QC → "Check image integrity (duplicates / clones)…"</b>.<br><br>'
                'It screens for accidentally reused panels (even flipped/rotated) and '
                'within-panel copy-move cloning — the checks journals now run on '
                'submissions. A screening aid, not proof; insets/controls can match '
                'legitimately.<br><br>'
                'Click <b>Next</b>.'
            ),
            get_target=lambda win: win.menuBar,
            completion_check=None,
            auto_advance=False,
        ),

        # ── Adjustment ledger ─────────────────────────────────────────────────
        TutorialStep(
            title='Step 11 — Adjustment provenance ledger',
            message=(
                'Open <b>QC → "Adjustment provenance ledger (Methods)…"</b>.<br><br>'
                'It lists every crop, rotation, brightness/contrast range and LUT per '
                'panel and drafts a ready-to-paste <b>Methods paragraph</b> disclosing '
                'them — and flags any non-linear (scripted) adjustment.<br><br>'
                'Copy the paragraph, then click <b>Next</b>.'
            ),
            get_target=lambda win: win.menuBar,
            completion_check=None,
            auto_advance=False,
        ),

        # ── Fonts ─────────────────────────────────────────────────────────────
        TutorialStep(
            title='Step 12 — Check the fonts',
            message=(
                'Open <b>QC → "Fonts (portable / Helvetica)…"</b>.<br><br>'
                'It reports which families are bundled for portable rendering and '
                'what Helvetica/Arial resolve to on this machine — so your figure '
                'looks the same everywhere and in the exported PDF.<br><br>'
                'Click <b>Next</b>.'
            ),
            get_target=lambda win: win.menuBar,
            completion_check=None,
            auto_advance=False,
        ),

        # ── Caption ───────────────────────────────────────────────────────────
        TutorialStep(
            title='Step 13 — Write the caption / legend',
            message=(
                'Save the figure first (<b>Ctrl+S</b>) if you have not, then open '
                '<b>File → "Figure caption / legend…"</b>.<br><br>'
                'Give it a title (e.g. "Figure 1") and the legend text. It is stored '
                'in a <code>.caption.json</code> sidecar beside the <code>.pyf</code> '
                '— it never gets painted onto the artwork.<br><br>'
                'The step advances once a caption is saved.'
            ),
            get_target=lambda win: win.menuBar,
            completion_check=_has_caption_sidecar,
            auto_advance=True,
            requires=_is_saved,
            requires_text='The caption is stored beside the saved file — save the figure first.',
            prepare=_prep_save,
        ),

        # ── Export formats ────────────────────────────────────────────────────
        TutorialStep(
            title='Step 14 — Export for submission',
            message=(
                'Open <b>File → Export As</b> and pick the right format:<br>'
                '• <b>PDF</b> — vector, fonts embedded (most journals)<br>'
                '• <b>PDF + LaTeX</b> — labels typeset by LaTeX; tick '
                '<i>Include caption?</i> to wrap it in a <code>figure</code> float<br>'
                '• <b>Print-ready TIFF (CMYK)</b> — high-DPI CMYK for print<br><br>'
                'Click <b>Next</b> when exported.'
            ),
            get_target=lambda win: win.menuBar,
            completion_check=None,
            auto_advance=False,
        ),

        # ── Done ──────────────────────────────────────────────────────────────
        TutorialStep(
            title='Publication &amp; QC complete!',
            message=(
                'Your figure is submission-ready.<br><br>'
                'Related tools worth a look:<br>'
                '• <b>QC → Remap image paths…</b> — fix broken links after moving files<br>'
                '• <b>Annotations → Remove</b> — bulk-clear ROIs, scale bars, texts<br>'
                '• <b>Help</b> menu → <b>Sharing, Review &amp; Accessibility</b> tutorial'
            ),
            get_target=None,
            completion_check=None,
            auto_advance=False,
        ),
    ])


def sharing_steps() -> list[TutorialStep]:
    """Collaboration and accessibility: consolidation, the Review round-trip,
    path remapping, colour-blind checking, and theming."""
    return _require_figure([
        # ── Welcome ───────────────────────────────────────────────────────────
        TutorialStep(
            title='Sharing, Review &amp; Accessibility tutorial',
            message=(
                'Everything about <b>collaborating</b> on a figure and making it '
                '<b>accessible</b>: portable archives, the <b>Review</b> comment '
                'round-trip, fixing moved-file links, and <b>colour-blindness</b> '
                'checking.<br><br>'
                'Have any saved figure open, then click <b>Next</b>.'
            ),
            get_target=None,
            completion_check=None,
            auto_advance=False,
        ),

        # ── Save & Consolidate ────────────────────────────────────────────────
        TutorialStep(
            title='Step 1 — Save and Consolidate',
            message=(
                'Open <b>File → "Save And Consolidate…"</b>.<br><br>'
                'It writes the <code>.pyf</code> plus copies of every referenced '
                'image into one folder/archive — a self-contained bundle a colleague '
                'can open with no missing links.<br><br>'
                'Click <b>Next</b> when done.'
            ),
            get_target=lambda win: win.menuBar,
            completion_check=None,
            auto_advance=False,
        ),

        # ── Export for review ─────────────────────────────────────────────────
        TutorialStep(
            title='Step 2 — Export for review',
            message=(
                'Open <b>File → Review comments → "Export for review…"</b>.<br><br>'
                'It writes one self-contained <b>HTML page</b> of the figure. Your '
                'co-authors open it in any browser (no PyFigures needed), click on the '
                'figure to pin comments, and send the file back — PyFigures can open '
                'an email draft for you (it never sends anything itself).<br><br>'
                'Click <b>Next</b>.'
            ),
            get_target=lambda win: win.menuBar,
            completion_check=None,
            auto_advance=False,
        ),

        # ── Import review comments ────────────────────────────────────────────
        TutorialStep(
            title='Step 3 — Import review comments',
            message=(
                'When comments come back, open '
                '<b>File → Review comments → "Import review comments…"</b> and select the file.<br><br>'
                'The comments are attached to the figure so you can address them '
                'panel by panel.<br><br>'
                'No reviewed copy yet? Use the sample one below.<br><br>'
                'Click <b>Next</b>.'
            ),
            get_target=lambda win: win.menuBar,
            completion_check=None,
            auto_advance=False,
            samples=_samples_review,
        ),

        # ── View review comments ──────────────────────────────────────────────
        TutorialStep(
            title='Step 4 — View review comments',
            message=(
                'Open <b>File → Review comments → "View review comments"</b> to see the imported '
                'notes overlaid on the figure (import some in Step 3 first).<br><br>'
                'Work through them, then re-export an updated review copy if needed.<br><br>'
                'Click <b>Next</b>.'
            ),
            get_target=lambda win: win.menuBar,
            completion_check=None,
            auto_advance=False,
        ),

        # ── Merge figures ─────────────────────────────────────────────────────
        TutorialStep(
            title='Step 5 — Merge another figure in',
            message=(
                'Open <b>File → "Merge into current figure…"</b> and pick another '
                '<code>.pyf</code>.<br><br>'
                'Its panels are appended to the current canvas — handy for assembling '
                'a big multi-part figure from pieces different people built.<br><br>'
                'Click <b>Next</b>.'
            ),
            get_target=lambda win: win.menuBar,
            completion_check=None,
            auto_advance=False,
            samples=_samples_other_figure,
        ),

        # ── Remap image paths ─────────────────────────────────────────────────
        TutorialStep(
            title='Step 6 — Fix moved-file links',
            message=(
                'If images were moved after saving, open '
                '<b>QC → "Remap image paths…"</b>.<br><br>'
                'Give the <b>old</b> folder (the start of the paths stored in the figure) '
                'and the <b>new</b> one: every image path starting with the old folder is '
                'rewritten at once — no need to re-add images.<br><br>'
                'To try it, the sample button copies the images to a new folder and '
                'gives you both paths. Click <b>Next</b>.'
            ),
            get_target=lambda win: win.menuBar,
            completion_check=None,
            auto_advance=False,
            samples=_samples_moved_images,
        ),

        # ── Colour-blind assistant ────────────────────────────────────────────
        TutorialStep(
            title='Step 7 — Colour-blind assistant',
            message=(
                'Open <b>QC → "Show color-blind assistant"</b>.<br><br>'
                'It recommends colour-blind-safe LUT/palette combinations — avoid '
                'red/green pairings that ~8% of male readers cannot distinguish.<br><br>'
                'Click <b>Next</b>.'
            ),
            get_target=lambda win: win.menuBar,
            completion_check=None,
            auto_advance=False,
        ),

        # ── Preview under CVD ─────────────────────────────────────────────────
        TutorialStep(
            title='Step 8 — Preview under colour-blindness',
            message=(
                'Open <b>QC → "Preview figure under colour-blindness…"</b>.<br><br>'
                'It simulates how your figure looks to deuteranope / protanope / '
                'tritanope readers so you can catch unreadable colour coding before '
                'submission.<br><br>'
                'Click <b>Next</b>.'
            ),
            get_target=lambda win: win.menuBar,
            completion_check=None,
            auto_advance=False,
        ),

        # ── Theme ─────────────────────────────────────────────────────────────
        TutorialStep(
            title='Step 9 — Switch the interface theme',
            message=(
                'Open <b>View → Theme</b> and pick a light or dark theme for the '
                'editor.<br><br>'
                'This only changes the <i>application</i> appearance — your figure '
                'and its exports are unaffected.<br><br>'
                'Click <b>Next</b>.'
            ),
            get_target=lambda win: win.menuBar,
            completion_check=None,
            auto_advance=False,
        ),

        # ── Done ──────────────────────────────────────────────────────────────
        TutorialStep(
            title='Sharing &amp; Accessibility complete!',
            message=(
                'You now know the full collaboration and accessibility toolkit.<br><br>'
                'Still to explore in the <b>Help</b> menu: the <b>Stacks, Channels &amp; '
                'Movies</b>, <b>Automate</b>, <b>Chat &amp; MCP</b>, <b>Poster</b> and <b>Photo '
                'Album</b> tutorials; <b>Chat &amp; MCP</b> shows how a language model can do all '
                'of this for you in plain language.<br><br>'
                'Happy figure-making!'
            ),
            get_target=None,
            completion_check=None,
            auto_advance=False,
        ),
    ], saved_titles=('Import review comments', 'View review comments'))


def _require_figure(steps, saved_titles=(), first=1):
    """Tutorials that work on "a figure": every step from *first* to the one
    before last needs images on the canvas — offer samples if there are none.
    Steps whose title contains one of *saved_titles* need a saved .pyf."""
    for s in steps[first:-1]:
        if s.requires is not None:
            continue
        if any(t in s.title for t in saved_titles):
            s.requires = lambda win: _has_real_image(win) and _is_saved(win)
            s.requires_text = 'This step works on a saved figure — save it first (Ctrl+S).'
            s.prepare = _prep_save
        else:
            s.requires = _has_real_image
            s.requires_text = ('This tutorial works on a figure with images — open one of yours, '
                               'or use sample images.')
            s.prepare = lambda win: _prep_two_rows(win)
    return steps


# ══════════════════════════════════════════════════════════════════════════════
# Stacks, channels & movies
# ══════════════════════════════════════════════════════════════════════════════

def _dims(img):
    from batoolset.img import guess_dimensions
    arr = getattr(img, 'img', None)
    if getattr(arr, 'ndim', 0) < 3:
        return ''
    try:
        return guess_dimensions(arr) or ''
    except Exception:
        return ''


def _is_z_panel(img):
    return 'd' in _dims(img) and not getattr(img, 'isText', False)


def _is_t_panel(img):
    return 't' in _dims(img) and not getattr(img, 'isText', False)


def _is_channel_panel(img):
    return 'c' in _dims(img) and img.img.shape[-1] > 1 and not getattr(img, 'isText', False)


def _panels(win, pred):
    return [i for i in _image_stack(win) if isinstance(getattr(i, 'filename', None), str) and pred(i)]


def _demo_stack_row_paths():
    """A 3-channel image, a z-stack and a time-lapse, saved so that their axes
    are unambiguous (ImageJ metadata)."""
    import os
    import numpy as np
    import tifffile
    _DEMO_COUNTER[0] += 1
    k = _DEMO_COUNTER[0]
    d = _demo_dir()
    ch = np.stack([_demo_plane(k * 10 + c) for c in range(3)], axis=-1)
    c_path = os.path.join(d, f'sample_channels_{k:02d}.tif')
    tifffile.imwrite(c_path, ch, photometric='rgb')
    z = np.stack([np.roll(_demo_plane(k * 10 + 5), 4 * i, axis=0) for i in range(8)])
    z_path = os.path.join(d, f'sample_zstack_{k:02d}.tif')
    tifffile.imwrite(z_path, z, imagej=True, metadata={'axes': 'ZYX', 'spacing': 2.0, 'unit': 'um'})
    return [c_path, z_path, _demo_movie_path()]


def _prep_stack_row(win):
    win.add_images_to_new_row(_demo_stack_row_paths())


def _prep_and_select(pred):
    """Make sure a panel matching *pred* exists (sample stacks otherwise) and
    select it — the Stack views menu works on the selected panel."""
    def select(win):
        found = _panels(win, pred)
        if found:
            win.paint.EZFIG_panel.set_current_selection(found[0])
            win.paint.EZFIG_panel.update()

    def prepare(win):
        if _panels(win, pred):
            select(win)
            return
        _prep_stack_row(win)
        _when(win, lambda w: bool(_panels(w, pred)), select)
    return prepare


def _has_any_stack(win):
    return bool(_panels(win, lambda i: _is_z_panel(i) or _is_t_panel(i) or _is_channel_panel(i)))


def stacks_steps() -> list[TutorialStep]:
    """Multi-dimensional images: projections, channel split, montages,
    kymographs, orthogonal views, channel merges and movie export."""
    n_panels = _make_count_increase_check(_n_images)
    return [
        TutorialStep(
            title='Stacks, Channels &amp; Movies tutorial',
            message=(
                'Microscopy data is rarely one flat image. This tour shows how PyFigures '
                'handles <b>Z stacks</b>, <b>time-lapses</b> and <b>multi-channel</b> '
                'images: projections, <b>channel split</b>, frame <b>montages</b>, '
                '<b>kymographs</b>, <b>orthogonal views</b>, channel <b>merges</b> and '
                '<b>movie export</b>.<br><br>'
                'No stacks of your own at hand? Every step can create small sample '
                'stacks for you.'
            ),
        ),
        TutorialStep(
            title='Step 1 — Bring in some stacks',
            message=(
                'Drop a <b>Z stack</b>, a <b>time-lapse</b> and/or a <b>multi-channel</b> '
                'image (TIFF, CZI, LIF, ND2…) onto the canvas and choose '
                '<b>"↔ To row"</b>.<br><br>'
                'A stack is shown as <b>one image</b> on the canvas — the next steps '
                'show the ways to look inside it.'
            ),
            get_target=lambda win: win.paint,
            completion_check=_has_any_stack,
            requires=_has_any_stack,
            requires_text='No stacks to hand? Use a sample 3-channel image, Z stack and time-lapse.',
            prepare=_prep_stack_row,
        ),
        TutorialStep(
            title='Step 2 — Project a Z stack',
            message=(
                '<b>Double-click</b> the Z stack to open the image editor.<br><br>'
                'In the <b>File Infos + Scale</b> tab, set <b>Projection</b> to '
                '<b>Max</b> (or Avg / Min) and, if you like, limit it to a range of '
                'slices. With no projection, the <b>slider</b> picks which slice is '
                'shown.<br><br>'
                'Click <b>Ok</b> — the step advances once a projection is set.'
            ),
            get_target=lambda win: win.paint,
            completion_check=_has_projection,
            requires=lambda win: bool(_panels(win, _is_z_panel)),
            requires_text='This step needs a Z stack on the canvas.',
            prepare=_prep_and_select(_is_z_panel),
        ),
        TutorialStep(
            title='Step 3 — Channel split',
            message=(
                '<b>Click</b> the multi-channel image to select it, then open '
                '<b>Insert → Stack views → "Channel split (each channel + merge)…"</b>.<br><br>'
                'Name each channel and pick its colour; click <b>Ok</b>. A new row shows '
                'every channel in grey with its name in colour, then the merge.<br><br>'
                '<i>Right-click → <b>Split ▶</b> on the image gives a quick split too.</i>'
            ),
            get_target=lambda win: win.menuBar,
            completion_check=n_panels,
            requires=lambda win: bool(_panels(win, _is_channel_panel)),
            requires_text='This step needs a multi-channel image (select it first).',
            prepare=_prep_and_select(_is_channel_panel),
        ),
        TutorialStep(
            title='Step 4 — Montage of frames',
            message=(
                'Select the <b>time-lapse</b> (or the Z stack) and open '
                '<b>Insert → Stack views → "Montage of frames (time / Z)…"</b>.<br><br>'
                'Choose how many frames (e.g. <code>6</code>, <code>all</code> or '
                '<code>0:20:5</code>), panels per row and the time stamps; click '
                '<b>Ok</b>. A new row shows the frames side by side.'
            ),
            get_target=lambda win: win.menuBar,
            completion_check=_make_count_increase_check(_n_images),
            requires=lambda win: bool(_panels(win, lambda i: _is_t_panel(i) or _is_z_panel(i))),
            requires_text='This step needs a time-lapse or Z stack (select it first).',
            prepare=_prep_and_select(_is_t_panel),
        ),
        TutorialStep(
            title='Step 5 — Kymograph',
            message=(
                'Select the <b>time-lapse</b> and open '
                '<b>Insert → Stack views → "Kymograph along a line…"</b>.<br><br>'
                'Give the two ends of the line (x1, y1 → x2, y2, in pixels) and how '
                'many pixels to average across it; click <b>Ok</b>.<br><br>'
                'The kymograph — position along the line against time, time running '
                'downwards — is added next to the panel. Moving objects draw slanted '
                'lines; their slope is their speed.'
            ),
            get_target=lambda win: win.menuBar,
            completion_check=_make_count_increase_check(_n_images),
            requires=lambda win: bool(_panels(win, _is_t_panel)),
            requires_text='This step needs a time-lapse (select it first).',
            prepare=_prep_and_select(_is_t_panel),
        ),
        TutorialStep(
            title='Step 6 — Orthogonal views',
            message=(
                'Select the <b>Z stack</b> and open '
                '<b>Insert → Stack views → "Orthogonal views (XZ / YZ)…"</b>.<br><br>'
                'Choose where to cut (x, y), which XY slice to show (or the max '
                'projection), and the <b>Z step / pixel size</b> ratio so the side views '
                'are not squashed; click <b>Ok</b>.<br><br>'
                'XY, YZ (right) and XZ (below) are added next to the panel.'
            ),
            get_target=lambda win: win.menuBar,
            completion_check=_make_count_increase_check(_n_images),
            requires=lambda win: bool(_panels(win, _is_z_panel)),
            requires_text='This step needs a Z stack (select it first).',
            prepare=_prep_and_select(_is_z_panel),
        ),
        TutorialStep(
            title='Step 7 — Merge separate channel files',
            message=(
                'Channels saved as <b>separate files</b>? Open '
                '<b>Insert → "Multi-channel merge…"</b>, pick one file per '
                'channel and a colour for each; click <b>Ok</b>.<br><br>'
                'The merged colour image is added to the figure — the source files '
                'stay untouched.<br><br>'
                'Click <b>Next</b> when done (or to skip).'
            ),
            get_target=lambda win: win.menuBar,
            auto_advance=False,
            samples=_samples_channel_files,
        ),
        TutorialStep(
            title='Step 8 — Export a movie',
            message=(
                'Open <b>File → Export As → "Video (animate time-stacks)…"</b>.<br><br>'
                'Every time-lapse panel plays in sync; still panels stay as they are. '
                'Choose what shorter movies do once they run out of frames '
                '(<b>freeze</b> or <b>blank</b>). MP4, AVI and MKV are supported.<br><br>'
                'Click <b>Next</b> when exported.'
            ),
            get_target=lambda win: win.menuBar,
            auto_advance=False,
            requires=_has_time_stack,
            requires_text='A movie needs at least one time-lapse panel.',
            prepare=_prep_and_select(_is_t_panel),
        ),
        TutorialStep(
            title='Stacks, Channels &amp; Movies complete!',
            message=(
                'You can now show what is inside a stack in every common way.<br><br>'
                'Also worth knowing:<br>'
                '• Right-click an image → <b>Split ▶ → "Split by a dimension"</b> — one panel per Z / time / channel<br>'
                '• Right-click → <b>Appearance ▶ → Set LUT(s)</b> — colour each channel<br>'
                '• Multi-series files (LIF, CZI…) ask which series to open when dropped'
            ),
        ),
    ]


# ══════════════════════════════════════════════════════════════════════════════
# Automate: drafts, recipes, library
# ══════════════════════════════════════════════════════════════════════════════

def automation_steps() -> list[TutorialStep]:
    """Building figures without clicking each panel: drafts from a results
    folder, recipes, the figure library, version compare, style copy, the
    pre-submission review and the MCP server."""
    return _require_figure([
        TutorialStep(
            title='Automate: drafts, recipes &amp; library',
            message=(
                'When you make the same kind of figure again and again, let PyFigures '
                'build it: a <b>draft from a results folder</b>, a <b>recipe</b> '
                '(a small text file describing the whole figure), the <b>figure '
                'library</b>, and checks across versions.<br><br>'
                'Most steps open a dialog — try it, then click <b>Next</b>.'
            ),
        ),
        TutorialStep(
            title='Step 1 — Draft a figure from a folder',
            message=(
                'Open <b>File → "Draft figure from folder…"</b> and pick a folder of '
                'results (images, and CSV tables if you have them).<br><br>'
                'PyFigures lays the images out in a grid, turns each CSV into a plot '
                '(with significance tests), adds scale bars and panel letters, sizes '
                'the figure to a journal column and drafts a caption — a first draft '
                'in seconds that you then polish by hand.'
            ),
            get_target=lambda win: win.menuBar,
            auto_advance=False,
            samples=_samples_results_folder,
        ),
        TutorialStep(
            title='Step 2 — Build a figure from a recipe',
            message=(
                'A <b>recipe</b> is a short YAML/JSON file: the images of each row, '
                'labels, scale bars, LUTs, crops, insets, plots, journal style, export '
                'formats… Open <b>File → "Build figure from recipe…"</b> and pick one.<br><br>'
                'Change an image or a setting in the recipe and rebuild — the figure '
                'updates identically every time. The same recipe runs from the command '
                'line (<code>python -m pyfigures.recipe my_figure.yaml</code>) and through '
                'the MCP server.<br><br>'
                'Every key is described in <code>docs/RECIPES.md</code>; '
                '<code>docs/recipe_example.yaml</code> is a full example. The sample '
                'button writes a short recipe with its images to try it on.'
            ),
            get_target=lambda win: win.menuBar,
            auto_advance=False,
            samples=_samples_recipe,
        ),
        TutorialStep(
            title='Step 3 — Search your figure library',
            message=(
                'Open <b>File → "Search figure library…"</b>.<br><br>'
                'Point it at the folder where you keep figures and type keywords; it '
                'searches every <code>.pyf</code> below it by image file names, labels '
                'and captions, so you can find "the figure with the GFP time-lapse '
                'from last year" and open it.'
            ),
            get_target=lambda win: win.menuBar,
            auto_advance=False,
            samples=_samples_library,
        ),
        TutorialStep(
            title='Step 4 — Compare two versions',
            message=(
                'Open <b>File → "Compare with another version…"</b> and pick an older '
                'copy of the figure.<br><br>'
                'A page opens in your browser listing what changed (panels, crops, '
                'LUTs, labels…) with the two renderings and their pixel difference.<br><br>'
                'No older copy? The sample button saves one of the figure as it is now: '
                'change something, then compare with it.'
            ),
            get_target=lambda win: win.menuBar,
            auto_advance=False,
            samples=_samples_older_version,
        ),
        TutorialStep(
            title='Step 5 — Copy the style of another figure',
            message=(
                'Open <b>File → "Copy style from another figure…"</b> and pick a '
                'figure whose look you like.<br><br>'
                'Tick what to copy — fonts, panel letters, scale bars, spacing, chart '
                'styling — and it is applied to this figure: handy to keep every '
                'figure of a paper consistent.'
            ),
            get_target=lambda win: win.menuBar,
            auto_advance=False,
            samples=_samples_other_figure,
        ),
        TutorialStep(
            title='Step 6 — Alt text for accessibility',
            message=(
                'Open <b>File → "Alt text (accessibility)…"</b>.<br><br>'
                'PyFigures drafts a text description of the figure from its panels '
                'and labels; edit it and it is saved beside the figure, ready for '
                'journals and slides that ask for alt text.'
            ),
            get_target=lambda win: win.menuBar,
            auto_advance=False,
            requires=_is_saved,
            requires_text='Alt text is stored beside the saved file — save the figure first.',
            prepare=_prep_save,
        ),
        TutorialStep(
            title='Step 7 — Pre-submission review',
            message=(
                'Open <b>QC → "Pre-submission review (all checks)…"</b>.<br><br>'
                'It runs every automatic check at once (missing scale bars or letters, '
                'resolution, fonts, duplicated panels, scale-bar consistency…) and '
                'lists the questions a reviewer will ask that only you can answer.'
            ),
            get_target=lambda win: win.menuBar,
            auto_advance=False,
        ),
        TutorialStep(
            title='Step 8 — Changed source files',
            message=(
                'Images get re-processed after a figure is made. Open '
                '<b>QC → "Check for changed source files…"</b>.<br><br>'
                'It lists every image file that changed on disk since the figure was '
                'saved, and offers to re-read them.'
            ),
            get_target=lambda win: win.menuBar,
            auto_advance=False,
            requires=_is_saved,
            requires_text='The check compares against the saved figure — save it first.',
            prepare=_prep_save,
        ),
        TutorialStep(
            title='Automate complete!',
            message=(
                'You can now build and check figures in bulk.<br><br>'
                'PyFigures also ships an <b>MCP server</b> with the same tools (see '
                '<code>docs/MCP_SERVER.md</code>): connect it to an MCP client such as '
                'Claude, ask for "a 3-panel figure from this folder with 10 µm scale bars" '
                'and it drives PyFigures for you. The <b>Chat &amp; MCP</b> tutorial (Help menu) shows how.'
            ),
        ),
    ], first=4)


# ══════════════════════════════════════════════════════════════════════════════
# Chat & MCP (runs in a window that can share its figure)
# ══════════════════════════════════════════════════════════════════════════════

def _chat_is_open(win) -> bool:
    dock = getattr(win, 'local_chat_dock', None)
    return dock is not None and not dock.isHidden()       # closing the dock hides it


def chat_steps() -> list[TutorialStep]:
    """Building and editing the figure in plain language: a model in the chat
    sidebar, or any MCP client, works on the figure open in this window."""
    return _require_figure([
        TutorialStep(
            title='Chat &amp; MCP tutorial',
            message=(
                'A language model can edit this figure for you: you ask in plain words '
                '("add 10 µm scale bars", "use magenta and green"), it calls PyFigures\' '
                'own tools, and each change appears here, <b>one undo step each</b>.<br><br>'
                'Two ways: the <b>chat sidebar</b> inside PyFigures, or any <b>MCP client</b> '
                '(Claude Desktop, LM Studio…). The model never draws pixels: it only runs '
                'documented operations on your images.<br><br>'
                'Have a figure with images open (or use sample images), then click <b>Next</b>.'
            ),
        ),
        TutorialStep(
            title='Step 1 — Get a model',
            message=(
                'The chat needs a model to talk to. Pick one:<br>'
                '• <b>LM Studio</b> (free, runs on your computer, data stay private): install it, '
                'download a model with tool use (a 9-billion-parameter Qwen works with 8 GB of '
                'graphics memory; 27 billion parameters is more reliable), load it, and start its '
                'server. PyFigures finds it by itself.<br>'
                '• or the chat\'s own <b>Model Library</b>, which downloads a model and its runtime;<br>'
                '• or a <b>cloud API</b> (OpenAI, Anthropic, OpenRouter) in the chat\'s connection '
                'settings, with your own key; the figure descriptions and previews are then sent '
                'to that provider.<br><br>'
                'The chat is the optional package <code>qtpy-ai-sidecar</code>. Click <b>Next</b>.'
            ),
            auto_advance=False,
        ),
        TutorialStep(
            title='Step 2 — Open the chat',
            message=(
                'Click the <b>robot</b> at the left end of the toolbar '
                '(or <b>Tools → Chat sidebar (local model)…</b>).<br><br>'
                'The chat docks on the right and is connected to <i>this</i> window\'s figure, '
                'unsaved changes included. If it has no model yet, it says how to get one. '
                'To have it open every time PyFigures starts, tick '
                '<b>View → Open the chat at start-up</b>.'
            ),
            get_target=lambda win: win.mainToolBar.widgetForAction(win.chat_toolbar_action),
            completion_check=_chat_is_open,
        ),
        TutorialStep(
            title='Step 3 — Ask for a change',
            message=(
                'Type in the chat, for example:<br>'
                '<i>"Add 10 µm scale bars to every image (0.1 µm per pixel)."</i><br><br>'
                'Watch the scale bars appear here. A model checks its own work with '
                '<b>render_preview</b> (an image of the figure) and <b>describe_figure</b>; '
                'impossible requests are refused with an explanation.'
            ),
            completion_check=_has_scalebar,
        ),
        TutorialStep(
            title='Step 4 — Undo what the model did',
            message=(
                'Press <b>Ctrl+Z</b>: the model\'s last change is undone, like any edit of yours. '
                '<b>Ctrl+Y</b> redoes it.<br><br>'
                'You keep the last word: nothing is saved to disk until <i>you</i> save. '
                'Click <b>Next</b>.'
            ),
            auto_advance=False,
        ),
        TutorialStep(
            title='Step 5 — Ask questions too',
            message=(
                'Questions work as well as orders:<br>'
                '<i>"Is the figure ready for a Nature double column?"</i> runs the journal '
                'checks and reports what fails (size, fonts, resolution) without changing '
                'anything.<br><br>'
                '<i>"How do I split the channels?"</i> answers with the same short guides as '
                '<b>Help → Show me how…</b>, which highlight the menus to use while '
                '<i>you</i> click. Click <b>Next</b>.'
            ),
            auto_advance=False,
        ),
        TutorialStep(
            title='Step 6 — Use another MCP client',
            message=(
                'To work from Claude Desktop, LM Studio\'s own chat or any MCP client instead, use '
                '<b>Tools → Share the open figure with the MCP server</b>: it shows the '
                'configuration to paste into the client, and the client then edits this window\'s '
                'figure live, as the chat does. Untick it to stop sharing.<br><br>'
                '<b>Tools → MCP server…</b> sets up the other way of working: the client edits '
                'saved <code>.pyf</code> files without PyFigures open (see '
                '<code>docs/MCP_SERVER.md</code>). Click <b>Next</b>.'
            ),
            get_target=lambda win: win.menuBar,
            auto_advance=False,
        ),
        TutorialStep(
            title='Step 7 — What a client did to a saved file',
            message=(
                'When a client edited a saved figure through the MCP server, '
                '<b>Tools → MCP call history / undo…</b> lists every call it made, with its '
                'arguments, and undoes its last changes. Click <b>Next</b>.'
            ),
            get_target=lambda win: win.menuBar,
            auto_advance=False,
        ),
        TutorialStep(
            title='Chat &amp; MCP complete!',
            message=(
                'You can now build and revise figures in conversation.<br><br>'
                'Language models still make mistakes, small ones more often: look at each '
                'result (the preview and <b>QC</b> checks make this quick) before you rely on it. '
                'For unpublished data, prefer a local model: with a cloud model the figure '
                'descriptions and previews go to its provider.'
            ),
        ),
    ], first=3)


# ══════════════════════════════════════════════════════════════════════════════
# Poster & photo album (runs in the poster window)
# ══════════════════════════════════════════════════════════════════════════════

def _poster_tool(win, action):
    """The toolbar button of a poster-window action."""
    from qtpy.QtWidgets import QToolBar
    for bar in win.findChildren(QToolBar):
        w = bar.widgetForAction(action)
        if w is not None:
            return w
    return None


def _poster_items(win, cls_name):
    return [s for s in win.canvas.shapes_to_draw if type(s).__name__ == cls_name]


def _poster_n_images(win):
    return len(_poster_items(win, 'PosterImage'))


def _poster_prep_images(n=4):
    def prepare(win):
        for p in _demo_image_paths(n):
            win.canvas.add_image(p)
        win._refresh_page_list()
        win._update_title()
    return prepare


def _make_poster_layout_check():
    """True once the photos on the page were moved/arranged since the step began."""
    initial = [None]

    def check(win):
        sig = win.canvas._geometry_signature()
        if initial[0] is None:
            initial[0] = sig
            return False
        return sig != initial[0]

    def reset():
        initial[0] = None

    check.reset = reset
    return check


def _poster_prep_background(win):
    win.canvas.set_background(_demo_image_paths(1)[0])


def _poster_is_saved(win):
    c = win.canvas
    return bool(c.file_path) and not c.is_modified()


def poster_steps(album=False) -> list[TutorialStep]:
    """The poster / collage designer (Tools → Poster / collage designer), or
    with *album* the photo album designer (Tools → Photo album designer):
    same window class, so the same steps except the intro, pages and end."""
    if album:
        intro = TutorialStep(
            title='Photo Album tutorial',
            message=(
                'This window makes <b>photo albums</b>: a front cover, two-page '
                '<b>spreads</b> and a back cover. Photos can be freely placed, rotated '
                'and layered on each page, over a background image.<br><br>'
                'It is separate from the figure editor and from the poster designer. '
                'Click <b>Next</b>.'
            ),
        )
        pages = TutorialStep(
            title='Step 7 — Pages of the album',
            message=(
                'The <b>Pages</b> panel lists the album: front cover, spreads, back '
                'cover. <b>+ Page</b> adds a spread (two pages side by side, so a photo '
                'can sit across the middle); spreads can be duplicated, reordered or '
                'removed, the covers stay first and last.<br><br>'
                'The step advances once the album has a second spread.'
            ),
            get_target=lambda win: win.page_dock,
            completion_check=lambda win: win.canvas.page_count() >= 4,
        )
        saved_as = 'An album is saved as <code>.pyfalbum</code>.'
        done = TutorialStep(
            title='Photo Album complete!',
            message=(
                'You can now lay out whole photo books.<br><br>'
                'Tip: put a figure made in the main editor in the album with '
                '<b>Add image…</b> → pick the <code>.pyf</code>.'
            ),
        )
    else:
        intro = TutorialStep(
            title='Poster tutorial',
            message=(
                'This window makes <b>posters</b> and <b>collages</b>: photos can be '
                'freely placed, rotated and layered on a page, over a background '
                'image.<br><br>'
                'It is separate from the figure editor; figures (<code>.pyf</code>) can '
                'be placed on a page as pictures. Photo albums have their own designer '
                '(Tools → Photo album designer… in the figure editor). Click <b>Next</b>.'
            ),
        )
        pages = TutorialStep(
            title='Step 7 — Pages',
            message=(
                'The <b>Pages</b> panel lists the pages of the document. Add, '
                'duplicate, reorder or remove pages there; choose a page size from the '
                'list.<br><br>'
                'The step advances once the document has two or more pages.'
            ),
            get_target=lambda win: win.page_dock,
            completion_check=lambda win: win.canvas.page_count() >= 2,
        )
        saved_as = 'One page is saved as <code>.pyfposter</code>, several as <code>.pyfalbum</code>.'
        done = TutorialStep(
            title='Poster complete!',
            message=(
                'You can now lay out posters and collages.<br><br>'
                'Tip: put a figure made in the main editor on a poster with '
                '<b>Add image…</b> → pick the <code>.pyf</code>, or from the figure editor '
                'with <b>Tools → "Send this figure to the poster designer"</b>.'
            ),
        )
    return [
        intro,
        TutorialStep(
            title='Step 1 — Add photos',
            message=(
                'Click <b>Add image…</b> (or drag image files onto the page). Add at '
                'least <b>three</b>.<br><br>'
                'A <code>.pyf</code> figure can be added too — it is placed as a picture '
                'of the figure.'
            ),
            get_target=lambda win: _poster_tool(win, win.add_image_action),
            completion_check=lambda win: _poster_n_images(win) >= 3,
            requires=lambda win: _poster_n_images(win) >= 3,
            requires_text='No photos to hand? Use four sample images.',
            prepare=_poster_prep_images(4),
        ),
        TutorialStep(
            title='Step 2 — Arrange them in one click',
            message=(
                'Try <b>Grid</b>, <b>Scatter</b> (photos thrown on a table) and '
                '<b>Fan</b> (a spread hand of photos).<br><br>'
                'Then drag a photo to move it; click it and drag a <b>corner handle</b> '
                'to resize it or the <b>rotate handle</b> to turn it. <b>Ctrl+Z</b> undoes.'
            ),
            get_target=lambda win: _poster_tool(win, win.grid_action),
            completion_check=_make_poster_layout_check(),
            requires=lambda win: _poster_n_images(win) >= 2,
            requires_text='This step needs photos on the page (Step 1).',
            prepare=_poster_prep_images(4),
        ),
        TutorialStep(
            title='Step 3 — Use a page layout',
            message=(
                'Click <b>Layout</b> and pick a pre-designed layout (like a slide '
                'layout). Fill its slots with the photos on the page, or sketch it as '
                'empty slots and drop photos in later.'
            ),
            get_target=lambda win: _poster_tool(win, win.layouts_action),
            completion_check=_make_poster_layout_check(),
            requires=lambda win: _poster_n_images(win) >= 2,
            requires_text='This step needs photos on the page (Step 1).',
            prepare=_poster_prep_images(4),
        ),
        TutorialStep(
            title='Step 4 — Align and stack',
            message=(
                '<b>Shift+click</b> several photos, then <b>Align</b> (edges or centres) '
                'or <b>Distribute</b> (even spacing).<br><br>'
                '<b>Bring to front</b> / <b>Send to back</b> change which photo is on '
                'top. Click <b>Next</b> when done.'
            ),
            get_target=lambda win: _poster_tool(win, win.align_action),
            auto_advance=False,
            requires=lambda win: _poster_n_images(win) >= 2,
            requires_text='This step needs photos on the page (Step 1).',
            prepare=_poster_prep_images(4),
        ),
        TutorialStep(
            title='Step 5 — Add a title',
            message=(
                'Click <b>Add text…</b> (the arrow next to it offers heading sizes '
                'H1 / H2 / H3 that scale with the page). Type your text, format it, '
                'and click Ok.<br><br>'
                '<b>Double-click</b> any text box later to edit it.'
            ),
            get_target=lambda win: _poster_tool(win, win.add_text_action),
            completion_check=lambda win: bool(_poster_items(win, 'PosterText')),
        ),
        TutorialStep(
            title='Step 6 — Set a background',
            message=(
                'Click <b>Set background…</b> and choose an image: it fills the page '
                'behind everything.<br><br>'
                'Drag it to reposition, scroll to zoom it; <b>Reset background '
                'position</b> centres it again, <b>Clear background</b> removes it.'
            ),
            get_target=lambda win: _poster_tool(win, win.bg_action),
            completion_check=lambda win: win.canvas.background is not None,
            requires=lambda win: win.canvas.background is not None,
            requires_text='No background picture to hand? Use a sample one.',
            prepare=_poster_prep_background,
        ),
        pages,
        TutorialStep(
            title='Step 8 — Save',
            message=(
                f'Click <b>Save</b>. {saved_as}<br><br>'
                'Image paths are stored relative to the document too, so the folder '
                'can be moved or shared without breaking it.'
            ),
            get_target=lambda win: _poster_tool(win, win.save_action),
            completion_check=_poster_is_saved,
        ),
        TutorialStep(
            title='Step 9 — Export and share',
            message=(
                'Pick the export that fits:<br>'
                '• <b>Export image / PDF…</b> — the current page<br>'
                '• <b>Export whole document (PDF)…</b> — every page in one PDF<br>'
                '• <b>Print-ready export…</b> — high-DPI TIFF/EPS (CMYK) for a print shop<br>'
                '• <b>Export as web photo book…</b> — one HTML file with a page-flip '
                'viewer, to email or upload<br>'
                '• <b>Export source-data bundle…</b> — a self-contained folder<br><br>'
                'Click <b>Next</b> when done.'
            ),
            get_target=lambda win: _poster_tool(win, win.export_album_action),
            auto_advance=False,
        ),
        TutorialStep(
            title='Step 10 — Build it from a recipe',
            message=(
                '<b>Build from recipe…</b> creates a whole poster or album from a '
                'short YAML/JSON file: page size, album mode, backgrounds, photos or '
                'whole folders (wildcards allowed), the arrangement of each page and '
                'its text.<br><br>'
                'The same recipe runs from the command line '
                '(<code>poster_headless build</code>) and through the MCP server. '
                'See <code>docs/poster.md</code>.'
            ),
            get_target=lambda win: _poster_tool(win, win.recipe_action),
            auto_advance=False,
        ),
        done,
    ]
