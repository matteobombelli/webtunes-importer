"""Setup tab: WebTunes pairing (mirroring the browser extension's popup) and
the import settings."""

import threading
from urllib.parse import urlparse

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QRadioButton,
    QSlider,
    QStackedWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from webtunes_importer.config import AppConfig, Connection, save_config
from webtunes_importer.constants import DEFAULT_SERVER_URL, QUALITY_CHOICES
from webtunes_importer.core import runtime_deps
from webtunes_importer.core.webtunes import (
    AuthRevokedError,
    PairError,
    WebTunesClient,
    normalize_server_url,
)
from webtunes_importer.gui.widgets import Card, WarningBanner

PAIR_HINT = (
    "In WebTunes, open <b>Settings → YouTube importer</b>, generate a pairing "
    "code, and enter it here."
)
REVOKED_NOTICE = "This connection was revoked in WebTunes. Pair again with a new code."
POLICY_WARNING = (
    "Importing may be unreliable due to changes in YouTube's policies. "
    "If importing is currently not working as intended, please notify me at "
    "matteo.bombelli@gmail.com"
)


class _AsyncSignals(QObject):
    pair_ok = Signal(str, object)  # token, userName
    pair_failed = Signal(str)
    verify_ok = Signal(object)  # userName
    verify_revoked = Signal()
    deno_progress = Signal(int)
    deno_done = Signal(object)  # None on success, error message on failure


