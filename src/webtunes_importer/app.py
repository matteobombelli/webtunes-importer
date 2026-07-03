"""Application entry point."""

import sys
from pathlib import Path

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from webtunes_importer import __version__
from webtunes_importer.constants import APP_NAME
from webtunes_importer.core.runtime_deps import inject_deno_path
from webtunes_importer.gui.theme import apply_palette, build_qss, load_fonts

_ICON = Path(__file__).resolve().parent / "resources" / "icons" / "app.svg"


def main() -> None:
    inject_deno_path()  # pick up a previously downloaded deno before yt-dlp runs

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(__version__)
    app.setStyle("Fusion")
    load_fonts(app)
    apply_palette(app)
    app.setStyleSheet(build_qss())
    app.setWindowIcon(QIcon(str(_ICON)))

    # imported here so QApplication exists before any widget module loads
    from webtunes_importer.gui.main_window import MainWindow

    window = MainWindow()
    window.show()
    sys.exit(app.exec())
