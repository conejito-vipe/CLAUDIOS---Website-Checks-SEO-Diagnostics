"""Ergänzende Stilregeln, die nach theme.STYLE gelten (spätere Regeln gleicher Genauigkeit gewinnen): bessere Lesbarkeit,
größere Überschriften, Chip (15 px hoch), Fensterknöpfe (Schließen rot, Minimieren orange beim Überfahren), Sprachflaggen und
Hilfe-Knopf (orange beim Überfahren, aktive Sprache orange umrandet), Autor-Link, roter Deinstallieren-Knopf und der Stil des
Splash für Dialoge."""
from __future__ import annotations

from .theme import BG, BG_DEEP, INK, MUTED

EXTRA = """
QWidget { font-size: 14px; }
QLabel#muted { color: %MUTED%; }
QLabel#subtitle { color: %MUTED%; font-size: 14px; }
QLabel#infohead { font-weight: 700; font-size: 14px; color: %INK%; }
QLabel#pill { font-size: 11px; padding: 0px 8px; border-radius: 6px; min-height: 15px; max-height: 15px; }
QLabel#logofallback { font-size: 38px; }
QLabel#h1 { font-size: 22px; font-weight: 700; color: %INK%; }
QLabel#h2 { font-size: 15px; font-weight: 600; color: %INK%; }
QPushButton#winbtn { padding: 0px; border-radius: 6px; }
QPushButton#winbtn[role="close"]:hover { background: #C62828; color: white; border-radius: 6px; }
QPushButton#winbtn[role="max"]:hover { background: #EE6A12; color: white; border-radius: 6px; }
QFrame#card[maximized="true"] { border-radius: 0px; border: none; }
QPushButton#infobtn { border: none; background: transparent; padding: 2px; border-radius: 8px; }
QPushButton#infobtn:hover { background: rgba(238, 106, 18, 60); }
QPushButton#winbtn[role="min"]:hover { background: #EE6A12; color: white; border-radius: 6px; }
QPushButton#langbtn { border: 1px solid transparent; border-radius: 6px; }
QPushButton#langbtn:hover { color: #EE6A12; background: rgba(238, 106, 18, 40); border: 1px solid rgba(238, 106, 18, 120); }
QPushButton#langbtn:checked { color: #EE6A12; background: rgba(238, 106, 18, 70); border: 1px solid #EE6A12; }
QPushButton#langbtn:disabled { color: #A9B4C0; background: transparent; }
QPushButton#langbtn:checked:disabled { background: rgba(238, 106, 18, 40); border: 1px solid rgba(238, 106, 18, 120); }
QPushButton#authorlink { background: transparent; border: none; padding: 0px 2px; color: #EE6A12; font-weight: 700; }
QPushButton#authorlink:hover { color: #FF8A3D; }
QPushButton#danger { background: #C62828; color: white; border: none; font-weight: 600; padding: 8px 14px; }
QPushButton#danger:hover { background: #A81E1E; }
QPushButton#danger:disabled { background: #4A2A2A; color: #9AA7B5; }
QListWidget#toc { background: transparent; border: none; border-right: 1px solid #3A485B; border-radius: 0px;
    padding: 0px 8px 0px 0px; outline: none; }
QListWidget#toc::item { padding: 7px 10px; border-radius: 6px; color: %MUTED%; }
QListWidget#toc::item:hover { background: #323F50; color: %INK%; }
QListWidget#toc::item:selected { background: #3B2D20; color: #FF8A3D; }
QPushButton#railbtn { background: transparent; border: none; border-radius: 10px; padding: 0px; }
QPushButton#railbtn:hover { background: #3A1F1F; }
QDialog, QMessageBox { background: %BG%; }
QMessageBox QLabel { color: %INK%; }
QCheckBox { spacing: 8px; }
QScrollArea, QScrollArea > QWidget > QWidget { background: transparent; }
""".replace("%BG%", BG).replace("%INK%", INK).replace("%MUTED%", MUTED)


# Haken im Auswahlfeld: ein orangefarbener Haken auf dunklem Grund (Bilddatei, die beim Start erzeugt wird)
CHECK_CSS = """
QCheckBox::indicator:checked, QAbstractItemView::indicator:checked { image: url(%IMG%); background: %BG_DEEP%;
    border: 1.5px solid #EE6A12; }
QCheckBox::indicator:checked:disabled { border-color: #8A6A4A; }
QCheckBox::indicator:unchecked:hover { border-color: #EE6A12; background: rgba(238, 106, 18, 40); }
QPushButton#expandbtn { font-weight: 700; border: 1.5px solid #EE6A12; color: #FFB27A; padding: 7px 14px; }
QPushButton#expandbtn:hover { background: rgba(238, 106, 18, 60); color: #FFFFFF; }
QLabel#cardname { color: %MUTED%; font-size: 13px; }
"""


def check_image() -> str | None:
    """Zeichnet den Haken (orange) in eine PNG-Datei im temporären Ordner und gibt den Pfad mit / zurück."""
    import tempfile
    from pathlib import Path

    from PySide6.QtCore import QPointF, Qt
    from PySide6.QtGui import QColor, QPainter, QPen, QPixmap, QPolygonF

    try:
        folder = Path(tempfile.gettempdir()) / "claudios-ui"
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / "check-orange.png"
        pix = QPixmap(32, 32)
        pix.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pix)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(QColor("#FF8A3D"), 4.2)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.drawPolyline(QPolygonF([QPointF(7, 17), QPointF(13.5, 23.5), QPointF(25, 9)]))
        painter.end()
        return path.as_posix() if pix.save(str(path), "PNG") else None
    except Exception:  # noqa: BLE001 – ohne Bild bleibt das Feld einfach orange gefüllt
        return None


def full_style() -> str:
    from .theme import STYLE

    image = check_image()
    extra = CHECK_CSS.replace("%MUTED%", MUTED).replace("%BG_DEEP%", BG_DEEP)
    extra = extra.replace("image: url(%IMG%);", f"image: url({image});" if image else "")
    return STYLE + EXTRA + extra
