"""Standalone poster/collage designer window.

Launched independently of the main scientific-figure editor (see the "Tools >
Poster / collage designer..." menu action added in pyfigures.gui.pfgui): it is
its own QMainWindow, does not subclass or embed EZFIG_GUI, and does not touch
any of its state. Closing it has no effect on the main editor and vice versa.
"""
from batoolset.settings.global_settings import set_UI
set_UI()

import json
import sys

from qtpy.QtCore import Qt, QSize, QPointF
from qtpy.QtWidgets import (
    QMainWindow, QToolBar, QScrollArea, QFileDialog, QMessageBox, QComboBox,
    QLabel, QWidget, QHBoxLayout, QVBoxLayout, QAction, QToolButton, QMenu,
    QDockWidget, QListWidget, QListWidgetItem, QPushButton, QInputDialog
)
from qtpy.QtGui import QKeySequence, QPalette, QIcon, QPixmap, QPainter

from batoolset.icons.tools import get_icon
from pyfigures.gui.theme import resolve_theme
from pyfigures.gui.user_prefs import load_theme
from pyfigures.poster.poster_canvas import PosterCanvas, _MmToPx
from pyfigures.poster.poster_shapes import TEXT_STYLE_PRESETS, TEXT_STYLE_ORDER

from pyfigures.poster.page_presets import PAGE_PRESETS

IMAGE_FILE_FILTER = 'Images (*.png *.jpg *.jpeg *.bmp *.tif *.tiff)'
# "Add image..." also accepts a .pyf scientific figure: it's flattened to a
# plain PNG (see poster_canvas._render_pyf_to_png) and added exactly like any
# other photo from then on, same as a drag-and-drop of a .pyf.
ADD_IMAGE_FILE_FILTER = ('Images and figures (*.png *.jpg *.jpeg *.bmp *.tif *.tiff *.pyf);;'
                        'Images (*.png *.jpg *.jpeg *.bmp *.tif *.tiff);;'
                        'PyFigures figure (*.pyf)')


