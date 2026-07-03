"""WebTunes' visual language, translated to Qt.

Tokens mirror WebTunes' globals.css design tokens verbatim (dark-only:
near-black surfaces stepping up to raised controls, indigo as the single
accent). Space Grotesk for headings, Geist for body text - both bundled.
"""

from pathlib import Path

from PySide6.QtGui import QColor, QFontDatabase, QPalette
from PySide6.QtWidgets import QApplication

TOKENS = {
    "surface0": "#09090b",  # page background
    "surface1": "#141417",  # panels / cards
    "surface2": "#1d1d21",  # inputs, hovers
    "surface3": "#2a2a30",  # raised controls, secondary buttons
    "border": "#34343c",
    "borderSubtle": "#232328",
    "fg": "#fafafa",
    "fgMuted": "#a1a1aa",
    "fgSubtle": "#71717a",
    "accent": "#4f46e5",
    "accentHover": "#6366f1",
    "accentBright": "#818cf8",
    "accentFg": "#ffffff",
    "danger": "#ef4444",
    "warning": "#f59e0b",
    "success": "#4ade80",
}

_FONTS_DIR = Path(__file__).resolve().parent.parent / "resources" / "fonts"

BODY_FAMILY = "Geist"
DISPLAY_FAMILY = "Space Grotesk"


def load_fonts(app: QApplication) -> None:
    """Register the bundled fonts; fall back silently to system sans."""
    for ttf in sorted(_FONTS_DIR.glob("*.ttf")):
        QFontDatabase.addApplicationFont(str(ttf))
    families = set(QFontDatabase.families())
    if BODY_FAMILY in families:
        font = app.font()
        font.setFamily(BODY_FAMILY)
        font.setPointSizeF(10.5)
        app.setFont(font)


def apply_palette(app: QApplication) -> None:
    """Dark QPalette so native popups (combo lists, menus, tooltips) match."""
    p = QPalette()
    p.setColor(QPalette.ColorRole.Window, QColor(TOKENS["surface0"]))
    p.setColor(QPalette.ColorRole.WindowText, QColor(TOKENS["fg"]))
    p.setColor(QPalette.ColorRole.Base, QColor(TOKENS["surface2"]))
    p.setColor(QPalette.ColorRole.AlternateBase, QColor(TOKENS["surface1"]))
    p.setColor(QPalette.ColorRole.Text, QColor(TOKENS["fg"]))
    p.setColor(QPalette.ColorRole.PlaceholderText, QColor(TOKENS["fgSubtle"]))
    p.setColor(QPalette.ColorRole.Button, QColor(TOKENS["surface3"]))
    p.setColor(QPalette.ColorRole.ButtonText, QColor(TOKENS["fg"]))
    p.setColor(QPalette.ColorRole.Highlight, QColor(TOKENS["accent"]))
    p.setColor(QPalette.ColorRole.HighlightedText, QColor(TOKENS["accentFg"]))
    p.setColor(QPalette.ColorRole.ToolTipBase, QColor(TOKENS["surface2"]))
    p.setColor(QPalette.ColorRole.ToolTipText, QColor(TOKENS["fg"]))
    p.setColor(QPalette.ColorRole.Link, QColor(TOKENS["accentBright"]))
    app.setPalette(p)