class SetupTab(QWidget):
    connection_changed = Signal(object)  # Connection | None

    def __init__(self, config: AppConfig, parent=None):
        super().__init__(parent)
        self.config = config
        self._async = _AsyncSignals()
        self._async.pair_ok.connect(self._on_pair_ok)
        self._async.pair_failed.connect(self._on_pair_failed)
        self._async.verify_ok.connect(self._on_verify_ok)
        self._async.verify_revoked.connect(self._on_verify_revoked)
        self._async.deno_progress.connect(self._on_deno_progress)
        self._async.deno_done.connect(self._on_deno_done)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 20, 24, 16)
        outer.setSpacing(14)

        outer.addWidget(self._build_connection_card())
        outer.addWidget(self._build_settings_card())
        outer.addStretch(1)
        self._build_footer(outer)

        self._render_connection()
        if self.config.connection:
            self._verify_async()

    # ----- connection card -----

    def _build_connection_card(self) -> Card:
        card = Card()
        title = QLabel("WebTunes connection")
        title.setProperty("role", "h2")
        card.body.addWidget(title)

        self.conn_stack = QStackedWidget()
        card.body.addWidget(self.conn_stack)

        # page 0: disconnected
        disc = QWidget()
        dl = QVBoxLayout(disc)
        dl.setContentsMargins(0, 0, 0, 0)
        dl.setSpacing(8)

        hint = QLabel(PAIR_HINT)
        hint.setWordWrap(True)
        hint.setProperty("role", "muted")
        dl.addWidget(hint)

        self.notice = WarningBanner("")
        self.notice.hide()
        dl.addWidget(self.notice)

        row = QHBoxLayout()
        self.code_edit = QLineEdit()
        self.code_edit.setPlaceholderText("Pairing code")
        self.code_edit.returnPressed.connect(self._pair)
        self.connect_btn = QPushButton("Connect")
        self.connect_btn.setProperty("variant", "primary")
        self.connect_btn.clicked.connect(self._pair)
        row.addWidget(self.code_edit, 1)
        row.addWidget(self.connect_btn)
        dl.addLayout(row)

        self.server_toggle = QToolButton()
        self.server_toggle.setText("WebTunes server")
        self.server_toggle.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.server_toggle.setArrowType(Qt.ArrowType.RightArrow)
        self.server_toggle.setCheckable(True)
        self.server_toggle.toggled.connect(self._toggle_server_field)
        dl.addWidget(self.server_toggle)

        self.server_edit = QLineEdit(self.config.settings.server_url)
        self.server_edit.setPlaceholderText(DEFAULT_SERVER_URL)
        self.server_edit.hide()
        self.server_edit.editingFinished.connect(self._save_server_url)
        dl.addWidget(self.server_edit)

        self.pair_error = QLabel()
        self.pair_error.setProperty("role", "error")
        self.pair_error.setWordWrap(True)
        self.pair_error.hide()
        dl.addWidget(self.pair_error)
        self.conn_stack.addWidget(disc)

        # page 1: connected
        conn = QWidget()
        cl = QVBoxLayout(conn)
        cl.setContentsMargins(0, 0, 0, 0)
        cl.setSpacing(4)
        self.connected_label = QLabel()
        self.connected_label.setWordWrap(True)
        cl.addWidget(self.connected_label)
        self.server_host = QLabel()
        self.server_host.setProperty("role", "subtle")
        cl.addWidget(self.server_host)
        disconnect_btn = QPushButton("Disconnect")
        disconnect_btn.setProperty("variant", "ghost")
        disconnect_btn.clicked.connect(self._disconnect)
        brow = QHBoxLayout()
        brow.addWidget(disconnect_btn)
        brow.addStretch(1)
        cl.addSpacing(6)
        cl.addLayout(brow)
        self.conn_stack.addWidget(conn)

        return card

    def _toggle_server_field(self, open_: bool) -> None:
        self.server_toggle.setArrowType(
            Qt.ArrowType.DownArrow if open_ else Qt.ArrowType.RightArrow)
        self.server_edit.setVisible(open_)

    def _save_server_url(self) -> None:
        self.config.settings.server_url = normalize_server_url(self.server_edit.text())
        save_config(self.config)

    def _render_connection(self, notice: str | None = None) -> None:
        conn = self.config.connection
        if conn:
            name = conn.user_name or "your account"
            self.connected_label.setText(f"Connected to WebTunes as <b>{name}</b>")
            self.server_host.setText(urlparse(conn.server_url).netloc)
            self.conn_stack.setCurrentIndex(1)
        else:
            self.conn_stack.setCurrentIndex(0)
        if notice:
            self.notice.label.setText(notice)
            self.notice.show()
        else:
            self.notice.hide()

    def _pair(self) -> None:
        code = self.code_edit.text().strip()
        if not code:
            return
        self._save_server_url()
        self.pair_error.hide()
        self.connect_btn.setEnabled(False)
        self.connect_btn.setText("Connecting…")
        server_url = self.config.settings.server_url

        def work():
            try:
                client = WebTunesClient(server_url)
                token, user_name = client.pair(code)
                self._async.pair_ok.emit(token, user_name)
            except PairError as e:
                self._async.pair_failed.emit(str(e))
            except Exception:
                self._async.pair_failed.emit(
                    "Could not reach the WebTunes server. Check the URL and your connection.")

        threading.Thread(target=work, daemon=True).start()

    def _on_pair_ok(self, token: str, user_name) -> None:
        self.connect_btn.setEnabled(True)
        self.connect_btn.setText("Connect")
        self.code_edit.clear()
        self.config.connection = Connection(
            server_url=self.config.settings.server_url, token=token, user_name=user_name)
        save_config(self.config)
        self._render_connection()
        self.connection_changed.emit(self.config.connection)

    def _on_pair_failed(self, message: str) -> None:
        self.connect_btn.setEnabled(True)
        self.connect_btn.setText("Connect")
        self.pair_error.setText(message)
        self.pair_error.show()

    def _disconnect(self) -> None:
        conn = self.config.connection
        if conn:
            client = WebTunesClient(conn.server_url, conn.token)
            threading.Thread(target=client.disconnect, daemon=True).start()
        self.config.connection = None
        save_config(self.config)
        self._render_connection()
        self.connection_changed.emit(None)

    def _verify_async(self) -> None:
        conn = self.config.connection

        def work():
            try:
                client = WebTunesClient(conn.server_url, conn.token)
                self._async.verify_ok.emit(client.verify())
            except AuthRevokedError:
                self._async.verify_revoked.emit()
            except Exception:
                pass  # offline is not disconnected - keep the cached connection

        threading.Thread(target=work, daemon=True).start()

    def _on_verify_ok(self, user_name) -> None:
        if self.config.connection and user_name:
            self.config.connection.user_name = user_name
            save_config(self.config)
            self._render_connection()

    def _on_verify_revoked(self) -> None:
        self.show_revoked()
        self.connection_changed.emit(None)

    def show_revoked(self) -> None:
        """Drop the stored connection and surface the revocation notice."""
        self.config.connection = None
        save_config(self.config)
        self._render_connection(notice=REVOKED_NOTICE)

    # ----- settings card -----

    def _build_settings_card(self) -> Card:
        card = Card()
        title = QLabel("Import settings")
        title.setProperty("role", "h2")
        card.body.addWidget(title)

        version_row = QHBoxLayout()
        version_row.setSpacing(10)
        version_row.addWidget(QLabel("Version:"))
        self.version_radios = {}
        for label, value in (("No preference", "none"), ("Studio", "studio"), ("Live", "live")):
            rb = QRadioButton(label)
            rb.setChecked(self.config.settings.version_pref == value)
            rb.toggled.connect(
                lambda on, value=value: on and self._set_setting("version_pref", value))
            self.version_radios[value] = rb
            version_row.addWidget(rb)
        version_row.addStretch(1)
        card.body.addLayout(version_row)

        quality_row = QHBoxLayout()
        quality_row.setSpacing(10)
        quality_row.addWidget(QLabel("Quality:"))
        self.quality_combo = QComboBox()
        for label, code in QUALITY_CHOICES:
            self.quality_combo.addItem(label, code)
        idx = next((i for i, (_, code) in enumerate(QUALITY_CHOICES)
                    if code == self.config.settings.quality), 2)
        self.quality_combo.setCurrentIndex(idx)
        self.quality_combo.currentIndexChanged.connect(
            lambda i: self._set_setting("quality", self.quality_combo.itemData(i)))
        quality_row.addWidget(self.quality_combo)
        quality_row.addStretch(1)
        card.body.addLayout(quality_row)

        strict_row = QHBoxLayout()
        strict_row.setSpacing(10)
        strict_row.addWidget(QLabel("Match strictness:"))
        self.strict_slider = QSlider(Qt.Orientation.Horizontal)
        self.strict_slider.setRange(0, 100)
        self.strict_slider.setValue(round(self.config.settings.strictness * 100))
        self.strict_slider.setFixedWidth(180)
        self.strict_value = QLabel(f"{self.config.settings.strictness:.2f}")
        self.strict_slider.valueChanged.connect(self._on_strictness)
        hint = QLabel("(higher = pickier)")
        hint.setProperty("role", "subtle")
        strict_row.addWidget(self.strict_slider)
        strict_row.addWidget(self.strict_value)
        strict_row.addWidget(hint)
        strict_row.addStretch(1)
        card.body.addLayout(strict_row)

        return card

    def _set_setting(self, name: str, value) -> None:
        setattr(self.config.settings, name, value)
        save_config(self.config)

    def _on_strictness(self, raw: int) -> None:
        self.strict_value.setText(f"{raw / 100:.2f}")
        self._set_setting("strictness", raw / 100)

    # ----- footer -----

    def _build_footer(self, outer: QVBoxLayout) -> None:
        self.dep_banner = None
        warnings = runtime_deps.startup_report()
        if warnings:
            needs_deno = runtime_deps.find_deno() is None
            self.dep_banner = WarningBanner(
                " ".join(warnings), "Download deno" if needs_deno else None)
            if self.dep_banner.action:
                self.dep_banner.action.clicked.connect(self._fetch_deno)
            outer.addWidget(self.dep_banner)

        footer = QLabel(POLICY_WARNING)
        footer.setWordWrap(True)
        footer.setProperty("role", "subtle")
        outer.addWidget(footer)

    def _fetch_deno(self) -> None:
        banner = self.dep_banner
        banner.action.setEnabled(False)

        def work():
            try:
                runtime_deps.fetch_deno(self._async.deno_progress.emit)
                self._async.deno_done.emit(None)
            except Exception as e:
                self._async.deno_done.emit(str(e))

        threading.Thread(target=work, daemon=True).start()

    def _on_deno_progress(self, pct: int) -> None:
        self.dep_banner.action.setText(f"Downloading… {pct}%")

    def _on_deno_done(self, error) -> None:
        banner = self.dep_banner
        if error:
            banner.action.setEnabled(True)
            banner.action.setText("Download deno")
            banner.label.setText(f"deno download failed: {error}")
            return
        remaining = runtime_deps.startup_report()
        if remaining:
            banner.label.setText(" ".join(remaining))
            banner.action.hide()
        else:
            banner.hide()
