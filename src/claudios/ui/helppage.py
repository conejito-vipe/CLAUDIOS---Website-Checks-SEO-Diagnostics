"""Seite „Hilfe“: Handbuch und Technik-Doku als zwei Reiter einer Seite."""
from __future__ import annotations

from PySide6.QtWidgets import QTabWidget, QVBoxLayout, QWidget

from ..i18n.strings import t
from .pages import DocPage


class HelpPage(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.handbook = DocPage("handbook")
        self.tech = DocPage("tech")
        self.tabs = QTabWidget()
        self.tabs.addTab(self.handbook, "")
        self.tabs.addTab(self.tech, "")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self.tabs)

    def retranslate(self) -> None:
        self.tabs.setTabText(0, t("nav.handbook"))
        self.tabs.setTabText(1, t("nav.tech"))
        self.handbook.retranslate()
        self.tech.retranslate()
