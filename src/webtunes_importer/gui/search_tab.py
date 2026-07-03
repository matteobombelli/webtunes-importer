"""Search tab: query the YouTube catalog and import individual tracks,
onthespot-style - a results table whose action cell turns into a live
progress readout."""

import threading
from collections.abc import Callable

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from webtunes_importer.core.queue_model import ImportItem, ItemStatus
from webtunes_importer.core.search import search_youtube
from webtunes_importer.gui.widgets import (
    ElidedLabel,
    RowActionWidget,
    ThumbnailLoader,
    format_duration,
)

THUMB_SIZE = 44
CONNECT_FIRST = "Connect to WebTunes in the Setup tab before importing."


class _SearchSignals(QObject):
    done = Signal(list)
    failed = Signal(str)


class SearchTab(QWidget):
    def __init__(self, enqueue: Callable[[ImportItem], None], parent=None):
        super().__init__(parent)
        self._enqueue = enqueue
        self._connected = False
        self._rows: dict[str, tuple[ImportItem, RowActionWidget]] = {}
        self._thumbs: dict[str, QLabel] = {}

        self._signals = _SearchSignals()
        self._signals.done.connect(self._fill_table)
        self._signals.failed.connect(self._search_failed)

        self._thumb_loader = ThumbnailLoader(self)
        self._thumb_loader.loaded.connect(self._set_thumbnail)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 20, 24, 16)
        outer.setSpacing(14)

        row = QHBoxLayout()
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search YouTube for a track…")
        self.search_edit.returnPressed.connect(self._search)
        self.search_btn = QPushButton("Search")
        self.search_btn.setProperty("variant", "primary")
        self.search_btn.clicked.connect(self._search)
        row.addWidget(self.search_edit, 1)
        row.addWidget(self.search_btn)
        outer.addLayout(row)

        self.status_label = QLabel()
        self.status_label.setProperty("role", "muted")
        self.status_label.hide()
        outer.addWidget(self.status_label)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Track", "Channel", "Duration", ""])
        self.table.verticalHeader().hide()
        self.table.setShowGrid(False)
        self.table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        header = self.table.horizontalHeader()
        header.setDefaultAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(1, 170)
        self.table.setColumnWidth(2, 80)
        self.table.setColumnWidth(3, 170)
        self.table.verticalHeader().setDefaultSectionSize(THUMB_SIZE + 12)
        outer.addWidget(self.table, 1)

    # ----- wiring from MainWindow -----

    def set_connected(self, connected: bool) -> None:
        self._connected = connected
        for _item, widget in self._rows.values():
            widget.import_btn.setEnabled(connected)
            widget.import_btn.setToolTip("" if connected else CONNECT_FIRST)

    def on_item_update(self, item_id: str, status: ItemStatus, percent: int) -> None:
        entry = self._rows.get(item_id)
        if entry:
            entry[1].set_state(status, percent)

    # ----- searching -----

    def _search(self) -> None:
        term = self.search_edit.text().strip()
        if not term:
            return
        self.search_btn.setEnabled(False)
        self.status_label.setText("Searching…")
        self.status_label.show()

        def work():
            try:
                self._signals.done.emit(search_youtube(term))
            except Exception as e:
                self._signals.failed.emit(str(e))

        threading.Thread(target=work, daemon=True).start()

    def _search_failed(self, message: str) -> None:
        self.search_btn.setEnabled(True)
        self.status_label.setText(f"Search failed: {message}")

    def _fill_table(self, items: list) -> None:
        self.search_btn.setEnabled(True)
        self.status_label.setText(
            f"{len(items)} results" if items else "No results.")
        self._rows.clear()
        self._thumbs.clear()
        self.table.setRowCount(len(items))

        for row, item in enumerate(items):
            track_cell = QWidget()
            cell_l = QHBoxLayout(track_cell)
            cell_l.setContentsMargins(8, 2, 8, 2)
            cell_l.setSpacing(10)
            thumb = QLabel()
            thumb.setFixedSize(THUMB_SIZE, THUMB_SIZE)
            thumb.setStyleSheet("background: #1d1d21; border-radius: 6px;")
            thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
            cell_l.addWidget(thumb)
            title = ElidedLabel(item.title)
            cell_l.addWidget(title, 1)
            self.table.setCellWidget(row, 0, track_cell)

            by = QTableWidgetItem(item.by)
            by.setToolTip(item.by)
            self.table.setItem(row, 1, by)
            self.table.setItem(row, 2, QTableWidgetItem(format_duration(item.duration)))

            actions = RowActionWidget()
            actions.import_btn.setEnabled(self._connected)
            actions.import_btn.setToolTip("" if self._connected else CONNECT_FIRST)
            actions.import_clicked.connect(lambda item=item: self._import_item(item))
            actions.retry_clicked.connect(lambda item=item: self._import_item(item))
            self.table.setCellWidget(row, 3, actions)

            self._rows[item.item_id] = (item, actions)
            self._thumbs[item.item_id] = thumb
            if item.thumbnail_url:
                self._thumb_loader.fetch(item.item_id, item.thumbnail_url)

    def _set_thumbnail(self, item_id: str, data: bytes) -> None:
        label = self._thumbs.get(item_id)
        if not label:
            return
        pixmap = QPixmap()
        if pixmap.loadFromData(data):
            side = min(pixmap.width(), pixmap.height())
            x = (pixmap.width() - side) // 2
            y = (pixmap.height() - side) // 2
            square = pixmap.copy(x, y, side, side).scaled(
                THUMB_SIZE, THUMB_SIZE,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation)
            label.setPixmap(square)

    # ----- importing -----

    def _import_item(self, item: ImportItem) -> None:
        if not self._connected:
            return
        entry = self._rows.get(item.item_id)
        if entry:
            item.status = ItemStatus.WAITING
            item.error = None
            entry[1].set_state(ItemStatus.WAITING, 0)
        self._enqueue(item)
