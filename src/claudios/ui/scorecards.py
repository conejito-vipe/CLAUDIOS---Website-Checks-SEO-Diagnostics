"""Wertungsring und Kategorie-Karten der Ergebnisseite (Entwurf B). Reine Anzeige: die Zahlen kommen aus dem Ergebnis."""
from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QFrame, QGridLayout, QLabel, QProgressBar, QWidget

from ..i18n.strings import n
from ..i18n.strings_names import category_name
from . import theme

GOOD, WARN, BAD = "#5FD9A0", "#F2C94C", "#FF8590"


SEVERITY = {0: "#C0CAD6", 1: "#82BEFF", 2: WARN, 3: "#FF9A55", 4: BAD}


def style_severity(item, severity: int) -> None:
    """Schwere als farbige, fette Zelle (Chip-Ersatz in der Tabelle); der Text bleibt für Screenreader erhalten."""
    item.setForeground(QColor(SEVERITY[severity]))
    font = item.font()
    font.setBold(True)
    item.setFont(font)


def score_color(score: int) -> str:
    """Grün ab 80, Gelb ab 50, sonst Rot. Alle drei sind auf dem dunklen Grund lesbar (siehe Kontrasttest)."""
    return GOOD if score >= 80 else WARN if score >= 50 else BAD


class ScoreRing(QWidget):
    """Kreisbogen von 0 bis 100 mit der Zahl in der Mitte; ohne Wert bleibt nur die leere Spur."""

    def __init__(self, size: int = 132) -> None:
        super().__init__()
        self.value: int | None = None
        self.setFixedSize(size, size)
        self.setAccessibleName("score")

    def set_value(self, value: int | None) -> None:
        self.value = value
        self.setAccessibleDescription("" if value is None else str(value))
        self.update()

    def paintEvent(self, _event) -> None:  # noqa: N802 – Qt
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        width = 12
        rect = QRectF(self.rect()).adjusted(width, width, -width, -width)
        pen = QPen(QColor(theme.TRACK), width)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.drawEllipse(rect)
        if self.value is None:
            return
        pen.setColor(QColor(score_color(self.value)))
        painter.setPen(pen)
        painter.drawArc(rect, 90 * 16, -round(360 * 16 * max(0, min(100, self.value)) / 100))
        font = QFont(self.font())
        font.setPixelSize(self.height() // 3)
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(QColor(theme.INK))
        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, n(self.value))


class CategoryCard(QFrame):
    """Eine Karte je Bereich: Klartext-Name links, Wert rechts, darunter der Balken."""

    def __init__(self, name: str, score: int) -> None:
        super().__init__()
        self.setObjectName("infoitem")
        self.name, self.score = name, score
        self.label = QLabel(category_name(name))
        self.label.setObjectName("cardname")
        self.label.setToolTip(category_name(name))
        self.number = QLabel(n(score))
        self.number.setStyleSheet(f"font-size: 18px; font-weight: 700; color: {score_color(score)};")
        bar = QProgressBar()
        bar.setRange(0, 100)
        bar.setValue(score)
        bar.setTextVisible(False)
        bar.setFixedHeight(5)
        bar.setStyleSheet(f"QProgressBar::chunk {{ background: {score_color(score)}; border-radius: 2px; }}")
        lay = QGridLayout(self)
        lay.setContentsMargins(10, 5, 10, 6)
        lay.setHorizontalSpacing(8)
        lay.setVerticalSpacing(3)
        lay.addWidget(self.label, 0, 0)
        lay.addWidget(self.number, 0, 1, Qt.AlignmentFlag.AlignRight)
        lay.addWidget(bar, 1, 0, 1, 2)
        lay.setColumnStretch(0, 1)


class CategoryRow(QWidget):
    """Die Karten der Bereiche in einem Raster; die Spaltenzahl richtet sich nach der Breite (lesbar, auch maximiert)."""

    MIN_CARD = 170

    def __init__(self) -> None:
        super().__init__()
        self.cards: list[CategoryCard] = []
        self._grid = QGridLayout(self)
        self._grid.setContentsMargins(0, 0, 0, 0)
        self._grid.setHorizontalSpacing(10)
        self._grid.setVerticalSpacing(6)
        self._cols = 0

    def columns(self) -> int:
        return max(2, min(6, self.width() // self.MIN_CARD)) if self.width() > 0 else 4

    def _layout_cards(self) -> None:
        cols = self.columns()
        self._cols = cols
        for index, card in enumerate(self.cards):
            self._grid.addWidget(card, index // cols, index % cols)
        for col in range(6):
            self._grid.setColumnStretch(col, 1 if col < cols else 0)

    def set_scores(self, scores: dict[str, int]) -> None:
        for card in self.cards:
            self._grid.removeWidget(card)
            card.deleteLater()
        self.cards = [CategoryCard(name, value) for name, value in scores.items()]
        self._layout_cards()
        self.setVisible(bool(self.cards))

    def resizeEvent(self, event) -> None:  # noqa: N802 – Qt
        super().resizeEvent(event)
        if self.columns() != self._cols and self.cards:
            self._layout_cards()
