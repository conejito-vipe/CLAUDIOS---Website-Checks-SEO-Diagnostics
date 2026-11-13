"""Farben und Stil nach der Vorlage: hellgrau-blau, oranger Akzent."""
BG = "#E9EEF2"
ORANGE = "#EE6A12"
INK = "#1B2A33"
MUTED = "#6B7A86"
TRACK = "#DDE3E8"

_TEMPLATE = """
QFrame#card { background: %BG%; border-radius: 14px; }
QWidget { font-family: 'Segoe UI', sans-serif; font-size: 13px; color: %INK%; }
QLabel#pill { background: %ORANGE%; color: white; font-weight: 600; padding: 3px 12px; border-radius: 8px; }
QLabel#muted { color: %MUTED%; }
QLabel#logofallback { font-size: 54px; font-weight: 800; color: %ORANGE%; }
QPushButton { background: white; border: 1px solid #C9D2D9; border-radius: 8px; padding: 6px 14px; }
QPushButton:hover { border-color: %ORANGE%; }
QPushButton:disabled { color: #9AA7B1; background: #F3F6F8; }
QPushButton#primary { background: %ORANGE%; color: white; border: none; font-weight: 600; padding: 8px 18px; }
QPushButton#primary:disabled { background: #F2B48A; color: white; }
QPushButton#winbtn { border: none; background: transparent; font-size: 16px; padding: 4px 10px; }
QPushButton#winbtn:hover { background: #D5DCE2; border-radius: 6px; }
QPushButton#langbtn { border: none; background: transparent; padding: 3px 8px; font-weight: 600; color: %MUTED%; }
QPushButton#langbtn:checked { color: %ORANGE%; }
QProgressBar { background: %TRACK%; border: none; border-radius: 2px; max-height: 4px; min-height: 4px; }
QProgressBar::chunk { background: %ORANGE%; border-radius: 2px; }
QListWidget#nav { background: transparent; border: none; outline: none; }
QListWidget#nav::item { padding: 9px 14px; border-radius: 8px; }
QListWidget#nav::item:selected { background: %ORANGE%; color: white; }
QLineEdit, QComboBox, QPlainTextEdit, QTableWidget { background: white; border: 1px solid #C9D2D9;
    border-radius: 8px; padding: 6px; }
QHeaderView::section { background: #F3F6F8; border: none; padding: 6px; font-weight: 600; }
"""

STYLE = (_TEMPLATE.replace("%BG%", BG).replace("%ORANGE%", ORANGE).replace("%INK%", INK)
         .replace("%MUTED%", MUTED).replace("%TRACK%", TRACK))
