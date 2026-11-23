"""Ergänzende Stilregeln, die nach theme.STYLE gelten (spätere Regeln gleicher Genauigkeit gewinnen): bessere Lesbarkeit,
größere Überschriften, Chip (14 px hoch), Fensterknöpfe (Schließen rot, Minimieren orange beim Überfahren), Autor-Link,
roter Deinstallieren-Knopf und der Stil des Splash für Dialoge."""
from __future__ import annotations

from .theme import BG, INK

EXTRA = """
QWidget { font-size: 14px; }
QLabel#muted { color: #3F4E59; }
QLabel#pill { font-size: 11px; padding: 0px 8px; border-radius: 6px; min-height: 15px; max-height: 15px; }
QLabel#logofallback { font-size: 38px; }
QLabel#h1 { font-size: 22px; font-weight: 700; color: %INK%; }
QLabel#h2 { font-size: 15px; font-weight: 600; color: %INK%; }
QPushButton#winbtn[role="close"]:hover { background: #C62828; color: white; border-radius: 6px; }
QPushButton#winbtn[role="min"]:hover { background: #EE6A12; color: white; border-radius: 6px; }
QPushButton#authorlink { background: transparent; border: none; padding: 0px 2px; color: #EE6A12; font-weight: 700; }
QPushButton#authorlink:hover { color: #C4540A; }
QPushButton#danger { background: #C62828; color: white; border: none; font-weight: 600; padding: 8px 14px; }
QPushButton#danger:hover { background: #A81E1E; }
QPushButton#danger:disabled { background: #E3A5A5; color: white; }
QDialog, QMessageBox { background: %BG%; }
QMessageBox QLabel { color: %INK%; }
QCheckBox { spacing: 8px; }
QScrollArea, QScrollArea > QWidget > QWidget { background: transparent; }
""".replace("%BG%", BG).replace("%INK%", INK)
