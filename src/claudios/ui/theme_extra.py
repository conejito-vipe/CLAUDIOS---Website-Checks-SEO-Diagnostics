"""Ergänzende Stilregeln, die nach theme.STYLE gelten (spätere Regeln gleicher Genauigkeit gewinnen): bessere Lesbarkeit,
größere Überschriften, flacher Chip (8 px hoch), roter Deinstallieren-Knopf und der Stil des Splash für Dialoge."""
from __future__ import annotations

from .theme import BG, INK

EXTRA = """
QWidget { font-size: 14px; }
QLabel#muted { color: #3F4E59; }
QLabel#pill { font-size: 9px; padding: 0px 8px; border-radius: 5px; min-height: 12px; max-height: 12px; }
QLabel#logofallback { font-size: 38px; }
QLabel#h1 { font-size: 22px; font-weight: 700; color: %INK%; }
QLabel#h2 { font-size: 15px; font-weight: 600; color: %INK%; }
QPushButton#danger { background: #C62828; color: white; border: none; font-weight: 600; padding: 8px 14px; }
QPushButton#danger:hover { background: #A81E1E; }
QPushButton#danger:disabled { background: #E3A5A5; color: white; }
QDialog, QMessageBox { background: %BG%; }
QMessageBox QLabel { color: %INK%; }
QCheckBox { spacing: 8px; }
QScrollArea, QScrollArea > QWidget > QWidget { background: transparent; }
""".replace("%BG%", BG).replace("%INK%", INK)
