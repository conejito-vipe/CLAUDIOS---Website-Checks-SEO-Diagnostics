"""Hauptfenster im gleichen Look wie der Splash."""
from __future__ import annotations

from PySide6.QtWidgets import QHBoxLayout, QListWidget, QListWidgetItem, QStackedWidget

from ..i18n.strings import set_lang, t
from ..settings import save as save_settings
from .dialogs import AboutDialog
from .pages import DocPage, ResultsPage, ScanPage, SettingsPage
from .widgets import CardWindow, Footer

NAV_KEYS = ("nav.scan", "nav.results", "nav.handbook", "nav.tech", "nav.settings", "nav.about")
ABOUT_ROW = 5


class MainWindow(CardWindow):
    def __init__(self, settings: dict) -> None:
        super().__init__(with_lang=True)
        self.settings = settings
        self.resize(1040, 700)
        self.setMinimumSize(900, 620)
        self._prev = 0

        self.nav = QListWidget()
        self.nav.setObjectName("nav")
        self.nav.setFixedWidth(190)
        for _key in NAV_KEYS:
            self.nav.addItem(QListWidgetItem(""))
        self.scan = ScanPage(lambda: self.settings)
        self.results = ResultsPage()
        self.handbook = DocPage("handbook")
        self.tech = DocPage("tech")
        self.settings_page = SettingsPage(settings)
        self.pages = (self.scan, self.results, self.handbook, self.tech, self.settings_page)
        self.stack = QStackedWidget()
        for page in self.pages:
            self.stack.addWidget(page)
        self.footer = Footer(with_grip=True)

        middle = QHBoxLayout()
        middle.setContentsMargins(16, 8, 16, 8)
        middle.setSpacing(16)
        middle.addWidget(self.nav)
        middle.addWidget(self.stack, 1)
        self.body.addLayout(middle, 1)
        self.body.addWidget(self.footer)

        self.titlebar.langChanged.connect(self.set_language)
        self.footer.clicked.connect(self.show_about)
        self.nav.currentRowChanged.connect(self._on_nav)
        self.scan.scan_finished.connect(self._on_result)
        self.titlebar.set_lang(self._lang())
        self.retranslate()
        self.nav.setCurrentRow(0)

    @staticmethod
    def _lang() -> str:
        from ..i18n.strings import get_lang

        return get_lang()

    def retranslate(self) -> None:
        self.setWindowTitle(t("app.title"))
        for index, key in enumerate(NAV_KEYS):
            self.nav.item(index).setText(t(key))
        for page in self.pages:
            page.retranslate()
        self.footer.retranslate()

    def set_language(self, lang: str) -> None:
        set_lang(lang)
        self.settings["language"] = lang
        save_settings(self.settings)
        self.titlebar.set_lang(lang)
        self.retranslate()

    def show_about(self) -> None:
        AboutDialog(self).exec()

    def _on_nav(self, row: int) -> None:
        if row == ABOUT_ROW:
            self.show_about()
            self.nav.blockSignals(True)
            self.nav.setCurrentRow(self._prev)
            self.nav.blockSignals(False)
            return
        if row >= 0:
            self._prev = row
            self.stack.setCurrentIndex(row)

    def _on_result(self, result) -> None:
        self.results.show_result(result)
        self.nav.setCurrentRow(1)

    def closeEvent(self, event) -> None:  # noqa: N802
        self.scan.shutdown()
        super().closeEvent(event)
