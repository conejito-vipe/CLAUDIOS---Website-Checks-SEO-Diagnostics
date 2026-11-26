"""Wertungsring und Kategorie-Karten der Ergebnisseite (Entwurf B). Reine Anzeige: die Zahlen kommen aus dem Ergebnis."""
from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QProgressBar, QVBoxLayout, QWidget

from ..i18n.strings import n
from . import theme

GOOD, WARN, BAD = "#4CC38A", "#E8B93C", "#F0616D"


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
    def __init__(self, name: str, score: int) -> None:
        super().__init__()
        self.setObjectName("infoitem")
        self.name, self.score = name, score
        self.label = QLabel(name)
        self.label.setObjectName("muted")
        self.number = QLabel(n(score))
        self.number.setStyleSheet(f"font-size: 22px; font-weight: 700; color: {score_color(score)};")
        bar = QProgressBar()
        bar.setRange(0, 100)
        bar.setValue(score)
        bar.setTextVisible(False)
        bar.setFixedHeight(6)
        bar.setStyleSheet(f"QProgressBar::chunk {{ background: {score_color(score)}; border-radius: 3px; }}")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 8, 12, 10)
        lay.setSpacing(4)
        for widget in (self.label, self.number, bar):
            lay.addWidget(widget)


class CategoryRow(QWidget):
    """Eine Karte je bewertete Kategorie, nebeneinander."""

    def __init__(self) -> None:
        super().__init__()
        self.cards: list[CategoryCard] = []
        self._lay = QHBoxLayout(self)
        self._lay.setContentsMargins(0, 0, 0, 0)
        self._lay.setSpacing(10)

    def set_scores(self, scores: dict[str, int]) -> None:
        for card in self.cards:
            self._lay.removeWidget(card)
            card.deleteLater()
        self.cards = [CategoryCard(name, value) for name, value in scores.items()]
        for card in self.cards:
            self._lay.addWidget(card, 1)
        self.setVisible(bool(self.cards))
