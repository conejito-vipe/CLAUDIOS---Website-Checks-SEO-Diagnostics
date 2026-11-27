"""Hauptfenster im gleichen Look wie der Splash. Weitere Seiten kommen als neue Datei ui/page_*.py (Modul mit NAV_KEY und
create(fenster), das ein Widget mit retranslate() liefert), ohne Änderung hier.
Während eines Scans bleibt die Ansicht stehen (kein Sprung in die Ergebnisse) und die Sprache ist gesperrt."""
from __future__ import annotations

import importlib
import pkgutil
from pathlib import Path

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import (
    QAbstractScrollArea,
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ..core import angebot
from ..i18n.strings import get_lang, set_lang, t
from ..settings import save as save_settings
from .activity import short_activity
from .components_page import ComponentsPage
from .dialogs import AboutDialog
from .finding_detail import DetailLinker
from .footer_link import LinkFooter
from .heartbeat import Heartbeat
from .helppage import HelpPage
from .highlight import attach
from .navicons import RAIL_H, RAIL_ITEM, RAIL_W, SIZE, RailDelegate, nav_icon
from .pages import ScanPage, SettingsPage
from .results_page import ResultsPage
from .uninstall import run_uninstall
from .widgets import CardWindow, load_rail_logo

BASE_KEYS = ("nav.scan", "nav.results", "nav.help", "nav.components", "nav.settings")
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
        self.setMinimumSize(760, 600)
        self._prev = 0
        self._scan_running = False
        self.confirm_close = False  # app.py schaltet die Sicherheitsfrage ein
        self.last_result = None

        self.scan = ScanPage(lambda: self.settings)
        self.results = ResultsPage()
        self.help = HelpPage()
        self.handbook, self.tech = self.help.handbook, self.help.tech
        self.components = ComponentsPage()
        self.settings_page = SettingsPage(settings)
        self.pages = [self.scan, self.results, self.help, self.components, self.settings_page]
        keys = list(BASE_KEYS)
        self.services = None
        for key, page in _discover_pages(self):
            if key == "nav.services":  # Schlüssel und Dienste stehen innerhalb der einen Seite „Einstellungen“
                self.services = page
                self.settings_page.embed(page)
                continue
            keys.append(key)
            self.pages.append(page)
        keys.append("nav.about")
        self.nav_keys = tuple(keys)
        self.about_row = len(keys) - 1
        _style_headings(self.pages)
        self.scan.bar.setVisible(False)  # ein Balken für den ganzen Lauf: der in der Seitenleiste
        attach(self.tech.view)  # Syntax-Hervorhebung der Technik-Doku (das Handbuch bekommt sie in der Hilfe-Seite)
        self.detail = DetailLinker(self, lambda: self.last_result)  # Klick auf einen Befund: Erklärung

        self.nav = QListWidget()
        self.nav.setObjectName("nav")
        self.nav.setItemDelegate(RailDelegate(self.nav))
        self.nav.setIconSize(QSize(SIZE, SIZE))
        self.nav.setSpacing(0)
        self.nav.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.nav.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.nav.setMouseTracking(True)
        for _key in self.nav_keys:
            _item = QListWidgetItem("")
            _item.setIcon(nav_icon(_key))
            self.nav.addItem(_item)
        if "nav.pro" in self.nav_keys:  # ausgeliefert inaktiv: erst die Verwaltung schaltet die Seite frei
            self.nav.item(self.nav_keys.index("nav.pro")).setHidden(not angebot.AKTIV)
        self.nav.item(self.nav_keys.index("nav.help")).setHidden(True)  # „Hilfe“ öffnet der Knopf in der Titelleiste
        self.nav.item(self.nav_keys.index("nav.settings")).setHidden(True)  # „Einstellungen“: Zahnrad in der Titelleiste
        self.nav.item(self.about_row).setHidden(True)  # „Info“ steht klein in der Fußzeile
        self.uninstall_btn = QPushButton()
        self.uninstall_btn.setObjectName("railbtn")
        self.uninstall_btn.setIcon(nav_icon("uninstall", normal="#E57373", active="#FF8A80"))
        self.uninstall_btn.setIconSize(QSize(SIZE, SIZE))
        self.uninstall_btn.setFixedSize(RAIL_ITEM, RAIL_ITEM)
        self.uninstall_btn.clicked.connect(self.uninstall_all)
        side = QWidget()
        side.setFixedWidth(RAIL_W + 8)
        side_lay = QVBoxLayout(side)
        side_lay.setContentsMargins(0, 0, 0, 0)
        side_lay.setSpacing(8)
        visible = sum(1 for i in range(self.nav.count()) if not self.nav.item(i).isHidden())
        self.nav.setFixedHeight(visible * RAIL_H + 4)  # alle Einträge immer sichtbar: die Leiste scrollt nie
        self.nav.setSizeAdjustPolicy(QAbstractScrollArea.SizeAdjustPolicy.AdjustToContents)
        self.live_box = QWidget()  # Anzeige eines laufenden Scans, auf jeder Seite sichtbar (Leiste unter dem Inhalt)
        live_lay = QHBoxLayout(self.live_box)
        live_lay.setContentsMargins(24, 0, 24, 6)
        live_lay.setSpacing(12)
        self.live_title = QLabel()
        self.live_title.setObjectName("h2")
        self.live_text = QLabel()
        self.live_text.setObjectName("muted")
        self.live_text.setTextFormat(Qt.TextFormat.PlainText)
        self.live_bar = QProgressBar()
        self.live_bar.setRange(0, 100)
        self.live_bar.setTextVisible(False)
        self.live_bar.setFixedWidth(220)
        for widget in (self.live_title, self.live_bar):
            live_lay.addWidget(widget)
        live_lay.addWidget(self.live_text, 1)
        self.live_box.setVisible(False)
        self.logo = QLabel()
        self.logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.logo.setAccessibleName("CLAUDIOS")
        pix = load_rail_logo()
        if pix is not None:
            self.logo.setPixmap(pix.scaledToWidth(RAIL_W - 8, Qt.TransformationMode.SmoothTransformation))
        else:
            self.logo.setText("CLAUDIOS")
            self.logo.setObjectName("logofallback")
        side_lay.addWidget(self.logo)
        side_lay.addWidget(self.nav)
        side_lay.addStretch(1)
        side_lay.addWidget(self.uninstall_btn, 0, Qt.AlignmentFlag.AlignHCenter)
        self.uninstall_lbl = QLabel()
        self.uninstall_lbl.setObjectName("muted")
        self.uninstall_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        side_lay.addWidget(self.uninstall_lbl)
        self.setMinimumSize(760, max(600, side.sizeHint().height() + 130))  # die Leiste muss immer ganz passen (kein Überlauf)

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
        self.body.addWidget(self.live_box)
        self.body.addWidget(self.footer)

        self.titlebar.langChanged.connect(self.set_language)
        self.titlebar.helpRequested.connect(self.show_help)
        self.titlebar.settingsRequested.connect(self.show_settings)
        self.footer.clicked.connect(self.show_about)
        self.nav.currentRowChanged.connect(self._on_nav)
        self.scan.scan_finished.connect(self._on_result)
        self.scan.activity.connect(self._on_activity)
        self.scan.running_changed.connect(self._on_running)
        self.titlebar.set_lang(get_lang())
        self.retranslate()
        self._heartbeat = Heartbeat(self)  # Wächter gegen Einfrieren (nur mit Absturz-Spur aktiv)
        self.nav.setCurrentRow(0)

    def _attach_details(self) -> None:
        self.detail.attach_results(self.results.table)  # Klick: Vollansicht mit Blättern
        for page in self.pages:
            if type(page).__name__ != "ComponentsPage":
                self.detail.attach(page)

    def retranslate(self) -> None:
        self.setWindowTitle(t("app.title"))
        self.titlebar.set_help_text(t("nav.help"), t("nav.settings"))
        if self.services is not None:
            self.services.retranslate()
        self.titlebar.sync_maximized(self.isMaximized())
        for index, key in enumerate(self.nav_keys):
            self.nav.item(index).setText(t(key))
            self.nav.item(index).setToolTip(t(key))
        self.uninstall_lbl.setText(t("app.uninstall.short"))
        self.uninstall_btn.setToolTip(t("app.uninstall"))
        self.uninstall_btn.setAccessibleName(t("app.uninstall"))
        self.live_title.setText(t("nav.running"))
        for page in self.pages:
            page.retranslate()
            QApplication.processEvents()  # lässt den Ladekreis beim Sprachwechsel weiterdrehen
        self.footer.retranslate()
        self._attach_details()

    def set_language(self, lang: str) -> None:
        if self._scan_running:  # ein Wechsel mitten im Scan baut alle Seiten neu auf und lässt das Programm hängen
            return
        set_lang(lang)
        self.settings["language"] = lang
        save_settings(self.settings)
        self.titlebar.set_lang(lang)
        self.titlebar.spinner.start()
        try:
            self.retranslate()
        finally:
            self.titlebar.spinner.stop()

    def show_help(self) -> None:
        self.nav.setCurrentRow(self.nav_keys.index("nav.help"))

    def show_settings(self) -> None:
        self.nav.setCurrentRow(self.nav_keys.index("nav.settings"))

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

    def _on_running(self, running: bool) -> None:
        self._scan_running = running
        self.live_box.setVisible(running)
        for button in self.titlebar._lang_buttons.values():  # noqa: SLF001 – Flaggen sind im Scan gesperrt
            button.setEnabled(not running)
        if running:
            self.live_bar.setValue(0)
            self.live_text.setText("")
            self.results.mark_running()
        else:
            self.results.hide_live()

    def _on_activity(self, message: str, percent: int, _kind: str) -> None:
        self.live_bar.setValue(percent)
        self.live_text.setText(short_activity(message))

    def _on_result(self, result) -> None:
        self.last_result = result
        self.results.show_result(result)
        self._attach_details()
        self.nav.setCurrentRow(1)  # erst nach dem Ende des Scans in die Ergebnisse wechseln

    def _really_close(self) -> bool:
        """Sicherheitsfrage vor dem Schließen (nur im echten Programm; Tests und das Aufräumen fragen nicht)."""
        if not self.confirm_close:
            return True
        text = t("close.running") if self._scan_running else t("close.ask")
        box = QMessageBox(QMessageBox.Icon.Question, t("close.title"), text, parent=self)
        yes, no = box.addButton(t("close.yes"), QMessageBox.ButtonRole.AcceptRole), box.addButton(
            t("close.no"), QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(no)
        box.exec()
        return box.clickedButton() is yes

    def closeEvent(self, event) -> None:  # noqa: N802
        if not self._really_close():
            event.ignore()
            return
        for page in self.pages:
            stop = getattr(page, "shutdown", None)
            if callable(stop):
                stop()
        super().closeEvent(event)
