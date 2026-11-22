"""Hauptfenster im gleichen Look wie der Splash. Weitere Seiten kommen als neue Datei ui/page_*.py
(Modul mit NAV_KEY und create(fenster), das ein Widget mit retranslate() liefert), ohne Änderung hier."""
from __future__ import annotations

import importlib
import pkgutil
from pathlib import Path

from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ..i18n.strings import get_lang, set_lang, t
from ..settings import save as save_settings
from .components_page import ComponentsPage
from .dialogs import AboutDialog
from .finding_detail import DetailLinker
from .footer_link import LinkFooter
from .highlight import attach
from .pages import DocPage, ScanPage, SettingsPage
from .results_page import ResultsPage
from .uninstall import run_uninstall
from .widgets import CardWindow

BASE_KEYS = ("nav.scan", "nav.results", "nav.handbook", "nav.tech", "nav.components", "nav.settings")
SCROLL_PAGES = frozenset({"ServicesPage", "ExportPage", "ComponentsPage", "SettingsPage"})
H2_LABELS = ("url_lbl", "profile_lbl", "focus_lbl", "hist_title", "local_title")


def _discover_pages(window) -> list[tuple[str, object]]:
    found = []
    for info in sorted(pkgutil.iter_modules([str(Path(__file__).parent)]), key=lambda i: i.name):
        if info.name.startswith("page_"):
            module = importlib.import_module(f"{__package__}.{info.name}")
            found.append((module.NAV_KEY, module.create(window)))
    return found


def _scrolled(page: QWidget) -> QScrollArea:
    """Seiten aus vielen untereinander stehenden Elementen bekommen bei kleinem Fenster einen Scrollbalken."""
    area = QScrollArea()
    area.setWidgetResizable(True)
    area.setFrameShape(QFrame.Shape.NoFrame)
    area.setWidget(page)
    area.viewport().setAutoFillBackground(False)
    page.setAutoFillBackground(False)
    return area


def _style_headings(pages: list) -> None:
    for page in pages:
        title = getattr(page, "title", None)
        if isinstance(title, QLabel):
            title.setObjectName("h1")
        for name in H2_LABELS:
            label = getattr(page, name, None)
            if isinstance(label, QLabel):
                label.setObjectName("h2")


class MainWindow(CardWindow):
    def __init__(self, settings: dict) -> None:
        super().__init__(with_lang=True)
        self.settings = settings
        self.resize(1040, 700)
        self.setMinimumSize(760, 520)
        self._prev = 0
        self.last_result = None

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
        _style_headings(self.pages)
        attach(self.tech.view)  # Syntax-Hervorhebung der Technik-Doku (früher in der Seite „Einrichtung")
        self.detail = DetailLinker(self, lambda: self.last_result)  # Klick auf einen Befund: Erklärung

        self.nav = QListWidget()
        self.nav.setObjectName("nav")
        for _key in self.nav_keys:
            self.nav.addItem(QListWidgetItem(""))
        self.uninstall_btn = QPushButton()
        self.uninstall_btn.setObjectName("danger")
        self.uninstall_btn.clicked.connect(self.uninstall_all)
        side = QWidget()
        side.setFixedWidth(190)
        side_lay = QVBoxLayout(side)
        side_lay.setContentsMargins(0, 0, 0, 0)
        side_lay.setSpacing(8)
        side_lay.addWidget(self.nav, 1)
        side_lay.addWidget(self.uninstall_btn)

        self.stack = QStackedWidget()
        for page in self.pages:
            self.stack.addWidget(_scrolled(page) if type(page).__name__ in SCROLL_PAGES else page)
        self.footer = LinkFooter()

        middle = QHBoxLayout()
        middle.setContentsMargins(16, 8, 16, 8)
        middle.setSpacing(16)
        middle.addWidget(side)
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

    def _attach_details(self) -> None:
        for page in self.pages:
            if type(page).__name__ != "ComponentsPage":
                self.detail.attach(page)

    def retranslate(self) -> None:
        self.setWindowTitle(t("app.title"))
        for index, key in enumerate(self.nav_keys):
            self.nav.item(index).setText(t(key))
        self.uninstall_btn.setText(t("app.uninstall"))
        for page in self.pages:
            page.retranslate()
        self.footer.retranslate()
        self._attach_details()

    def set_language(self, lang: str) -> None:
        set_lang(lang)
        self.settings["language"] = lang
        save_settings(self.settings)
        self.titlebar.set_lang(lang)
        self.retranslate()

    def show_about(self) -> None:
        AboutDialog(self).exec()

    def uninstall_all(self) -> None:
        run_uninstall(self)

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
            self._attach_details()  # Seiten bauen ihre Listen teils erst beim Anzeigen

    def _on_result(self, result) -> None:
        self.last_result = result
        self.results.show_result(result)
        self._attach_details()
        self.nav.setCurrentRow(1)

    def closeEvent(self, event) -> None:  # noqa: N802
        for page in self.pages:
            stop = getattr(page, "shutdown", None)
            if callable(stop):
                stop()
        super().closeEvent(event)