def build_qss() -> str:
    return """
QMainWindow, QDialog {{ background: {surface0}; }}
QWidget {{ color: {fg}; }}
QLabel {{ background: transparent; }}

QLabel[role="h1"] {{
    font-family: '{display}';
    font-size: 20px;
    font-weight: 600;
}}
QLabel[role="h2"] {{
    font-family: '{display}';
    font-size: 15px;
    font-weight: 600;
}}
QLabel[role="muted"] {{ color: {fgMuted}; }}
QLabel[role="subtle"] {{ color: {fgSubtle}; font-size: 12px; }}
QLabel[role="error"] {{ color: {danger}; }}
QLabel[role="success"] {{ color: {success}; }}

/* Tabs: transparent bar, indigo underline on the active tab */
QTabWidget::pane {{ border: none; background: {surface0}; }}
QTabBar {{ background: transparent; }}
QTabBar::tab {{
    background: transparent;
    color: {fgMuted};
    padding: 9px 18px;
    margin-right: 4px;
    border: none;
    border-bottom: 2px solid transparent;
    font-family: '{display}';
    font-size: 13px;
    font-weight: 600;
}}
QTabBar::tab:hover {{ color: {fg}; }}
QTabBar::tab:selected {{ color: {fg}; border-bottom: 2px solid {accentBright}; }}

/* Cards */
QFrame[card="true"] {{
    background: {surface1};
    border: 1px solid {borderSubtle};
    border-radius: 10px;
}}
QFrame[card="true"] QLabel {{ border: none; }}

/* Notice/warning banners */
QFrame[banner="warning"] {{
    background: rgba(245, 158, 11, 0.08);
    border: 1px solid rgba(245, 158, 11, 0.35);
    border-radius: 8px;
}}
QFrame[banner="warning"] QLabel {{ color: {warning}; border: none; }}

/* Inputs */
QLineEdit, QPlainTextEdit, QListWidget {{
    background: {surface2};
    border: 1px solid {border};
    border-radius: 8px;
    padding: 7px 10px;
    selection-background-color: {accent};
    selection-color: {accentFg};
}}
QLineEdit:focus, QPlainTextEdit:focus {{ border: 1px solid {accent}; }}
QLineEdit:disabled {{ color: {fgSubtle}; background: {surface1}; }}

QComboBox {{
    background: {surface2};
    border: 1px solid {border};
    border-radius: 8px;
    padding: 6px 10px;
}}
QComboBox:focus {{ border: 1px solid {accent}; }}
QComboBox::drop-down {{ border: none; width: 24px; }}
QComboBox QAbstractItemView {{
    background: {surface2};
    border: 1px solid {border};
    border-radius: 8px;
    selection-background-color: {surface3};
    selection-color: {fg};
    outline: none;
}}

/* Buttons: secondary by default, variant="primary"/"ghost" opt-in */
QPushButton {{
    background: {surface3};
    color: {fg};
    border: none;
    border-radius: 8px;
    padding: 8px 16px;
    font-weight: 600;
}}
QPushButton:hover {{ background: {border}; }}
QPushButton:disabled {{ color: {fgSubtle}; background: {surface2}; }}
QPushButton[variant="primary"] {{ background: {accent}; color: {accentFg}; }}
QPushButton[variant="primary"]:hover {{ background: {accentHover}; }}
QPushButton[variant="primary"]:disabled {{ background: {surface3}; color: {fgSubtle}; }}
QPushButton[variant="ghost"] {{
    background: transparent;
    color: {fgMuted};
    border: 1px solid {border};
}}
QPushButton[variant="ghost"]:hover {{ color: {fg}; border-color: {fgMuted}; }}

QToolButton {{
    background: transparent;
    color: {fgMuted};
    border: none;
    padding: 4px;
    font-weight: 600;
}}
QToolButton:hover {{ color: {fg}; }}

/* Radio buttons */
QRadioButton {{ spacing: 7px; color: {fg}; background: transparent; }}
QRadioButton::indicator {{
    width: 16px; height: 16px;
    border-radius: 9px;
    border: 1px solid {fgSubtle};
    background: {surface2};
}}
QRadioButton::indicator:hover {{ border-color: {fgMuted}; }}
QRadioButton::indicator:checked {{
    width: 8px; height: 8px;
    border: 5px solid {accent};
    border-radius: 9px;
    background: {accentFg};
}}

/* Slider */
QSlider::groove:horizontal {{
    height: 4px;
    background: {surface3};
    border-radius: 2px;
}}
QSlider::sub-page:horizontal {{ background: {accentHover}; border-radius: 2px; }}
QSlider::handle:horizontal {{
    width: 16px; height: 16px;
    margin: -6px 0;
    border-radius: 8px;
    background: {fg};
}}
QSlider::handle:horizontal:hover {{ background: {accentBright}; }}

/* Progress bars */
QProgressBar {{
    background: {surface2};
    border: none;
    border-radius: 5px;
    height: 10px;
    text-align: center;
    color: transparent;
}}
QProgressBar::chunk {{ background: {accent}; border-radius: 5px; }}

/* Table (Search results) */
QTableWidget {{
    background: {surface1};
    border: 1px solid {borderSubtle};
    border-radius: 10px;
    gridline-color: transparent;
    alternate-background-color: {surface1};
}}
QTableWidget::item {{ padding: 4px; border: none; }}
QTableWidget::item:hover {{ background: {surface2}; }}
QTableWidget::item:selected {{ background: {surface2}; color: {fg}; }}
QHeaderView::section {{
    background: {surface1};
    color: {fgSubtle};
    border: none;
    border-bottom: 1px solid {borderSubtle};
    padding: 8px;
    font-weight: 600;
}}
QTableCornerButton::section {{ background: {surface1}; border: none; }}

/* Scrollbars: thin and dark, like the web app */
QScrollBar:vertical {{ background: transparent; width: 8px; margin: 0; }}
QScrollBar::handle:vertical {{ background: {surface3}; border-radius: 4px; min-height: 24px; }}
QScrollBar::handle:vertical:hover {{ background: {border}; }}
QScrollBar:horizontal {{ background: transparent; height: 8px; margin: 0; }}
QScrollBar::handle:horizontal {{ background: {surface3}; border-radius: 4px; min-width: 24px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; width: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}

QToolTip {{
    background: {surface2};
    color: {fg};
    border: 1px solid {border};
    padding: 5px 8px;
}}
""".format(display=DISPLAY_FAMILY, **TOKENS)
