"""Seite 'Search Console': Anmeldung, Stufe 2 und CSV-Import. Wird vom Hauptfenster automatisch gefunden."""
from __future__ import annotations

import threading
import webbrowser
from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import QCheckBox, QFileDialog, QLabel, QListWidget, QMessageBox, QPushButton, QVBoxLayout, QWidget

from ..core.errors import ClaudiosError, ErrorCode as E
from ..gsc import csvimport, oauth, session
from ..i18n.strings import n, t
from .dialogs import error_info, show_error

NAV_KEY = "nav.gsc"
MAX_JSON = 100_000


def _plain(label: QLabel) -> QLabel:
    label.setTextFormat(Qt.TextFormat.PlainText)
    label.setWordWrap(True)
    return label


class _Task(QThread):
    done = Signal()
    failed = Signal(object)

    def __init__(self, fn) -> None:
        super().__init__()
        self._fn = fn
        self.cancel_event = threading.Event()

    def run(self) -> None:
        try:
            self._fn(self.cancel_event)
        except Exception as exc:  # noqa: BLE001 – jeder Fehler wird dem Nutzer mit Grund gezeigt
            self.failed.emit(exc)
        else:
            self.done.emit()


def _read(path: str, limit: int) -> bytes:
    try:
        with open(path, "rb") as handle:
            return handle.read(limit + 1)
    except OSError as exc:
        raise ClaudiosError(E.GOOGLE_IMPORT, reason=type(exc).__name__) from None


class GscPage(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self._task: _Task | None = None
        session.SESSION.load_saved()
        self.title = _plain(QLabel())
        self.intro = _plain(QLabel())
        self.intro.setObjectName("muted")
        self.client_lbl = _plain(QLabel())
        self.import_btn = QPushButton()
        self.remember = QCheckBox()
        self.signin_btn = QPushButton()
        self.signin_btn.setObjectName("primary")
        self.signout_btn = QPushButton()
        self.status = _plain(QLabel())
        self.sites_lbl = _plain(QLabel())
        self.sites = QListWidget()
        self.refresh_btn = QPushButton()
        self.level2 = QCheckBox()
        self.level2_lbl = _plain(QLabel())
        self.level2_lbl.setObjectName("muted")
        self.csv_btn = QPushButton()
        self.csv_lbl = _plain(QLabel())
        self.csv_lbl.setObjectName("muted")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)
        for widget in (self.title, self.intro, self.client_lbl, self.import_btn, self.remember, self.signin_btn,
                       self.signout_btn, self.status, self.sites_lbl, self.sites, self.refresh_btn, self.level2,
                       self.level2_lbl, self.csv_btn, self.csv_lbl):
            lay.addWidget(widget)
        self.import_btn.clicked.connect(self.import_client)
        self.signin_btn.clicked.connect(self.sign_in)
        self.signout_btn.clicked.connect(self.sign_out)
        self.refresh_btn.clicked.connect(self.refresh_sites)
        self.level2.toggled.connect(self._toggle_level2)
        self.csv_btn.clicked.connect(self.import_csv)

    def retranslate(self) -> None:
        self.title.setText(t("gsc.title"))
        self.intro.setText(t("gsc.intro"))
        self.import_btn.setText(t("gsc.import_client"))
        self.signin_btn.setText(t("gsc.signin"))
        self.signout_btn.setText(t("gsc.signout"))
        self.sites_lbl.setText(t("gsc.sites"))
        self.refresh_btn.setText(t("gsc.refresh"))
        self.level2.setText(t("gsc.level2"))
        self.csv_btn.setText(t("gsc.csv_import"))
        self.refresh()

    def refresh(self) -> None:
        state = session.SESSION
        busy = self._task is not None
        self.client_lbl.setText(t("gsc.client.ok") if state.client else t("gsc.client.none"))
        eligible = state.eligible_sites()
        self.status.setText(t("gsc.status.in", count=n(len(state.sites)), eligible=n(len(eligible)))
                            if state.signed_in else t("gsc.status.out"))
        self.sites.clear()
        for entry in state.sites:
            self.sites.addItem(f"{entry.get('siteUrl', '')}  ({entry.get('permissionLevel', '')})")
        self.remember.setText(t("gsc.remember") if state.store.persistent else t("gsc.remember_na"))
        self.remember.setEnabled(state.store.persistent and not busy)
        self.import_btn.setEnabled(not busy)
        self.signin_btn.setEnabled(state.client is not None and not busy)
        self.signout_btn.setEnabled(state.signed_in and not busy)
        self.refresh_btn.setEnabled(state.signed_in and state.client is not None and not busy)
        self.level2.blockSignals(True)
        self.level2.setChecked(state.level2)
        self.level2.blockSignals(False)
        self.level2.setEnabled(bool(eligible) and not busy)
        self.level2_lbl.setText(t("gsc.level2_on") if state.level2 else "")
        count = len(state.csv_pages) if state.csv_pages else 0
        self.csv_lbl.setText(t("gsc.csv_ok", count=n(count)) if count else t("gsc.csv_hint"))

    def _fail(self, exc: BaseException) -> None:
        show_error(self, error_info(exc))

    def import_client(self) -> None:
        path, _filter = QFileDialog.getOpenFileName(self, t("gsc.dialog_json"), str(Path.home()), "JSON (*.json)")
        if not path:
            return
        try:
            data = _read(path, MAX_JSON)
            if len(data) > MAX_JSON:
                raise ClaudiosError(E.GOOGLE_IMPORT, reason="file too large")
            session.SESSION.set_client(oauth.parse_client_json(data.decode("utf-8-sig", errors="replace")))
        except ClaudiosError as exc:
            self._fail(exc)
        self.refresh()

    def _run(self, fn) -> None:
        if self._task is not None:
            return
        task = _Task(fn)
        task.done.connect(self.refresh)
        task.failed.connect(self._fail)
        task.finished.connect(self._clear)
        self._task = task
        self.refresh()
        task.start()

    def _clear(self) -> None:
        self._task = None
        self.refresh()

    def sign_in(self) -> None:
        state = session.SESSION
        if state.client is None:
            return
        remember = self.remember.isChecked() and state.store.persistent
        self.status.setText(t("gsc.signin_wait"))

        def work(cancel: threading.Event) -> None:
            tokens = oauth.sign_in(state.client, webbrowser.open, cancel=cancel)
            state.set_tokens(tokens, remember)
            state.list_sites()

        self._run(work)

    def refresh_sites(self) -> None:
        self._run(lambda cancel: session.SESSION.list_sites())

    def sign_out(self) -> None:
        session.SESSION.sign_out()
        self.refresh()

    def _toggle_level2(self, checked: bool) -> None:
        if checked:
            answer = QMessageBox.question(self, t("gsc.title"), t("gsc.level2_ask"))
            if answer != QMessageBox.StandardButton.Yes:
                self.refresh()
                return
        session.SESSION.level2 = checked
        self.refresh()

    def import_csv(self) -> None:
        path, _filter = QFileDialog.getOpenFileName(self, t("gsc.dialog_csv"), str(Path.home()), "CSV (*.csv)")
        if not path:
            return
        try:
            session.SESSION.csv_pages = csvimport.parse_pages_csv(_read(path, csvimport.MAX_BYTES))
        except ClaudiosError as exc:
            self._fail(exc)
        self.refresh()

    def shutdown(self) -> None:
        task = self._task
        if task is not None and task.isRunning():
            task.cancel_event.set()
            task.wait(5000)


def create(window) -> GscPage:
    return GscPage()
