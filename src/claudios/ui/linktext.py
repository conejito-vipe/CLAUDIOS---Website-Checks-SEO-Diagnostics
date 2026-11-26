"""Textfeld mit anklickbaren https-Adressen (Hilfe). Die Adressen werden blau unterstrichen; ein Klick ohne Auswahl öffnet
sie im Browser. Es werden nur Adressen mit https geöffnet."""
from __future__ import annotations

import re

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QColor, QDesktopServices, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import QPlainTextEdit, QTextEdit

URL = re.compile(r"""https://[^\s<>"')\]]+""")
TRAIL = ".,;:!?)"


def url_spans(text: str) -> list[tuple[int, int]]:
    spans = []
    for match in URL.finditer(text):
        url = match.group(0).rstrip(TRAIL)
        spans.append((match.start(), match.start() + len(url)))
    return spans


def url_at_column(line: str, column: int) -> str | None:
    for start, end in url_spans(line):
        if start <= column < end:
            return line[start:end]
    return None


class LinkText(QPlainTextEdit):
    def __init__(self, *args) -> None:
        super().__init__(*args)
        self.viewport().setMouseTracking(True)
        self._marks: list[str] = []

    def set_marks(self, terms: list[str]) -> None:
        """Suchbegriffe, die im Text farbig hinterlegt werden (zusammen mit den Links in den Zusatzauswahlen)."""
        self._marks = [term for term in terms if len(term.strip()) > 1]
        self.underline_links()

    def underline_links(self) -> None:
        fmt = QTextCharFormat()
        fmt.setForeground(QColor("#8EC0FF"))
        fmt.setFontUnderline(True)
        selections = []
        text = self.toPlainText()
        mark = QTextCharFormat()
        mark.setBackground(QColor("#6B4310"))
        mark.setForeground(QColor("#FFFFFF"))
        for term in self._marks:
            for match in re.finditer(re.escape(term.strip()), text, re.IGNORECASE):
                cursor = QTextCursor(self.document())
                cursor.setPosition(match.start())
                cursor.setPosition(match.end(), QTextCursor.MoveMode.KeepAnchor)
                selection = QTextEdit.ExtraSelection()
                selection.cursor = cursor
                selection.format = mark
                selections.append(selection)
        for start, end in url_spans(text):
            cursor = QTextCursor(self.document())
            cursor.setPosition(start)
            cursor.setPosition(end, QTextCursor.MoveMode.KeepAnchor)
            selection = QTextEdit.ExtraSelection()
            selection.cursor = cursor
            selection.format = fmt
            selections.append(selection)
        self.setExtraSelections(selections)

    def _url_under(self, pos) -> str | None:
        cursor = self.cursorForPosition(pos)
        return url_at_column(cursor.block().text(), cursor.positionInBlock())

    def mouseMoveEvent(self, event) -> None:  # noqa: N802 (Qt-Name)
        super().mouseMoveEvent(event)
        over = self._url_under(event.position().toPoint())
        self.viewport().setCursor(Qt.CursorShape.PointingHandCursor if over else Qt.CursorShape.IBeamCursor)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802 (Qt-Name)
        url = None
        if event.button() == Qt.MouseButton.LeftButton and not self.textCursor().hasSelection():
            url = self._url_under(event.position().toPoint())
        super().mouseReleaseEvent(event)
        if url:
            QDesktopServices.openUrl(QUrl(url))
