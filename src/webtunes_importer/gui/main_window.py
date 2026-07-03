"""Main window: the tab shell, plus the wiring between the config, the shared
import queue, the sequential worker, and the three tabs."""

from PySide6.QtWidgets import QLabel, QMainWindow, QTabWidget, QVBoxLayout, QWidget

from webtunes_importer.config import load_config
from webtunes_importer.constants import APP_NAME
from webtunes_importer.core.queue_model import ImportQueue
from webtunes_importer.core.webtunes import WebTunesClient
from webtunes_importer.gui.links_tab import LinksTab
from webtunes_importer.gui.search_tab import SearchTab
from webtunes_importer.gui.setup_tab import SetupTab
from webtunes_importer.gui.worker import ImportWorker, WorkerSignals


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.resize(880, 640)
        self.setMinimumSize(680, 520)

        self.config = load_config()
        self.queue = ImportQueue()
        self.signals = WorkerSignals()

        central = QWidget()
        layout = QVBoxLayout(central)
        layout.setContentsMargins(24, 18, 24, 0)
        layout.setSpacing(10)

        title = QLabel(APP_NAME)
        title.setProperty("role", "h1")
        layout.addWidget(title)

        self.tabs = QTabWidget()
        self.setup_tab = SetupTab(self.config)
        self.links_tab = LinksTab(self.queue.put)
        self.search_tab = SearchTab(self.queue.put)
        self.tabs.addTab(self.setup_tab, "Setup")
        self.tabs.addTab(self.links_tab, "Links")
        self.tabs.addTab(self.search_tab, "Search")
        layout.addWidget(self.tabs, 1)
        self.setCentralWidget(central)

        # worker signals -> tabs (queued delivery onto the GUI thread)
        self.signals.log.connect(self.links_tab.on_log)
        self.signals.job_progress.connect(self.links_tab.on_progress)
        self.signals.job_counts.connect(self.links_tab.on_counts)
        self.signals.job_finished.connect(self.links_tab.on_finished)
        self.signals.item_update.connect(self.search_tab.on_item_update)
        self.signals.auth_revoked.connect(self._on_auth_revoked)

        self.setup_tab.connection_changed.connect(self._on_connection_changed)
        self._apply_connection_state()

        self.worker = ImportWorker(
            self.queue, self.signals,
            get_settings=lambda: self.config.settings,
            get_client=self._make_client,
        )
        self.worker.start()

        if not self.config.connection:
            self.tabs.setCurrentWidget(self.setup_tab)

    def _make_client(self) -> WebTunesClient | None:
        conn = self.config.connection
        if not conn:
            return None
        return WebTunesClient(conn.server_url, conn.token)

    def _on_connection_changed(self, _connection) -> None:
        self._apply_connection_state()

    def _apply_connection_state(self) -> None:
        connected = self.config.connection is not None
        self.links_tab.set_connected(connected)
        self.search_tab.set_connected(connected)

    def _on_auth_revoked(self) -> None:
        self.setup_tab.show_revoked()
        self._apply_connection_state()
        self.tabs.setCurrentWidget(self.setup_tab)

    def closeEvent(self, event) -> None:  # noqa: N802 (Qt API)
        self.worker.stop()
        super().closeEvent(event)