class PosterWindow(QMainWindow):
    """The poster / collage designer, or with *album* the photo album
    designer (pfgui's Tools menu, `python -m pyfigures.album`). The two are
    kept apart: a poster window never turns into a photo album, and each
    refuses to open the other's documents (see open_poster)."""

    def __init__(self, parent=None, album=False):
        super().__init__(parent)
        self.album = bool(album)
        self.tool_name = 'Photo Album Designer' if self.album else 'Poster / Collage Designer'
        self.setWindowTitle(f'PyFigures — {self.tool_name}')
        from pyfigures.icons import app_icon
        self.setWindowIcon(app_icon('pyfigures_album' if self.album else 'pyfigures_poster'))

        self.canvas = PosterCanvas(page_width_mm=210.0, page_height_mm=297.0)
        if self.album:
            self.canvas.new_document(album=True)
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidget(self.canvas)
        self.scroll_area.setWidgetResizable(False)
        self.scroll_area.setAlignment(Qt.AlignCenter)
        # Same dark "mat" role the main editor's canvas surround uses
        # (scrollableEZFIG.py: self.scrollArea.setBackgroundRole(QPalette.Dark)).
        self.scroll_area.setBackgroundRole(QPalette.Dark)
        self.setCentralWidget(self.scroll_area)

        self._build_toolbar()
        self._build_page_dock()
        self._update_undo_redo_buttons()
        self._reload_toolbar_icons(resolve_theme(load_theme()))
        self.resize(1100, 850)

    # ---- UI setup -------------------------------------------------

    # icon names deliberately mirror the main editor's toolbar
    # (pyfigures/gui/pfgui.py _TOOLBAR_ICON_MAP / scrollableEZFIG.py) wherever
    # an equivalent action exists there, so the two tools read as one family.
    _TOOLBAR_ICON_MAP = [
        ('new_action', 'mdi.newspaper-plus'),
        ('open_action', 'fa.folder-open-o'),
        ('recipe_action', 'mdi.script-text-outline'),
        ('save_action', 'fa.save'),
        ('save_as_action', 'mdi.content-save-edit-outline'),
        ('export_action', 'mdi.export'),
        ('export_album_action', 'mdi.book-open-page-variant-outline'),
        ('export_print_action', 'mdi.printer-outline'),
        ('export_source_data_action', 'mdi.folder-zip-outline'),
        ('export_web_action', 'mdi.book-open-page-variant'),
        ('undo_action', 'fa5s.undo'),
        ('redo_action', 'fa5s.redo'),
        ('add_image_action', 'mdi.image-plus'),
        ('add_text_action', 'mdi.format-title'),
        ('bg_action', 'mdi.wallpaper'),
        ('clear_bg_action', 'mdi.image-off-outline'),
        ('reset_bg_view_action', 'mdi.backup-restore'),
        ('delete_action', 'fa.trash'),
        ('raise_action', 'mdi.arrange-bring-to-front'),
        ('lower_action', 'mdi.arrange-send-to-back'),
        ('ungroup_action', 'mdi.ungroup'),
        ('align_action', 'mdi.align-horizontal-left'),
        ('distribute_action', 'mdi.distribute-horizontal-center'),
        ('scatter_action', 'mdi.shuffle-variant'),
        ('fan_action', 'mdi.cards-outline'),
        ('grid_action', 'mdi.view-grid-outline'),
        ('layouts_action', 'mdi.view-dashboard-outline'),
        ('zoom_in_action', 'ei.zoom-in'),
        ('zoom_out_action', 'ei.zoom-out'),
        ('zoom_reset_action', 'ei.resize-full'),
        ('tutorial_action', 'mdi.school-outline'),
    ]

    def _build_toolbar(self):
        bar = QToolBar('Poster tools', self)
        bar.setMovable(False)
        self.addToolBar(bar)

        self.new_action = QAction('New', self)
        self.new_action.triggered.connect(self.new_poster)
        bar.addAction(self.new_action)

        self.open_action = QAction('Open…', self)
        self.open_action.setShortcut(QKeySequence.Open)
        self.open_action.triggered.connect(self.open_poster)
        bar.addAction(self.open_action)

        self.recipe_action = QAction('Build from recipe…', self)
        self.recipe_action.setToolTip('Build a whole poster or photo album from a YAML/JSON recipe '
                                      '(pages, backgrounds, photos or folders, arrangement, text) — '
                                      'the same recipe the command line and the MCP server use.')
        self.recipe_action.triggered.connect(self.build_from_recipe)
        bar.addAction(self.recipe_action)

        self.save_action = QAction('Save', self)
        self.save_action.setShortcut(QKeySequence.Save)
        self.save_action.triggered.connect(self.save_poster)
        bar.addAction(self.save_action)

        self.save_as_action = QAction('Save As…', self)
        self.save_as_action.triggered.connect(self.save_poster_as)
        bar.addAction(self.save_as_action)

        self.export_action = QAction('Export image / PDF…', self)
        self.export_action.setToolTip('Export the current page only. For a multi-page document, '
                                      'use "Export whole document (PDF)…" instead.')
        self.export_action.triggered.connect(self.export_poster)
        bar.addAction(self.export_action)

        self.export_album_action = QAction('Export whole document (PDF)…', self)
        self.export_album_action.setToolTip('Export every page as one multi-page PDF — the whole '
                                            'photo album, front cover through back cover, in one '
                                            'file (works for a plain one-page document too).')
        self.export_album_action.triggered.connect(self.export_album)
        bar.addAction(self.export_album_action)

        self.export_print_action = QAction('Print-ready export…', self)
        self.export_print_action.setToolTip('High-DPI TIFF/EPS (optionally CMYK) or vector PDF/SVG, for '
                                            'sending to a print shop — current page or the whole document.')
        self.export_print_action.triggered.connect(self.export_print_ready)
        bar.addAction(self.export_print_action)

        self.export_source_data_action = QAction('Export source-data bundle…', self)
        self.export_source_data_action.setToolTip('Consolidate this document into a self-contained folder: '
                                                   'a portable copy plus every image/background file, copied '
                                                   'and renamed by page. Any photo flattened from a .pyf figure '
                                                   'gets that figure\'s own source-data bundle nested alongside '
                                                   'it. Saves the document first.')
        self.export_source_data_action.triggered.connect(self.export_source_data_bundle)
        bar.addAction(self.export_source_data_action)

        self.export_web_action = QAction('Export as web photo book…', self)
        self.export_web_action.setToolTip('A single, self-contained HTML file — every page embedded '
                                          "as an image, with a page-flip viewer. No app needed to view "
                                          "it, just a browser: email it, share the file, or upload it "
                                          "anywhere. The nicest way to send someone a photo album.")
        self.export_web_action.triggered.connect(self.export_web_album)
        bar.addAction(self.export_web_action)

        bar.addSeparator()

        # Whole-document snapshot undo/redo (see PosterCanvas._push_undo_checkpoint) —
        # covers every kind of edit (shape move/resize, text, page add/remove,
        # album-mode toggle, ...) uniformly.
        self.undo_action = QAction('Undo', self)
        self.undo_action.setShortcut(QKeySequence.Undo)
        self.undo_action.triggered.connect(self.canvas.undo)
        bar.addAction(self.undo_action)

        self.redo_action = QAction('Redo', self)
        self.redo_action.setShortcuts([QKeySequence('Ctrl+Shift+Z'), QKeySequence('Ctrl+Y')])
        self.redo_action.triggered.connect(self.canvas.redo)
        bar.addAction(self.redo_action)

        self.canvas.undo_redo_changed.connect(self._update_undo_redo_buttons)

        bar.addSeparator()

        self.add_image_action = QAction('Add image…', self)
        self.add_image_action.triggered.connect(self.add_image)
        bar.addAction(self.add_image_action)

        self.add_text_action = QAction('Add text…', self)
        self.add_text_action.setToolTip('Add a body-sized text box — rich formatting (bold, color, '
                                        'font, Greek letters); double-click any text box later to '
                                        'edit it again. Use the dropdown arrow for a heading size '
                                        '(H1/H2/H3), sized as a fraction of the page so it scales '
                                        'with the page size instead of a fixed point size.')
        self.add_text_action.triggered.connect(lambda: self.add_text('body'))
        bar.addAction(self.add_text_action)
        add_text_button = bar.widgetForAction(self.add_text_action)
        if add_text_button is not None:
            text_style_menu = QMenu(self)
            for key in TEXT_STYLE_ORDER:
                action = text_style_menu.addAction(TEXT_STYLE_PRESETS[key]['label'])
                action.triggered.connect(lambda checked, k=key: self.add_text(k))
            add_text_button.setMenu(text_style_menu)
            add_text_button.setPopupMode(QToolButton.MenuButtonPopup)

        self.bg_action = QAction('Set background…', self)
        self.bg_action.triggered.connect(self.set_background)
        bar.addAction(self.bg_action)

        self.clear_bg_action = QAction('Clear background', self)
        self.clear_bg_action.triggered.connect(self.canvas.clear_background)
        bar.addAction(self.clear_bg_action)

        self.reset_bg_view_action = QAction('Reset background position', self)
        self.reset_bg_view_action.setToolTip('Drag the background to reposition it, scroll to zoom/crop '
                                             'it tighter; this resets it back to centered, no zoom.')
        self.reset_bg_view_action.triggered.connect(self.canvas.reset_background_view)
        bar.addAction(self.reset_bg_view_action)

        bar.addSeparator()

        self.delete_action = QAction('Delete selected', self)
        self.delete_action.setShortcut(QKeySequence.Delete)
        self.delete_action.triggered.connect(self.canvas.delete_selected)
        bar.addAction(self.delete_action)

        self.raise_action = QAction('Bring to front', self)
        self.raise_action.triggered.connect(self.canvas.raise_selected)
        bar.addAction(self.raise_action)

        self.lower_action = QAction('Send to back', self)
        self.lower_action.triggered.connect(self.canvas.lower_selected)
        bar.addAction(self.lower_action)

        self.ungroup_action = QAction('Ungroup', self)
        self.ungroup_action.setToolTip('A layout applied/sketched as one block can be dragged as a '
                                       "unit; this breaks it apart so its photos move independently again.")
        self.ungroup_action.triggered.connect(self.canvas.ungroup_selected)
        bar.addAction(self.ungroup_action)

        self.align_action = QAction('Align', self)
        self.align_action.setToolTip('Shift+click several shapes to select them, then pick how to '
                                     'align them to each other (left/right/top/bottom edges, or '
                                     'centers) — uses the selection\'s own bounding box as the target, '
                                     'like PowerPoint/Illustrator\'s align tools.')
        bar.addAction(self.align_action)
        align_button = bar.widgetForAction(self.align_action)
        if align_button is not None:
            align_menu = QMenu(self)
            for label, mode in [('Align left', 'left'), ('Align right', 'right'),
                                ('Align top', 'top'), ('Align bottom', 'bottom'),
                                ('Align center (horizontal)', 'center_h'),
                                ('Align center (vertical)', 'center_v')]:
                action = align_menu.addAction(label)
                action.triggered.connect(lambda checked, m=mode: self.canvas.align_selected(m))
            align_button.setMenu(align_menu)
            align_button.setPopupMode(QToolButton.InstantPopup)
            # No single obvious "default" alignment to run on a plain click
            # (unlike Add text/Layout) — every click opens the menu, so show
            # the label to make that discoverable rather than icon-only.
            align_button.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)

        self.distribute_action = QAction('Distribute', self)
        self.distribute_action.setToolTip("Evenly space 3+ selected shapes' centers between the two "
                                          'outermost ones (Shift+click to select more than one).')
        bar.addAction(self.distribute_action)
        distribute_button = bar.widgetForAction(self.distribute_action)
        if distribute_button is not None:
            distribute_menu = QMenu(self)
            for label, axis in [('Distribute horizontally', 'x'), ('Distribute vertically', 'y')]:
                action = distribute_menu.addAction(label)
                action.triggered.connect(lambda checked, a=axis: self.canvas.distribute_selected(a))
            distribute_button.setMenu(distribute_menu)
            distribute_button.setPopupMode(QToolButton.InstantPopup)
            distribute_button.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)

        bar.addSeparator()

        self.scatter_action = QAction('Scatter', self)
        self.scatter_action.setToolTip('Scatter every image on the page like photos thrown on a '
                                       'table (random position + random tilt).')
        self.scatter_action.triggered.connect(self.arrange_scatter)
        bar.addAction(self.scatter_action)

        self.fan_action = QAction('Fan', self)
        self.fan_action.setToolTip('Fan every image out along an arc, like a spread hand of photographs.')
        self.fan_action.triggered.connect(self.arrange_fan)
        bar.addAction(self.fan_action)

        self.grid_action = QAction('Grid', self)
        self.grid_action.setToolTip('Lay every image out in a tidy grid (rotation reset, resized to fit).')
        self.grid_action.triggered.connect(self.arrange_grid)
        bar.addAction(self.grid_action)

        self.layouts_action = QAction('Layout', self)
        self.layouts_action.setToolTip('Pick a pre-designed page layout (like a PowerPoint slide '
                                       'layout), fill its slots with the photos on the page, or '
                                       'sketch it as empty slots to fill in later.')
        self.layouts_action.triggered.connect(self.choose_layout)
        bar.addAction(self.layouts_action)
        # No separate top-level "Layout" menu — this is the one entry point,
        # so show its label beside the icon rather than icon-only like the
        # rest of the toolbar, to keep it easy to find.
        layouts_button = bar.widgetForAction(self.layouts_action)
        if layouts_button is not None:
            layouts_button.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)

        bar.addSeparator()

        # Same 10%-per-click zoom + Ctrl +/-/0 shortcuts as the main editor's
        # scrollableEZFIG.zoomIn/zoomOut/zoom_reset — no percentage readout there
        # either, so the poster tool doesn't invent one.
        self.zoom_in_action = QAction('Zoom+', self)
        self.zoom_in_action.setShortcuts([QKeySequence('Ctrl++'), QKeySequence('Ctrl+Shift+=')])
        self.zoom_in_action.triggered.connect(self.canvas.zoom_in)
        bar.addAction(self.zoom_in_action)

        self.zoom_out_action = QAction('Zoom-', self)
        self.zoom_out_action.setShortcuts([QKeySequence('Ctrl+-'), QKeySequence('Ctrl+Shift+-')])
        self.zoom_out_action.triggered.connect(self.canvas.zoom_out)
        bar.addAction(self.zoom_out_action)

        self.zoom_reset_action = QAction('Reset zoom', self)
        self.zoom_reset_action.setShortcut(QKeySequence('Ctrl+0'))
        self.zoom_reset_action.triggered.connect(self.canvas.zoom_reset)
        bar.addAction(self.zoom_reset_action)

        self.tutorial_action = QAction('Tutorial', self)
        self.tutorial_action.setToolTip('Guided tour of the poster / photo-album designer')
        self.tutorial_action.triggered.connect(self.start_tutorial)
        bar.addAction(self.tutorial_action)

        bar.addSeparator()

        page_widget = QWidget()
        page_layout = QHBoxLayout(page_widget)
        page_layout.setContentsMargins(4, 0, 4, 0)
        page_layout.addWidget(QLabel('Page:'))
        self.page_combo = QComboBox()
        self.page_combo.addItems(list(PAGE_PRESETS.keys()) + ['Custom'])
        self.page_combo.setCurrentText('A4')
        self.page_combo.currentTextChanged.connect(self._on_page_preset_changed)
        page_layout.addWidget(self.page_combo)
        bar.addWidget(page_widget)

    def _on_page_preset_changed(self, name):
        if name in PAGE_PRESETS:
            w, h = PAGE_PRESETS[name]
            self.canvas.set_page_size_mm(w, h)
            self._refresh_page_list()

    def _reload_toolbar_icons(self, theme_name):
        """Tint every toolbar icon for *theme_name* ('light'/'dark'), mirroring
        pyfigures.gui.pfgui.EZFIG_GUI._reload_toolbar_icons so both tools' icons
        stay visible/contrasted together when the user switches theme."""
        if theme_name == 'dark':
            color, color_disabled = '#dcdcdc', '#555555'
        else:
            color, color_disabled = '#404040', 'lightgray'
        for attr, icon_name in self._TOOLBAR_ICON_MAP:
            action = getattr(self, attr, None)
            if action is not None:
                action.setIcon(get_icon(icon_name, color=color, color_disabled=color_disabled))

    # ---- page navigator (multi-page documents / photo albums) -------------------------------------------------
    # A document is one page until add_page() is used (front/back covers,
    # interior spreads — see poster_shapes.PAGE_KINDS); this dock is where
    # that happens and where pages are browsed/reordered/removed. Nothing
    # here is required for a plain one-page poster.

    def _build_page_dock(self):
        dock = QDockWidget('Pages', self)
        dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(4, 4, 4, 4)

        # No poster <-> album switch here: photo albums have their own
        # designer (album=True), which pins the covers for good.
        if self.album:
            hint = QLabel('Front cover, spreads (two pages side by side, so a photo or text can '
                          'sit right across the middle) and back cover.')
            hint.setWordWrap(True)
            layout.addWidget(hint)

        self.page_list = QListWidget()
        self.page_list.setIconSize(QSize(64, 64))
        self.page_list.currentRowChanged.connect(self._on_page_row_changed)
        layout.addWidget(self.page_list)

        add_row = QHBoxLayout()
        add_button = QToolButton()
        add_button.setText('+ Page')
        self.page_add_button = add_button
        add_menu = QMenu(self)
        self.page_add_menu = add_menu
        add_menu.addAction('Spread (two pages)', lambda: self._add_page('spread'))
        self._cover_front_action = add_menu.addAction('Front cover', lambda: self._add_page('cover_front'))
        self._cover_back_action = add_menu.addAction('Back cover', lambda: self._add_page('cover_back'))
        self._plain_page_action = add_menu.addAction('Plain page', lambda: self._add_page('single'))
        for action in (self._cover_front_action, self._cover_back_action, self._plain_page_action):
            action.setVisible(not self.album)              # an album only ever adds spreads
        add_button.setMenu(add_menu)
        add_button.setPopupMode(QToolButton.InstantPopup)
        add_row.addWidget(add_button)

        self.page_dup_button = QPushButton('Duplicate')
        self.page_dup_button.clicked.connect(self._duplicate_page)
        add_row.addWidget(self.page_dup_button)

        self.page_del_button = QPushButton('Delete')
        self.page_del_button.clicked.connect(self._remove_page)
        add_row.addWidget(self.page_del_button)
        layout.addLayout(add_row)

        move_row = QHBoxLayout()
        self.page_up_button = QPushButton('▲ Move up')
        self.page_up_button.clicked.connect(lambda: self._move_page(-1))
        move_row.addWidget(self.page_up_button)
        self.page_down_button = QPushButton('▼ Move down')
        self.page_down_button.clicked.connect(lambda: self._move_page(1))
        move_row.addWidget(self.page_down_button)
        layout.addLayout(move_row)

        dock.setWidget(container)
        self.addDockWidget(Qt.LeftDockWidgetArea, dock)
        self.page_dock = dock
        self._refresh_page_list()

    def _add_page(self, kind):
        self.canvas.add_page(kind=kind)
        self._refresh_page_list()

    def _duplicate_page(self):
        self.canvas.duplicate_page()
        self._refresh_page_list()

    def _remove_page(self):
        if self.canvas.page_count() <= 1:
            QMessageBox.information(self, 'Only page', 'A document always keeps at least one page.')
            return
        i = self.canvas.current_page_index
        if self.canvas.album_mode and i in (0, self.canvas.page_count() - 1):
            QMessageBox.information(self, 'Cover page', 'A photo album always keeps its front and '
                                    'back covers.')
            return
        self.canvas.remove_page()
        self._refresh_page_list()

    def _move_page(self, delta):
        i = self.canvas.current_page_index
        j = i + delta
        last = self.canvas.page_count() - 1
        if self.canvas.album_mode and (i in (0, last) or not (0 <= j <= last) or j in (0, last)):
            return
        if 0 <= j < self.canvas.page_count():
            self.canvas.move_page(i, j)
            self._refresh_page_list()

    def _on_page_row_changed(self, row):
        if row < 0:
            return
        old_row = self.canvas.current_page_index
        if row == old_row:
            return
        if 0 <= old_row < self.page_list.count():
            # Refresh the thumbnail/label of the page being left, in case it
            # was edited since the list was last rebuilt — cheaper than
            # rebuilding every row on every navigation.
            self.page_list.item(old_row).setIcon(QIcon(self._page_thumbnail(old_row)))
            self.page_list.item(old_row).setText(self.canvas.page_label(old_row))
        self.canvas.goto_page(row)
        self._sync_page_size_combo()
        self._refresh_page_action_states()

    def _refresh_page_list(self):
        self.page_list.blockSignals(True)
        self.page_list.clear()
        for i in range(self.canvas.page_count()):
            item = QListWidgetItem(self.canvas.page_label(i))
            item.setIcon(QIcon(self._page_thumbnail(i)))
            self.page_list.addItem(item)
        self.page_list.setCurrentRow(self.canvas.current_page_index)
        self.page_list.blockSignals(False)
        self._sync_page_size_combo()
        self._refresh_page_action_states()

    def _refresh_page_action_states(self):
        # In album mode covers are pinned (new_document(album=True)) — the
        # manual "add a cover"/"add a plain page" choices and the
        # duplicate/delete/move actions on a cover slot are all disabled
        # rather than left to silently no-op.
        album = self.canvas.album_mode
        self._cover_front_action.setEnabled(not album)
        self._cover_back_action.setEnabled(not album)
        self._plain_page_action.setEnabled(not album)

        i = self.canvas.current_page_index
        last = self.canvas.page_count() - 1
        on_cover = album and i in (0, last)
        self.page_dup_button.setEnabled(not on_cover)
        self.page_del_button.setEnabled(not on_cover)
        self.page_up_button.setEnabled(not on_cover and i > (1 if album else 0))
        self.page_down_button.setEnabled(not on_cover and i < last - (1 if album else 0))

    def _page_thumbnail(self, index, max_size=64):
        """A small rendered preview of page *index*, reusing the canvas's own
        paint code (temporarily pointed at that page) rather than a second
        drawing implementation — same idea as PosterCanvas.export_album_pdf."""
        page = self.canvas.pages[index]
        scale = max_size / max(page.width_mm, page.height_mm)
        w, h = max(1, round(page.width_mm * scale)), max(1, round(page.height_mm * scale))
        pixmap = QPixmap(w, h)
        pixmap.fill(Qt.white)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
        saved_index = self.canvas.current_page_index
        self.canvas.current_page_index = index
        mm_to_px = _MmToPx(scale=scale, origin=QPointF(0.0, 0.0))
        self.canvas._paint_content(painter, mm_to_px)
        self.canvas.current_page_index = saved_index
        painter.end()
        return pixmap

    def _sync_page_size_combo(self):
        w, h = self.canvas.page_width_mm, self.canvas.page_height_mm
        match = next((name for name, (pw, ph) in PAGE_PRESETS.items()
                     if abs(pw - w) < 0.01 and abs(ph - h) < 0.01), 'Custom')
        self.page_combo.blockSignals(True)
        self.page_combo.setCurrentText(match)
        self.page_combo.blockSignals(False)

    # ---- actions -------------------------------------------------

    def _update_undo_redo_buttons(self):
        self.undo_action.setEnabled(self.canvas.can_undo())
        self.redo_action.setEnabled(self.canvas.can_redo())
        # An undo/redo can change page count/kind/album_mode just like any
        # other edit — keep the Pages dock in sync with whatever the
        # snapshot just restored.
        self._refresh_page_list()
        self._update_title()

    def _update_title(self):
        import os
        name = os.path.basename(self.canvas.file_path) if self.canvas.file_path else 'Untitled'
        star = '*' if self.canvas.is_modified() else ''
        self.setWindowTitle(f'{star}{name} — PyFigures {self.tool_name}')

    def _confirm_discard(self):
        """True if it's fine to replace/close the current document: nothing
        unsaved, or the user saved it / chose to discard the changes."""
        if not self.canvas.is_modified():
            return True
        answer = QMessageBox.question(
            self, 'Unsaved changes', 'This poster has unsaved changes. Save them first?',
            QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel, QMessageBox.Save)
        if answer == QMessageBox.Cancel:
            return False
        if answer == QMessageBox.Save:
            return self.save_poster()
        return True

    def closeEvent(self, event):
        if self._confirm_discard():
            if getattr(self, '_tutorial', None) is not None:
                self._tutorial.stop()
            event.accept()
        else:
            event.ignore()

    def start_tutorial(self):
        """Guided tour of this window (also Help → Poster Tutorial / Photo
        Album Tutorial in the figure editor)."""
        from pyfigures.gui.tutorial import TutorialController, poster_steps
        if getattr(self, '_tutorial', None) is None:
            self._tutorial = TutorialController(self)
        self.show()
        self.raise_()
        self._tutorial.start(poster_steps(album=self.album))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if getattr(self, '_tutorial', None) is not None:
            self._tutorial.handle_resize()

    def new_poster(self):
        if not self._confirm_discard():
            return
        self.canvas.new_document(album=self.album)
        self._refresh_page_list()
        self._update_title()

    def add_image(self):
        path, _ = QFileDialog.getOpenFileName(self, 'Add image', '', ADD_IMAGE_FILE_FILTER)
        if not path:
            return
        if path.lower().endswith('.pyf'):
            self.add_figure_file(path)
            return
        try:
            self.canvas.add_image(path)
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, 'Could not add image', str(exc))

    def add_figure_file(self, pyf_path):
        """Add a .pyf scientific figure: shown from its flatten, remembered so
        PDF/SVG exports draw it as vectors (also the figure editor's
        Tools > Send this figure to the poster designer). Returns the shape."""
        from pyfigures.poster.poster_canvas import _render_pyf_to_png
        try:
            png = _render_pyf_to_png(pyf_path, parent=self)
        except Exception as exc:
            QMessageBox.critical(self, 'Could not render figure', str(exc))
            return None
        try:
            return self.canvas.add_image(png, source_pyf=pyf_path)
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, 'Could not add image', str(exc))
            return None

    def add_text(self, style='body'):
        shape = self.canvas.add_text(style=style)
        self.canvas.edit_text(shape)

    def set_background(self):
        path, _ = QFileDialog.getOpenFileName(self, 'Set background image', '', IMAGE_FILE_FILTER)
        if not path:
            return
        try:
            self.canvas.check_image_readable(path)
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, 'Could not set background', str(exc))
            return
        self.canvas.set_background(path)

    def open_poster(self, path=None):
        if not self._confirm_discard():
            return
        if not path:
            if self.album:
                path, _ = QFileDialog.getOpenFileName(self, 'Open photo album', '',
                                                      'PyFigures album (*.pyfalbum)')
            else:
                path, _ = QFileDialog.getOpenFileName(
                    self, 'Open poster', '',
                    'PyFigures poster/album (*.pyfposter *.pyfalbum);;'
                    'PyFigures poster (*.pyfposter);;PyFigures album (*.pyfalbum)')
        if not path:
            return
        if not self._refuse_other_designers_file(path):
            return
        try:
            self.canvas.load(path)
        except Exception as exc:
            QMessageBox.critical(self, 'Could not open poster', str(exc))
            return
        self._refresh_page_list()
        self._update_title()
        missing = self.canvas.missing_files()
        if missing:
            lines = [f'page {pi + 1} {role}: {p}' for pi, role, p in missing[:15]]
            if len(missing) > 15:
                lines.append(f'… and {len(missing) - 15} more')
            QMessageBox.warning(self, 'Missing images',
                                f'{len(missing)} image file(s) used by this document can no longer '
                                'be found (moved, renamed or deleted); they show as grey boxes:\n\n'
                                + '\n'.join(lines))

    def _refuse_other_designers_file(self, path, is_album=None):
        """True if *path* (or a recipe whose `album:` is *is_album*) belongs
        in this window; otherwise says which designer opens it and returns
        False. Photo albums only open in the photo album designer, posters
        and plain multi-page documents only in the poster designer."""
        import os
        if is_album is None:
            if not os.path.isfile(path):
                return True                    # load() reports the real error
            from pyfigures.poster.serialization import is_photo_album
            is_album = is_photo_album(path)
        if is_album == self.album:
            return True
        if is_album:
            QMessageBox.information(self, 'Photo album',
                                    f'{os.path.basename(path)} is a photo album: open it in the photo '
                                    'album designer (Tools > Photo album designer… in the figure '
                                    'editor, or python -m pyfigures.album).')
        else:
            QMessageBox.information(self, 'Not a photo album',
                                    f'{os.path.basename(path)} is a poster, not a photo album: open it '
                                    'in the poster designer (Tools > Poster / collage designer… in '
                                    'the figure editor, or python -m pyfigures.poster).')
        return False

    def build_from_recipe(self, path=None):
        """Build the document a recipe describes (see poster_recipe.py), save
        it where the recipe says, and open it here."""
        if not self._confirm_discard():
            return
        if not path:
            path, _ = QFileDialog.getOpenFileName(self, 'Build poster from recipe', '',
                                                  'Recipe (*.yaml *.yml *.json)')
        if not path:
            return
        from pyfigures.poster.poster_recipe import build_poster_from_recipe, load_recipe, plan_recipe
        try:
            plan = plan_recipe(load_recipe(path), path)
        except Exception:
            plan = None                        # build_poster_from_recipe reports the mistake below
        if plan is not None and not self._refuse_other_designers_file(path, is_album=plan['album']):
            return
        try:
            result = build_poster_from_recipe(path, canvas=self.canvas)
        except Exception as exc:
            QMessageBox.critical(self, 'Recipe failed', str(exc))
            self._refresh_page_list()
            self._update_title()
            return
        self._refresh_page_list()
        self._update_title()
        extra = ''.join(f'\n{k}: {result[k]}' for k in ('render', 'web') if k in result)
        QMessageBox.information(self, 'Recipe built',
                                f"{result['page_count']} page(s), {result['image_count']} image(s) → "
                                f"{result['output']}{extra}")

    def _save_to(self, path):
        try:
            self.canvas.save(path, filetype=self.canvas.suggested_filetype())
        except Exception as exc:
            QMessageBox.critical(self, 'Could not save', f'{path}\n\n{exc}')
            return False
        self._update_title()
        return True

    def save_poster(self):
        """Save to the current file (asks for one the first time). Returns
        True when the document was written. A single-page poster that has
        since become an album is saved next to it as .pyfalbum rather than
        over the .pyfposter (which can only hold one plain page)."""
        path = self.canvas.file_path
        if not path:
            return self.save_poster_as()
        ext = '.' + self.canvas.suggested_filetype()
        if not path.lower().endswith(ext):
            import os
            path = os.path.splitext(path)[0] + ext
        return self._save_to(path)

    def save_poster_as(self):
        if self.canvas.suggested_filetype() == 'pyfalbum':
            path, _ = QFileDialog.getSaveFileName(self, 'Save album as', '',
                                                  'PyFigures album (*.pyfalbum)')
            ext = '.pyfalbum'
        else:
            path, _ = QFileDialog.getSaveFileName(self, 'Save poster as', '',
                                                  'PyFigures poster (*.pyfposter)')
            ext = '.pyfposter'
        if not path:
            return False
        if not path.lower().endswith(ext):
            path += ext
        return self._save_to(path)

    def export_poster(self):
        path, _ = QFileDialog.getSaveFileName(
            self, 'Export current page', '',
            'PNG image (*.png);;JPEG image (*.jpg);;TIFF image (*.tif);;PDF (*.pdf);;SVG (*.svg)')
        if not path:
            return
        try:
            self.canvas.save(path)
        except Exception as exc:
            QMessageBox.critical(self, 'Export failed', f'{path}\n\n{exc}')

    def export_album(self):
        """Export every page as one multi-page PDF — the whole photo album
        (front cover through back cover) in one file, unlike export_poster
        which only ever renders the current page. Works for a plain one-page
        document too (a one-page "album")."""
        path, _ = QFileDialog.getSaveFileName(self, 'Export whole document as PDF', '', 'PDF (*.pdf)')
        if not path:
            return
        if not path.lower().endswith('.pdf'):
            path += '.pdf'
        dpi, ok = QInputDialog.getItem(self, 'Export DPI', 'Choose a resolution (DPI):',
                                       ['72', '150', '300', '600'], 2, False)
        if not ok:
            return
        try:
            self.canvas.export_album_pdf(path, dpi=int(dpi))
        except Exception as exc:
            QMessageBox.critical(self, 'Export failed', f'{path}\n\n{exc}')

    def export_print_ready(self):
        """High-DPI TIFF/EPS (optionally CMYK) or vector PDF/SVG — current
        page or the whole document. Renders straight from the live canvas,
        no save required first (unlike export_source_data_bundle, this
        never touches the document's own image paths)."""
        scope, ok = QInputDialog.getItem(self, 'Print-ready export', 'Export:',
                                         ['Current page', 'Whole document'], 0, False)
        if not ok:
            return
        whole = scope == 'Whole document'
        fmt, ok = QInputDialog.getItem(self, 'Print-ready export', 'Format:',
                                       ['tiff', 'eps', 'pdf', 'svg'], 0, False)
        if not ok:
            return
        color_mode = 'rgb'
        if fmt in ('tiff', 'eps'):
            color_mode, ok = QInputDialog.getItem(self, 'Print-ready export', 'Colour mode:',
                                                  ['cmyk', 'rgb'], 0, False)
            if not ok:
                return
        dpi_str, ok = QInputDialog.getItem(self, 'Print-ready export', 'DPI:',
                                           ['150', '300', '600'], 1, False)
        if not ok:
            return
        dpi = int(dpi_str)
        ext = 'tif' if fmt == 'tiff' else fmt

        if whole and fmt in ('tiff', 'eps', 'svg'):
            out_dir = QFileDialog.getExistingDirectory(
                self, 'Choose output folder (one file per page + manifest.json)')
            if not out_dir:
                return
            try:
                result = self.canvas.export_album_print_ready(out_dir, filetype=fmt,
                                                               color_mode=color_mode, dpi=dpi)
            except Exception as exc:
                QMessageBox.critical(self, 'Print export failed', str(exc))
                return
            QMessageBox.information(self, 'Print-ready export',
                                    f"Wrote {len(result['files'])} page(s) to:\n{out_dir}")
            return

        path, _ = QFileDialog.getSaveFileName(self, 'Export print-ready file', '', f'{fmt.upper()} (*.{ext})')
        if not path:
            return
        if not path.lower().endswith(f'.{ext}'):
            path += f'.{ext}'
        try:
            if whole:
                self.canvas.export_album_print_ready(path, filetype=fmt, color_mode=color_mode, dpi=dpi)
            else:
                self.canvas.export_print_ready(path, filetype=fmt, color_mode=color_mode, dpi=dpi)
        except Exception as exc:
            QMessageBox.critical(self, 'Print export failed', str(exc))
            return
        QMessageBox.information(self, 'Print-ready export', f'Wrote:\n{path}')

    def export_source_data_bundle(self):
        """Consolidate the document into a self-contained folder (see
        poster_source_data.export_poster_source_data). Saves first — the
        bundle is built from the file on disk (via the same headless
        subprocess the MCP tool uses), never from the live canvas, since
        consolidating rewrites image paths and that must never happen to
        the document currently open for editing."""
        if not self.save_poster() or not self.canvas.file_path:
            return  # user cancelled Save As, or the save failed (already reported)
        out_dir = QFileDialog.getExistingDirectory(self, 'Choose output folder for the source-data bundle')
        if not out_dir:
            return
        import subprocess
        cmd = [sys.executable, '-m', 'pyfigures.poster.poster_headless', 'export-source-data',
              self.canvas.file_path, out_dir]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            QMessageBox.critical(self, 'Consolidation failed', proc.stderr or proc.stdout)
            return
        try:
            result = json.loads(proc.stdout)
        except Exception:
            result = {}
        QMessageBox.information(
            self, 'Source-data bundle',
            f"Wrote {result.get('n_files', '?')} file(s) "
            f"({result.get('nested_pyf_bundles', 0)} nested .pyf bundle(s)) to:\n{out_dir}")

    def export_web_album(self):
        """A single self-contained .html photo book (see
        PosterCanvas.export_album_web) — safe to build straight from the
        live canvas since, unlike consolidation, this never rewrites any
        path on the document itself."""
        path, _ = QFileDialog.getSaveFileName(self, 'Export as web photo book', '', 'HTML (*.html)')
        if not path:
            return
        if not path.lower().endswith('.html'):
            path += '.html'
        try:
            result = self.canvas.export_album_web(path)
        except Exception as exc:
            QMessageBox.critical(self, 'Web export failed', str(exc))
            return
        QMessageBox.information(
            self, 'Web photo book',
            f"Wrote a {result['page_count']}-page photo book to:\n{path}\n\n"
            "Open it in any browser, or share the file directly — everything "
            "needed to view it is inside.")

    # ---- automatic arrangement -------------------------------------------------
    # Same pure functions the headless MCP tools use (pyfigures.poster.poster_layouts)
    # — one click here does exactly what an MCP arrange_poster_* call would do.

    def arrange_scatter(self):
        self.canvas.arrange('scatter')

    def arrange_fan(self):
        self.canvas.arrange('fan')

    def arrange_grid(self):
        self.canvas.arrange('grid')

    def choose_layout(self):
        """Open the layout gallery (pyfigures.poster.poster_layout_dialog).
        Checking "Sketch as empty slots" adds the layout as unfilled
        placeholders (no photos needed yet — the main editor's
        templatify_figure/fill_template idea, built forwards); otherwise it
        fills the layout with every photo already on the page."""
        from pyfigures.poster.poster_layout_dialog import LayoutGalleryDialog
        from pyfigures.poster.poster_templates import layout_targets
        n_photos = len(layout_targets(self.canvas.shapes_to_draw))
        dlg = LayoutGalleryDialog(self, image_count=n_photos)
        if not (dlg.exec() and dlg.selected_layout):
            return
        if dlg.sketch_mode:
            self.canvas.sketch_layout(dlg.selected_layout)
            return
        if not n_photos:
            QMessageBox.information(self, 'No images', 'Add some images to the page first, '
                                    'or check "Sketch as empty slots" to lay the page out '
                                    'before you have any.')
            return
        self.canvas.arrange('layout', layout_name=dlg.selected_layout)
