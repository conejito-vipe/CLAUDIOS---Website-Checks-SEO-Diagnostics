"""Fußzeile mit dem Namen des Autors in Orange als Link auf sein GitHub-Profil. Der Text bleibt in strings_author.py: die
Zeile wird am Namen geteilt (vorher, Name als Knopf, nachher)."""
from __future__ import annotations

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QLabel, QPushButton

from ..i18n.strings_author import AUTHOR
from .widgets import Footer

PROFILE_URL = f"https://github.com/{AUTHOR}"


class LinkFooter(Footer):
    def __init__(self) -> None:
        super().__init__()
        self.author = QPushButton()
        self.author.setObjectName("authorlink")
        self.author.setFlat(True)
        self.author.setCursor(Qt.CursorShape.PointingHandCursor)
        self.author.setToolTip(PROFILE_URL)
        self.author.clicked.connect(lambda _checked=False: QDesktopServices.openUrl(QUrl(PROFILE_URL)))
        self.tail = QLabel()
        self.tail.setObjectName("muted")
        self.tail.setTextFormat(Qt.TextFormat.PlainText)
        layout = self.layout()
        index = layout.indexOf(self.before)
        layout.insertWidget(index + 1, self.author)
        layout.insertWidget(index + 2, self.tail)

    def retranslate(self) -> None:
        super().retranslate()
        pre, name, post = self.before.text().partition(AUTHOR)
        self.author.setVisible(bool(name))
        self.tail.setVisible(bool(name))
        if name:
            self.before.setText(pre.rstrip())
            self.author.setText(name)
            self.tail.setText(post.strip())
