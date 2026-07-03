"""Links tab: paste a Spotify / Apple Music / YouTube link, import everything
behind it, watch progress, and review missed tracks."""

from collections.abc import Callable

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from webtunes_importer.core.jobs import JobResult, classify_url
from webtunes_importer.core.queue_model import LinkJob
from webtunes_importer.core.webtunes import AuthRevokedError
from webtunes_importer.gui.widgets import Card

CONNECT_FIRST = "Connect to WebTunes in the Setup tab before importing."


class LinksTab(QWidget):
    def __init__(self, enqueue: Callable[[LinkJob], None], parent=None):
        super().__init__(parent)
        self._enqueue = enqueue
        self._job: LinkJob | None = None
        self._connected = False

        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 20, 24, 16)
        outer.setSpacing(14)

        card = Card()
        row = QHBoxLayout()
        self.url_edit = QLineEdit()
        self.url_edit.setPlaceholderText(
            "Spotify, Apple Music, or YouTube link (playlist or song)")
        self.url_edit.returnPressed.connect(self._start)
        self.import_btn = QPushButton("Import")
        self.import_btn.setProperty("variant", "primary")
        self.import_btn.clicked.connect(self._start)
        row.addWidget(self.url_edit, 1)
        row.addWidget(self.import_btn)
        card.body.addLayout(row)

        self.error_label = QLabel()
        self.error_label.setProperty("role", "error")
        self.error_label.hide()
        card.body.addWidget(self.error_label)

        progress_row = QHBoxLayout()
        self.progress = QProgressBar()
        self.progress.setFixedHeight(10)
        self.progress.setTextVisible(False)
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setProperty("variant", "ghost")
        self.cancel_btn.clicked.connect(self._cancel)
        self.cancel_btn.hide()
        progress_row.addWidget(self.progress, 1)
        progress_row.addWidget(self.cancel_btn)
        card.body.addLayout(progress_row)

        self.counter_label = QLabel()
        self.counter_label.setProperty("role", "muted")
        self.counter_label.hide()
        card.body.addWidget(self.counter_label)
        outer.addWidget(card)

        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumBlockCount(2000)
        outer.addWidget(self.log_view, 1)

        self.missed_card = Card()
        missed_title = QLabel("Missed tracks")
        missed_title.setProperty("role", "h2")
        self.missed_card.body.addWidget(missed_title)
        self.missed_list = QListWidget()
        self.missed_list.setMaximumHeight(140)
        self.missed_card.body.addWidget(self.missed_list)
        self.missed_path_label = QLabel()
        self.missed_path_label.setProperty("role", "subtle")
        self.missed_path_label.setWordWrap(True)
        self.missed_path_label.linkActivated.connect(self._reveal_missed_file)
        self.missed_card.body.addWidget(self.missed_path_label)
        self.missed_card.hide()
        outer.addWidget(self.missed_card)

        self._missed_dir = None
        self._update_enabled()

    # ----- wiring from MainWindow -----

    def set_connected(self, connected: bool) -> None:
        self._connected = connected
        self._update_enabled()

    def on_log(self, message: str) -> None:
        self.log_view.appendPlainText(message)

    def on_progress(self, done: int, total: int) -> None:
        self.progress.setMaximum(max(total, 1))
        self.progress.setValue(done)
        self._progress_pos = (done, total)
        self._refresh_counter()

    def on_counts(self, imported: int, missed: int) -> None:
        self._counts = (imported, missed)
        self._refresh_counter()

    def on_finished(self, result) -> None:
        self._job = None
        self.cancel_btn.hide()
        self._update_enabled()
        if isinstance(result, AuthRevokedError):
            self.on_log(CONNECT_FIRST)
            return
        if isinstance(result, Exception):
            self.on_log(f"Error: {result}")
            return
        self._show_missed(result)

    # ----- internals -----

    def _update_enabled(self) -> None:
        running = self._job is not None
        self.import_btn.setEnabled(self._connected and not running)
        self.import_btn.setToolTip("" if self._connected else CONNECT_FIRST)

    def _refresh_counter(self) -> None:
        imported, missed = getattr(self, "_counts", (0, 0))
        done, total = getattr(self, "_progress_pos", (0, 0))
        self.counter_label.setText(
            f"{imported} imported · {missed} missed · {done} / {total}")
        self.counter_label.show()

    def _start(self) -> None:
        if self._job or not self._connected:
            return
        url = self.url_edit.text().strip()
        if not classify_url(url):
            self.error_label.setText("Enter a Spotify, Apple Music, or YouTube URL.")
            self.error_label.show()
            return
        self.error_label.hide()
        self.missed_card.hide()
        self.log_view.clear()
        self.progress.setValue(0)
        self._counts = (0, 0)
        self._progress_pos = (0, 0)

        self._job = LinkJob(url=url)
        self.cancel_btn.show()
        self._update_enabled()
        self._enqueue(self._job)

    def _cancel(self) -> None:
        if self._job:
            self._job.cancel.set()
            self.on_log("Cancelling after the current track…")
            self.cancel_btn.setEnabled(False)

    def _show_missed(self, result: JobResult) -> None:
        self.cancel_btn.setEnabled(True)
        if not result.missed:
            return
        self.missed_list.clear()
        self.missed_list.addItems(result.missed)
        if result.missed_file:
            self._missed_dir = str(result.missed_file.parent)
            self.missed_path_label.setText(
                f'Missed tracks were written to <a href="#reveal" '
                f'style="color:#818cf8">{result.missed_file}</a> '
                f"(overwritten on the next import)."
            )
        self.missed_card.show()

    def _reveal_missed_file(self, _link: str) -> None:
        if self._missed_dir:
            QDesktopServices.openUrl(QUrl.fromLocalFile(self._missed_dir))
