"""Auswahl bei der Deinstallation (wie im Schwesterprogramm): Liste der Teile mit Größe und Grund, eigene Daten nicht vorgewählt,
eine Bestätigung, erst dann wird „Jetzt deinstallieren“ frei. Das Fenster löscht selbst nichts; es liefert nur die Auswahl."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QCheckBox, QFrame, QHBoxLayout, QLabel, QPushButton, QScrollArea, QVBoxLayout, QWidget

from ..core.numfmt import format_bytes
from ..i18n.strings import get_lang, t
from .cardbox import MARGIN, CardDialog


def _plain(label: QLabel, name: str = "") -> QLabel:
    label.setTextFormat(Qt.TextFormat.PlainText)
    label.setWordWrap(True)
    if name:
        label.setObjectName(name)
    return label


class UninstallDialog(CardDialog):
    def __init__(self, parent, items: list) -> None:
        super().__init__(parent, t("uni.title"))
        self.resize(2 * MARGIN + 640, 2 * MARGIN + 600)
        self.items = items
        self.boxes: dict[str, QCheckBox] = {}
        heading = _plain(QLabel(t("uni.title")), "h1")
        intro = _plain(QLabel(t("uni.intro")), "muted")
        self.content.addWidget(heading)
        self.content.addWidget(intro)
        holder = QWidget()
        rows = QVBoxLayout(holder)
        rows.setContentsMargins(0, 0, 8, 0)
        rows.setSpacing(10)
        lang = get_lang()
        for item in items:
            row = QFrame()
            row.setObjectName("panel")
            lay = QVBoxLayout(row)
            lay.setContentsMargins(12, 8, 12, 8)
            lay.setSpacing(2)
            box = QCheckBox(item.label + (f"  ({t('uni.personal')})" if item.personal else ""))
            box.setChecked(bool(item.default))
            box.toggled.connect(self._sync)
            self.boxes[item.key] = box
            lay.addWidget(box)
            detail = item.why + (f"  ·  {format_bytes(item.size, lang)}" if item.size else "")
            lay.addWidget(_plain(QLabel(detail), "muted"))
            rows.addWidget(row)
        rows.addStretch(1)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(holder)
        self.content.addWidget(scroll, 1)
        self.content.addWidget(_plain(QLabel(t("uni.kept")), "muted"))
        self.confirm = QCheckBox(t("uni.confirm"))
        self.confirm.toggled.connect(self._sync)
        self.content.addWidget(self.confirm)
        buttons = QHBoxLayout()
        buttons.addStretch(1)
        cancel = QPushButton(t("uni.cancel"))
        cancel.clicked.connect(self.reject)
        self.go = QPushButton(t("uni.go"))
        self.go.setObjectName("danger")
        self.go.clicked.connect(self.accept)
        buttons.addWidget(cancel)
        buttons.addWidget(self.go)
        self.content.addLayout(buttons)
        self._sync()

    def selected(self) -> set[str]:
        return {key for key, box in self.boxes.items() if box.isChecked()}

    def _sync(self, *_args) -> None:
        self.go.setEnabled(self.confirm.isChecked() and bool(self.selected()))
