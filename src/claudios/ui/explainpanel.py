"""Erklärspalte der Ergebnisseite (Entwurf B, Variante 1): rechts neben der Befundliste, der Dialog bleibt für die
Vollansicht mit Codefenster."""
from __future__ import annotations

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QFrame, QLabel, QPushButton, QTextBrowser, QVBoxLayout

from ..i18n.strings import get_lang, t
from .finding_detail import explain_html, find_id, meta_for, meta_text

WIDTH = 340


class ExplainPanel(QFrame):
    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("panel")
        self.setFixedWidth(WIDTH)
        self.texts: list[str] | None = None
        self.check_id: str | None = None
        self.title = QLabel()
        self.title.setObjectName("h2")
        self.title.setWordWrap(True)
        self.title.setTextFormat(Qt.TextFormat.PlainText)
        self.view = QTextBrowser()
        self.view.setOpenLinks(False)
        self.view.setOpenExternalLinks(False)
        self.view.anchorClicked.connect(self._open)
        self.open_btn = QPushButton()
        self.open_btn.clicked.connect(self._open_dialog)
        self.open_dialog = lambda texts: False  # vom Hauptfenster auf den Erklär-Dialog gesetzt
        self.groups = lambda: []
        self.result = lambda: None
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 14, 16, 14)
        lay.setSpacing(10)
        for widget in (self.title, self.view):
            lay.addWidget(widget, 1 if widget is self.view else 0)
        lay.addWidget(self.open_btn)
        self.retranslate()

    def retranslate(self) -> None:
        self.open_btn.setText(t("explain.open"))
        self.show_for(self.texts)

    def show_for(self, texts: list[str] | None) -> None:
        self.texts = texts
        self.check_id = find_id(texts) if texts else None
        self.open_btn.setEnabled(self.check_id is not None)
        if self.check_id is None:
            self.title.setText(t("explain.title"))
            self.view.setPlainText(t("explain.hint"))
            return
        lang = get_lang()
        meta = meta_for(self.check_id)
        self.title.setText(f"{meta_text(meta, 'title', lang) or self.check_id} ({self.check_id})")
        self.view.setHtml(explain_html(self.check_id, self.groups(), texts, lang, meta, self.result()))

    def _open_dialog(self) -> None:
        if self.texts:
            self.open_dialog(self.texts)

    @staticmethod
    def _open(url: QUrl) -> None:
        if url.scheme() == "https":  # nur https, nie ein anderes Schema aus Inhalten
            QDesktopServices.openUrl(url)
