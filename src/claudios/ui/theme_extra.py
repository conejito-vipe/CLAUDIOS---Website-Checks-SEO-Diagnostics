"""Ergänzende Stilregeln, die nach theme.STYLE gelten (spätere Regeln gleicher Genauigkeit gewinnen): bessere Lesbarkeit,
größere Überschriften, Chip (15 px hoch), Fensterknöpfe (Schließen rot, Minimieren orange beim Überfahren), Sprachflaggen und
Hilfe-Knopf (orange beim Überfahren, aktive Sprache orange umrandet), Autor-Link, roter Deinstallieren-Knopf und der Stil des
Splash für Dialoge."""
from __future__ import annotations

from .theme import BG, INK, MUTED

EXTRA = """
QWidget { font-size: 14px; }
QLabel#muted { color: %MUTED%; }
QLabel#subtitle { color: %MUTED%; font-size: 14px; }
QLabel#infohead { font-weight: 700; font-size: 14px; color: %INK%; }
QLabel#pill { font-size: 11px; padding: 0px 8px; border-radius: 6px; min-height: 15px; max-height: 15px; }
QLabel#logofallback { font-size: 38px; }
QLabel#h1 { font-size: 22px; font-weight: 700; color: %INK%; }
QLabel#h2 { font-size: 15px; font-weight: 600; color: %INK%; }
QPushButton#winbtn[role="close"]:hover { background: #C62828; color: white; border-radius: 6px; }
QPushButton#winbtn[role="min"]:hover { background: #EE6A12; color: white; border-radius: 6px; }
QPushButton#langbtn { border: 1px solid transparent; border-radius: 6px; }
QPushButton#langbtn:hover { color: #EE6A12; background: rgba(238, 106, 18, 40); border: 1px solid rgba(238, 106, 18, 120); }
QPushButton#langbtn:checked { color: #EE6A12; background: rgba(238, 106, 18, 70); border: 1px solid #EE6A12; }
QPushButton#langbtn:disabled { color: #9AA7B1; background: transparent; }
QPushButton#langbtn:checked:disabled { background: rgba(238, 106, 18, 40); border: 1px solid rgba(238, 106, 18, 120); }
QPushButton#authorlink { background: transparent; border: none; padding: 0px 2px; color: #EE6A12; font-weight: 700; }
QPushButton#authorlink:hover { color: #FF8A3D; }
QPushButton#danger { background: #C62828; color: white; border: none; font-weight: 600; padding: 8px 14px; }
QPushButton#danger:hover { background: #A81E1E; }
QPushButton#danger:disabled { background: #4A2A2A; color: #9AA7B5; }
QPushButton#railbtn { background: transparent; border: none; border-radius: 10px; padding: 0px; }
QPushButton#railbtn:hover { background: #3A1F1F; }
QDialog, QMessageBox { background: %BG%; }
QMessageBox QLabel { color: %INK%; }
QCheckBox { spacing: 8px; }
QScrollArea, QScrollArea > QWidget > QWidget { background: transparent; }
""".replace("%BG%", BG).replace("%INK%", INK).replace("%MUTED%", MUTED)
