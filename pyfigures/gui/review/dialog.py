"""Qt dialog for viewing imported review comments — the only Qt-dependent
piece of the review package (html_export.py has no GUI dependency at all)."""


def show_review_comments_dialog(parent, image_path: str, comments: list, on_clear=None):
    """Modal dialog: the flattened figure with numbered pins overlaid, plus a
    scrollable list of the comment text. *on_clear*, if given, is called with
    no args when the user clicks "Clear all" (owner has resolved everything)."""
    from qtpy.QtWidgets import (
        QDialog, QVBoxLayout, QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
        QPushButton, QScrollArea, QWidget,
    )
    from qtpy.QtGui import QPixmap, QPainter, QColor, QFont, QBrush, QPen
    from qtpy.QtCore import Qt

    dlg = QDialog(parent)
    dlg.setWindowTitle(f"Review comments ({len(comments)})")
    dlg.resize(900, 620)
    layout = QHBoxLayout(dlg)

    pixmap = QPixmap(image_path)
    if not comments:
        annotated = pixmap
    else:
        annotated = QPixmap(pixmap)
        painter = QPainter(annotated)
        painter.setRenderHint(QPainter.Antialiasing)
        radius = max(10, min(pixmap.width(), pixmap.height()) // 80)
        font = QFont()
        font.setBold(True)
        font.setPointSize(max(8, radius))
        painter.setFont(font)
        for i, c in enumerate(comments):
            cx = c.get("x", 0) * pixmap.width()
            cy = c.get("y", 0) * pixmap.height()
            painter.setBrush(QBrush(QColor(224, 68, 43)))
            painter.setPen(QPen(QColor(255, 255, 255), 2))
            painter.drawEllipse(int(cx - radius), int(cy - radius), radius * 2, radius * 2)
            painter.setPen(QPen(QColor(255, 255, 255)))
            painter.drawText(int(cx - radius), int(cy - radius), radius * 2, radius * 2,
                              Qt.AlignCenter, str(i + 1))
        painter.end()

    img_label = QLabel()
    img_label.setPixmap(annotated.scaledToWidth(560, Qt.SmoothTransformation) if annotated.width() > 560 else annotated)
    scroller = QScrollArea()
    scroller.setWidget(img_label)
    scroller.setWidgetResizable(True)
    layout.addWidget(scroller, 3)

    right = QVBoxLayout()
    list_widget = QListWidget()
    for i, c in enumerate(comments):
        author = c.get("author") or "anonymous"
        item_text = f"#{i + 1} — {author}\n{c.get('text', '')}"
        list_widget.addItem(QListWidgetItem(item_text))
    right.addWidget(QLabel(f"{len(comments)} comment(s)"))
    right.addWidget(list_widget)

    btn_row = QHBoxLayout()
    close_btn = QPushButton("Close")
    close_btn.clicked.connect(dlg.accept)
    btn_row.addWidget(close_btn)
    if on_clear is not None:
        clear_btn = QPushButton("Clear all (resolved)")

        def _do_clear():
            on_clear()
            dlg.accept()

        clear_btn.clicked.connect(_do_clear)
        btn_row.addWidget(clear_btn)
    right.addLayout(btn_row)

    right_widget = QWidget()
    right_widget.setLayout(right)
    layout.addWidget(right_widget, 2)

    dlg.exec()
