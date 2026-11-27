"""Symbole der Navigationsleiste (Entwurf B): schmale Icon-Leiste. Die Symbole sind Strichgrafiken (SVG-Pfade), die zur
Laufzeit in der Farbe des Zustands gezeichnet werden. Der Text der Einträge bleibt gesetzt (Tooltip, Screenreader, Tests);
der Delegate zeichnet nur das Symbol."""
from __future__ import annotations

from PySide6.QtCore import QRectF, QSize, Qt
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QStyle, QStyledItemDelegate

from .theme import MUTED, ORANGE, ORANGE_HI, ORANGE_SOFT

SIZE = 22
RAIL_ITEM = 48
RAIL_W = 116  # Breite der Leiste: Symbol mit Beschriftung darunter
RAIL_H = 52
PATHS = {
    "nav.scan": "M21 21l-4.3-4.3M11 18a7 7 0 1 0 0-14 7 7 0 0 0 0 14z",
    "nav.results": "M4 20V10M10 20V4M16 20v-7M22 20H2",
    "nav.findings": "M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01",
    "nav.services": "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18zM3 12h18M12 3c2.5 2.7 3.8 5.7 3.8 9S14.5 18.3 12 21c-2.5-2.7-3.8-5.7-3.8-9S9.5 5.7 12 3z",
    "nav.gsc": "M3 17l6-6 4 4 8-8M15 7h6v6",
    "nav.components": "M21 8l-9-5-9 5v8l9 5 9-5V8zM3 8l9 5 9-5M12 13v8",
    "nav.export": "M12 3v12M7 10l5 5 5-5M4 21h16",
    "nav.settings": "M4 6h10M18 6h2M4 12h4M12 12h8M4 18h12M14 4v4M8 10v4M16 16v4",
    "nav.help": "M4 5a2 2 0 0 1 2-2h13v16H6a2 2 0 0 0-2 2V5zM19 19v2H6",
    "nav.about": "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18zM12 11v5M12 8h.01",
    "nav.pro": "M12 3l2.8 5.7 6.2.9-4.5 4.4 1.1 6.2L12 17.2 6.4 20.2l1.1-6.2L3 9.6l6.2-.9L12 3z",
    "win.min": "M5 12h14",
    "win.max": "M6 6h12v12H6z",
    "win.restore": "M8 8h10v10H8zM6 15V6h9",
    "win.close": "M6 6l12 12M18 6L6 18",
    "expand": "M4 9V4h5M20 9V4h-5M4 15v5h5M20 15v5h-5",
    "uninstall": "M4 7h16M10 11v6M14 11v6M6 7l1 13h10l1-13M9 7V4h6v3",
}
FALLBACK = "M12 12h.01"


def _pixmap(path: str, color: str, size: int, ratio: float = 2.0) -> QPixmap:
    svg = (f'<svg viewBox="0 0 24 24" fill="none" stroke="{color}" '
           f'stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="{path}"/></svg>')
    pixmap = QPixmap(int(size * ratio), int(size * ratio))
    pixmap.setDevicePixelRatio(ratio)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    QSvgRenderer(svg.encode("utf-8")).render(painter, QRectF(0, 0, size, size))
    painter.end()
    return pixmap


def nav_icon(key: str, normal: str = MUTED, active: str = ORANGE_HI, size: int = SIZE) -> QIcon:
    path = PATHS.get(key, FALLBACK)
    icon = QIcon()
    icon.addPixmap(_pixmap(path, normal, size), QIcon.Mode.Normal)
    icon.addPixmap(_pixmap(path, active, size), QIcon.Mode.Selected)
    icon.addPixmap(_pixmap(path, active, size), QIcon.Mode.Active)
    return icon


class RailDelegate(QStyledItemDelegate):
    """Zeichnet je Eintrag nur ein Symbol auf einer abgerundeten Fläche (gewählt: Akzent, darüber: Hover)."""

    def sizeHint(self, option, index) -> QSize:  # noqa: N802 (Qt-Name)
        return QSize(RAIL_W - 8, RAIL_H)

    def paint(self, painter, option, index) -> None:  # noqa: N802 (Qt-Name)
        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        hover = bool(option.state & QStyle.StateFlag.State_MouseOver)
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        if selected:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(ORANGE_SOFT))
            painter.drawRoundedRect(QRectF(option.rect).adjusted(1, 1, -1, -1), 10, 10)
        elif hover:  # nur ein zarter orangefarbener Schein, Symbol und Schrift werden orange
            glow = QColor(ORANGE)
            glow.setAlpha(34)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(glow)
            painter.drawRoundedRect(QRectF(option.rect).adjusted(3, 3, -3, -3), 12, 12)
        lit = selected or hover
        icon = index.data(Qt.ItemDataRole.DecorationRole)
        if isinstance(icon, QIcon):
            mode = QIcon.Mode.Selected if lit else QIcon.Mode.Normal
            side = SIZE
            left = option.rect.x() + (option.rect.width() - side) // 2
            top = option.rect.y() + 6
            icon.paint(painter, left, top, side, side, Qt.AlignmentFlag.AlignCenter, mode)
        font = QFont(option.font)
        font.setPixelSize(11)
        painter.setFont(font)
        painter.setPen(QColor(ORANGE_HI if lit else MUTED))
        label = painter.fontMetrics().elidedText(str(index.data(Qt.ItemDataRole.DisplayRole) or ""),
                                                 Qt.TextElideMode.ElideRight, option.rect.width() - 6)
        text_rect = QRectF(option.rect.x() + 3, option.rect.y() + 6 + SIZE + 3, option.rect.width() - 6, 17)
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop, label)
        painter.restore()
