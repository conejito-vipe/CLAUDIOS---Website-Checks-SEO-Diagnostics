"""Seite Hilfe: Kopfzeile mit Titel und gemeinsamer Suche, darunter die Reiter Handbuch und
Technik-Doku mit Inhaltsverzeichnis links und Text rechts. Beide mit Hervorhebung, Technik-Doku mit Zeilenumbruch."""
from __future__ import annotations

from PySide6.QtWidgets import QHBoxLayout, QLabel, QLineEdit, QPlainTextEdit, QTabWidget, QVBoxLayout, QWidget

from .. import __version__
from ..i18n.strings import t
from .highlight import attach
from .pages import DocPage


class HelpPage(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.handbook = DocPage("handbook")
        self.tech = DocPage("tech")
        self.tech.view.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        attach(self.handbook.view)  # die Technik-Doku bekommt ihre Hervorhebung im Hauptfenster
        for page in (self.handbook, self.tech):
            page.search.setVisible(False)  # die Suche steht im Seitenkopf und gilt für beide Reiter
        self.title = QLabel()
        self.title.setObjectName("h1")
        self.search = QLineEdit()
        self.search.setClearButtonEnabled(True)
        self.search.setMinimumWidth(280)
        head = QHBoxLayout()
        head.addWidget(self.title, 1)
        head.addWidget(self.search)
        self.tabs = QTabWidget()
        self.tabs.addTab(self.handbook, "")
        self.tabs.addTab(self.tech, "")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addLayout(head)
        lay.addWidget(self.tabs, 1)
        self.search.textChanged.connect(self._on_search)
        self.tabs.currentChanged.connect(self._on_tab)

    def _current(self) -> DocPage:
        return self.tabs.currentWidget()

    def _on_search(self, text: str) -> None:
        for page in (self.handbook, self.tech):
            page.search.blockSignals(True)
            page.search.setText(text)
            page.search.blockSignals(False)
        self._current().refresh()  # der andere Reiter wird erst beim Wechsel neu gezeichnet (die Technik-Doku ist groß)

    def _on_tab(self, _index: int) -> None:
        self._current().refresh_if_stale()

    def retranslate(self) -> None:
        self.title.setText(t("doc.title", version=__version__))
        self.search.setPlaceholderText(t("doc.search"))
        self.tabs.setTabText(0, t("nav.handbook"))
        self.tabs.setTabText(1, t("nav.tech"))
        self.handbook.retranslate()
        self.tech.retranslate()
