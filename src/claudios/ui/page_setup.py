"""Seite 'Einrichtung' (Assistent beim ersten Start). Wird vom Hauptfenster automatisch gefunden.
create() hängt außerdem die Syntax-Hervorhebung an die Technik-Doku (window.tech)."""
from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QLabel, QListWidget, QPushButton, QVBoxLayout, QWidget

from .. import paths
from ..components import manager
from ..components.lock import load_lock
from ..i18n.strings import n, t
from .highlight import attach

NAV_KEY = "nav.setup"
MARKER = "setup_done"


def _plain(label: QLabel) -> QLabel:
    label.setTextFormat(Qt.TextFormat.PlainText)
    label.setWordWrap(True)
    return label


def _done() -> bool:
    return (paths.config_dir() / MARKER).exists()


class SetupPage(QWidget):
    def __init__(self, window) -> None:
        super().__init__()
        self._window = window
        self.title = _plain(QLabel())
        self.intro = _plain(QLabel())
        self.intro.setObjectName("muted")
        self.step1 = _plain(QLabel())
        self.status = _plain(QLabel())
        self.components = QListWidget()
        self.to_components = QPushButton()
        self.step2 = _plain(QLabel())
        self.to_gsc = QPushButton()
        self.step3 = _plain(QLabel())
        self.to_scan = QPushButton()
        self.notes = _plain(QLabel())
        self.notes.setObjectName("muted")
        self.finish_btn = QPushButton()
        self.finish_btn.setObjectName("primary")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)
        for widget in (self.title, self.intro, self.step1, self.status, self.components, self.to_components,
                       self.step2, self.to_gsc, self.step3, self.to_scan, self.notes, self.finish_btn):
            lay.addWidget(widget)
        self.to_components.clicked.connect(lambda: self.go("nav.components"))
        self.to_gsc.clicked.connect(lambda: self.go("nav.gsc"))
        self.to_scan.clicked.connect(lambda: self.go("nav.scan"))
        self.finish_btn.clicked.connect(self.finish)

    def go(self, key: str) -> None:
        keys = tuple(getattr(self._window, "nav_keys", ()))
        if key in keys:
            self._window.nav.setCurrentRow(keys.index(key))

    def show_first(self) -> None:
        self.go(NAV_KEY)

    def finish(self) -> None:
        try:
            (paths.config_dir() / MARKER).write_text("1", "utf-8")
        except OSError:
            pass  # dann erscheint der Assistent beim nächsten Start noch einmal
        self.go("nav.scan")

    def retranslate(self) -> None:
        self.title.setText(t("setup.title"))
        self.intro.setText(t("setup.intro"))
        self.step1.setText(t("setup.step1"))
        self.to_components.setText(t("setup.to_components"))
        self.step2.setText(t("setup.step2"))
        self.to_gsc.setText(t("setup.to_gsc"))
        self.step3.setText(t("setup.step3"))
        self.to_scan.setText(t("setup.to_scan"))
        self.notes.setText(t("setup.notes"))
        self.finish_btn.setText(t("setup.finish"))
        self.refresh()

    def refresh(self) -> None:
        try:
            lock = load_lock()
        except (ValueError, KeyError, OSError):
            lock = []
        self.components.clear()
        installed = 0
        for comp in lock:
            state = manager.status(comp)
            installed += state == "installed"
            self.components.addItem(f"{comp.title}: {t('cmp.st.' + state)}")
        self.status.setText(t("setup.status", ok=n(installed), total=n(len(lock))))

    def showEvent(self, event) -> None:  # noqa: N802 (Name von Qt)
        self.refresh()
        super().showEvent(event)


def create(window) -> SetupPage:
    attach(window.tech.view)
    page = SetupPage(window)
    if not _done():
        QTimer.singleShot(0, page.show_first)
    return page
