"""Hauptfenster im gleichen Look wie der Splash. Weitere Seiten kommen als neue Datei ui/page_*.py
(Modul mit NAV_KEY und create(fenster), das ein Widget mit retranslate() liefert), ohne Änderung hier."""
from __future__ import annotations

import importlib
import pkgutil
from pathlib import Path

from PySide6.QtWidgets import QHBoxLayout, QListWidget, QListWidgetItem, QStackedWidget

from ..i18n.strings import get_lang, set_lang, t
from ..settings import save as save_settings
from .components_page import ComponentsPage
from .dialogs import AboutDialog
from .pages import DocPage, ResultsPage, ScanPage, SettingsPage
from .widgets import CardWindow, Footer

BASE_KEYS = ("nav.scan", "nav.results", "nav.handbook", "nav.tech", "nav.components", "nav.settings")


def _discover_pages(window) -> list[tuple[str, object]]:
    found = []
    for info in sorted(pkgutil.iter_modules([str(Path(__file__).parent)]), key=lambda i: i.name):
        if info.name.startswith("page_"):
            module = importlib.import_module(f"{__package__}.{info.name}")
            found.append((module.NAV_KEY, module.create(window)))
    return found


class MainWindow(CardWindow):
    def __init__(self, settings: dict) -> None:
        super().__init__(with_lang=True)
        self.settings = settings
        self.resize(1040, 700)
        self.setMinimumSize(900, 620)
        self._prev = 0

        self.scan = ScanPage(lambda: self.settings)
        self.results = ResultsPage()
        self.handbook = DocPage("handbook")
        self.tech = DocPage("tech")
        self.components = ComponentsPage()
        self.settings_page = SettingsPage(settings)
        self.pages = [self.scan, self.results, self.handbook, self.tech, self.components, self.settings_page]
        keys = list(BASE_KEYS)
        for key, page in _discover_pages(self):
            keys.append(key)
            self.pages.append(page)
        keys.append("nav.about")
        self.nav_keys = tuple(keys)
        self.about_row = len(keys) - 1

        self.nav = QListWidget()
        self.nav.setObjectName("nav")
        self.nav.setFixedWidth(190)
        for _key in self.nav_keys:
            self.nav.addItem(QListWidgetItem(""))
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
        self.titlebar.set_lang(get_lang())
        self.retranslate()
        self.nav.setCurrentRow(0)

    def retranslate(self) -> None:
        self.setWindowTitle(t("app.title"))
        for index, key in enumerate(self.nav_keys):
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
        if row == self.about_row:
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
        for page in self.pages:
            stop = getattr(page, "shutdown", None)
            if callable(stop):
                stop()
        super().closeEvent(event)
