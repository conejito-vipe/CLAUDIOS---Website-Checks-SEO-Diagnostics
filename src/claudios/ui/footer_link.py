"""Fußzeile mit dem Namen des Autors in Orange als Link auf sein GitHub-Profil. Der Text bleibt in strings_author.py: die
Zeile wird am Namen geteilt (vorher, Name als Knopf, nachher)."""
from __future__ import annotations

from PySide6.QtCore import QSize, Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QLabel, QPushButton

from ..i18n.strings import t
from ..i18n.strings_author import AUTHOR
from .navicons import nav_icon
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
        self.info_btn = QPushButton()
        self.info_btn.setObjectName("infobtn")
        self.info_btn.setIcon(nav_icon("nav.about", size=16))
        self.info_btn.setIconSize(QSize(16, 16))
        self.info_btn.setFixedSize(24, 24)
        self.info_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.info_btn.clicked.connect(lambda _checked=False: self.clicked.emit())
        layout = self.layout()
        layout.addWidget(self.info_btn)
        index = layout.indexOf(self.before)
        layout.insertWidget(index + 1, self.author)
        layout.insertWidget(index + 2, self.tail)

    def retranslate(self) -> None:
        super().retranslate()
        self.info_btn.setToolTip(t("nav.about"))
        self.info_btn.setAccessibleName(t("nav.about"))
        pre, name, post = self.before.text().partition(AUTHOR)
        self.author.setVisible(bool(name))
        self.tail.setVisible(bool(name))
        if name:
            self.before.setText(pre.rstrip())
            self.author.setText(name)
            self.tail.setText(post.strip())
