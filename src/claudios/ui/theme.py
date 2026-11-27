"""Farben und Stil (Entwurf B): dunkel, ein orangefarbener Akzent. Texte auf dem Akzent sind dunkel (Kontrast)."""
BG = "#1D2530"          # Fenster
BG_DEEP = "#151C25"     # Eingabefelder, Titelleiste, Codefenster
SURFACE = "#273140"     # Karten
SURFACE2 = "#323F50"    # Schaltflächen, Hover
LINE = "#3A485B"        # feine Rahmen
LINE2 = "#4B5C72"       # Rahmen von Eingaben und Schaltflächen
ORANGE = "#EE6A12"
ORANGE_HI = "#FF8A3D"
ON_ORANGE = "#1B1005"   # Text auf dem Akzent
ORANGE_SOFT = "#3B2D20"  # gewählter Eintrag der Navigation
INK = "#F3F6FA"
MUTED = "#C0CAD6"
DISABLED = "#8996A6"
TRACK = LINE

_TEMPLATE = """
QFrame#card { background: %BG%; border: 1px solid %LINE%; border-radius: 14px; }
QWidget { font-family: 'Segoe UI', '.AppleSystemUIFont', 'Helvetica Neue', sans-serif; font-size: 13px; color: %INK%; }
QToolTip { background: %SURFACE2%; color: %INK%; border: 1px solid %LINE2%; padding: 4px 8px; }
QLabel#pill { background: %ORANGE%; color: %ON_ORANGE%; font-weight: 700; padding: 3px 12px; border-radius: 8px; }
QLabel#muted { color: %MUTED%; }
QLabel#logofallback { font-size: 54px; font-weight: 800; color: %ORANGE%; }
QFrame#panel { background: %SURFACE%; border: 1px solid %LINE%; border-radius: 14px; }
QFrame#infoitem { background: transparent; border: none; border-left: 3px solid %ORANGE%; }
QPushButton { background: %SURFACE2%; border: 1px solid %LINE2%; border-radius: 8px; padding: 6px 14px; color: %INK%; }
QPushButton:hover { border-color: %ORANGE%; }
QPushButton:disabled { color: %DISABLED%; background: %SURFACE%; border-color: %LINE%; }
QPushButton#primary { background: %ORANGE%; color: %ON_ORANGE%; border: none; font-weight: 700; padding: 8px 18px; }
QPushButton#primary:hover { background: %ORANGE_HI%; }
QPushButton#primary:disabled { background: #5A4128; color: #C9AE92; }
QPushButton#winbtn { border: none; background: transparent; font-size: 16px; padding: 4px 10px; }
QPushButton#winbtn:hover { background: %LINE%; border-radius: 6px; }
QPushButton#langbtn { border: none; background: transparent; padding: 3px 8px; font-weight: 600; color: %MUTED%; }
QPushButton#langbtn:checked { color: %ORANGE_HI%; }
QProgressBar { background: %TRACK%; border: none; border-radius: 2px; max-height: 4px; min-height: 4px; }
QProgressBar::chunk { background: %ORANGE%; border-radius: 2px; }
QListWidget#nav { background: transparent; border: none; outline: none; }
QLineEdit, QComboBox, QPlainTextEdit, QTextBrowser, QTextEdit, QTableWidget, QTreeWidget, QListWidget {
    background: %BG_DEEP%; border: 1px solid %LINE2%; border-radius: 8px; padding: 6px; color: %INK%;
    selection-background-color: %ORANGE%; selection-color: %ON_ORANGE%; }
QLineEdit:focus, QComboBox:focus, QPlainTextEdit:focus { border-color: %ORANGE%; }
QLineEdit:disabled, QComboBox:disabled { color: %DISABLED%; background: %SURFACE%; }
QComboBox QAbstractItemView { background: %SURFACE2%; color: %INK%; border: 1px solid %LINE2%;
    selection-background-color: %ORANGE%; selection-color: %ON_ORANGE%; }
QHeaderView::section { background: %SURFACE2%; color: %INK%; border: none; padding: 6px; font-weight: 600; }
QTableWidget { gridline-color: %LINE%; }
QCheckBox::indicator { width: 16px; height: 16px; border: 1.5px solid %MUTED%; border-radius: 4px; background: %BG_DEEP%; }
QCheckBox::indicator:checked { background: %ORANGE%; border-color: %ORANGE%; }
QCheckBox::indicator:hover { border-color: %ORANGE%; }
QTabWidget::pane { border: 1px solid %LINE%; border-radius: 8px; top: -1px; }
QTabBar::tab { background: transparent; color: %MUTED%; padding: 8px 16px; border: none; border-bottom: 2px solid transparent; }
QTabBar::tab:selected { color: %INK%; border-bottom: 2px solid %ORANGE%; }
QTabBar::tab:hover { color: %INK%; }
QScrollBar:vertical { background: transparent; width: 10px; margin: 0; }
QScrollBar::handle:vertical { background: %LINE2%; border-radius: 5px; min-height: 30px; }
QScrollBar::handle:vertical:hover { background: %MUTED%; }
QScrollBar:horizontal { background: transparent; height: 10px; margin: 0; }
QScrollBar::handle:horizontal { background: %LINE2%; border-radius: 5px; min-width: 30px; }
QScrollBar::add-line, QScrollBar::sub-line { width: 0; height: 0; }
QScrollBar::add-page, QScrollBar::sub-page { background: transparent; }
"""

_VALUES = {
    "BG_DEEP": BG_DEEP, "SURFACE2": SURFACE2, "SURFACE": SURFACE, "LINE2": LINE2, "LINE": LINE, "BG": BG,
    "ORANGE_HI": ORANGE_HI, "ON_ORANGE": ON_ORANGE, "ORANGE": ORANGE, "INK": INK, "MUTED": MUTED,
    "DISABLED": DISABLED, "TRACK": TRACK,
}


def _fill(template: str) -> str:
    for name, value in _VALUES.items():  # längere Namen zuerst, damit %ORANGE% nicht %ORANGE_HI% zerlegt
        template = template.replace(f"%{name}%", value)
    return template


STYLE = _fill(_TEMPLATE)
