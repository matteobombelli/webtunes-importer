"""Small reusable widgets shared by the tabs."""

import requests
from PySide6.QtCore import QObject, QRunnable, Qt, QThreadPool, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from webtunes_importer.core.queue_model import ItemStatus


def set_role(label: QLabel, role: str) -> None:
    """Re-tag a label's style role and refresh its styling."""
    label.setProperty("role", role)
    label.style().unpolish(label)
    label.style().polish(label)


class Card(QFrame):
    """A WebTunes-style panel: surface-1, subtle border, rounded corners."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setProperty("card", True)
        self.body = QVBoxLayout(self)
        self.body.setContentsMargins(20, 18, 20, 18)
        self.body.setSpacing(10)


class WarningBanner(QFrame):
    """Amber notice box with an optional action button."""

    def __init__(self, text: str, action_label: str | None = None, parent=None):
        super().__init__(parent)
        self.setProperty("banner", "warning")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        self.label = QLabel(text)
        self.label.setWordWrap(True)
        layout.addWidget(self.label, 1)
        self.action = None
        if action_label:
            self.action = QPushButton(action_label)
            self.action.setProperty("variant", "ghost")
            layout.addWidget(self.action)


class RowActionWidget(QWidget):
    """The action cell of one Search-tab row: an Import button that becomes a
    progress readout, then a result label (with Retry on failure)."""

    import_clicked = Signal()
    retry_clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 2, 6, 2)
        self.stack = QStackedWidget()
        layout.addWidget(self.stack)

        # page 0: idle
        idle = QWidget()
        idle_l = QHBoxLayout(idle)
        idle_l.setContentsMargins(0, 0, 0, 0)
        self.import_btn = QPushButton("Import")
        self.import_btn.setProperty("variant", "primary")
        self.import_btn.clicked.connect(self.import_clicked)
        idle_l.addWidget(self.import_btn)
        self.stack.addWidget(idle)

        # page 1: in flight
        busy = QWidget()
        busy_l = QVBoxLayout(busy)
        busy_l.setContentsMargins(0, 2, 0, 2)
        busy_l.setSpacing(3)
        self.status_label = QLabel("Queued")
        self.status_label.setProperty("role", "subtle")
        self.bar = QProgressBar()
        self.bar.setFixedHeight(6)
        self.bar.setTextVisible(False)
        busy_l.addWidget(self.status_label)
        busy_l.addWidget(self.bar)
        self.stack.addWidget(busy)

        # page 2: finished
        done = QWidget()
        done_l = QHBoxLayout(done)
        done_l.setContentsMargins(0, 0, 0, 0)
        self.result_label = QLabel()
        self.retry_btn = QPushButton("Retry")
        self.retry_btn.setProperty("variant", "ghost")
        self.retry_btn.clicked.connect(self.retry_clicked)
        done_l.addWidget(self.result_label, 1)
        done_l.addWidget(self.retry_btn)
        self.stack.addWidget(done)

    def set_state(self, status: ItemStatus, percent: int) -> None:
        if status is ItemStatus.WAITING:
            self.stack.setCurrentIndex(1)
            self.status_label.setText("Queued")
            self.bar.setRange(0, 0)
        elif status is ItemStatus.DOWNLOADING:
            self.stack.setCurrentIndex(1)
            self.status_label.setText(f"Downloading {percent}%")
            self.bar.setRange(0, 100)
            self.bar.setValue(percent)
        elif status is ItemStatus.UPLOADING:
            self.stack.setCurrentIndex(1)
            self.status_label.setText("Uploading…")
            self.bar.setRange(0, 0)
        elif status is ItemStatus.DONE:
            self._finish("Imported ✓", "success", retry=False)
        elif status is ItemStatus.DUPLICATE:
            self._finish("Already in WebTunes", "muted", retry=False)
        elif status is ItemStatus.FAILED:
            self._finish("Failed", "error", retry=True)
        elif status is ItemStatus.CANCELLED:
            self.stack.setCurrentIndex(0)

    def _finish(self, text: str, role: str, retry: bool) -> None:
        self.stack.setCurrentIndex(2)
        self.result_label.setText(text)
        set_role(self.result_label, role)
        self.retry_btn.setVisible(retry)


class _ThumbSignal(QObject):
    loaded = Signal(str, bytes)  # item_id, image bytes


class _ThumbTask(QRunnable):
    def __init__(self, item_id: str, url: str, signal: _ThumbSignal):
        super().__init__()
        self.item_id = item_id
        self.url = url
        self.signal = signal

    def run(self) -> None:
        try:
            resp = requests.get(self.url, timeout=15)
            resp.raise_for_status()
            self.signal.loaded.emit(self.item_id, resp.content)
        except Exception:
            pass  # a missing thumbnail is cosmetic


class ThumbnailLoader(QObject):
    """Fetches thumbnails off the GUI thread; QPixmap construction happens in
    the receiver's slot (pixmaps must only be built on the GUI thread)."""

    loaded = Signal(str, bytes)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._signal = _ThumbSignal()
        self._signal.loaded.connect(self.loaded)
        self._pool = QThreadPool(self)
        self._pool.setMaxThreadCount(4)

    def fetch(self, item_id: str, url: str) -> None:
        self._pool.start(_ThumbTask(item_id, url, self._signal))


def format_duration(seconds: float | None) -> str:
    if not seconds:
        return "–"
    seconds = int(seconds)
    if seconds >= 3600:
        return f"{seconds // 3600}:{seconds % 3600 // 60:02d}:{seconds % 60:02d}"
    return f"{seconds // 60}:{seconds % 60:02d}"


class ElidedLabel(QLabel):
    """Label that elides its text instead of stretching the layout."""

    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self._full = text
        self.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)

    def setText(self, text: str) -> None:  # noqa: N802 (Qt API)
        self._full = text
        super().setText(text)
        self.setToolTip(text)

    def paintEvent(self, event) -> None:  # noqa: N802 (Qt API)
        metrics = self.fontMetrics()
        elided = metrics.elidedText(self._full, Qt.TextElideMode.ElideRight, self.width())
        if elided != self.text():
            super().setText(elided)
        super().paintEvent(event)
