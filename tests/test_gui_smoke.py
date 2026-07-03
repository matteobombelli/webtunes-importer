"""Offscreen smoke test: the full window builds, themes, and tears down."""

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")


@pytest.fixture
def isolated_config(monkeypatch, tmp_path):
    import webtunes_importer.config as config

    monkeypatch.setattr(config, "config_path", lambda: tmp_path / "config.json")
    monkeypatch.setattr(config, "data_path", lambda: tmp_path / "data")


def test_main_window_builds(qtbot, isolated_config):
    from webtunes_importer.gui.main_window import MainWindow

    window = MainWindow()
    qtbot.addWidget(window)
    assert window.tabs.count() == 3
    assert [window.tabs.tabText(i) for i in range(3)] == ["Setup", "Links", "Search"]
    # disconnected: import paths disabled, Setup tab in front
    assert not window.links_tab.import_btn.isEnabled()
    assert window.tabs.currentWidget() is window.setup_tab
    window.worker.stop()


def test_qss_builds_and_fonts_load(qtbot):
    from PySide6.QtWidgets import QApplication

    from webtunes_importer.gui.theme import build_qss, load_fonts

    qss = build_qss()
    assert "{" in qss and "#4f46e5" in qss and "{{" not in qss
    load_fonts(QApplication.instance())  # must not raise


def test_row_action_widget_states(qtbot):
    from webtunes_importer.core.queue_model import ItemStatus
    from webtunes_importer.gui.widgets import RowActionWidget

    w = RowActionWidget()
    qtbot.addWidget(w)
    assert w.stack.currentIndex() == 0
    w.set_state(ItemStatus.WAITING, 0)
    assert w.stack.currentIndex() == 1
    w.set_state(ItemStatus.DOWNLOADING, 42)
    assert "42%" in w.status_label.text()
    w.set_state(ItemStatus.DONE, 100)
    assert w.stack.currentIndex() == 2
    assert not w.retry_btn.isVisible() or not w.retry_btn.isVisibleTo(w.stack)
    w.set_state(ItemStatus.FAILED, 0)
    assert w.result_label.text() == "Failed"


def test_format_duration():
    from webtunes_importer.gui.widgets import format_duration

    assert format_duration(None) == "–"
    assert format_duration(65) == "1:05"
    assert format_duration(3661) == "1:01:01"
