"""Update-Hinweis beim Start (nur im installierten Programm) und Einspielen des Installers.

Die Prüfung läuft in einem Thread, drei Sekunden nach dem Start. Der Nutzer kann sie im Dialog abschalten
(Einstellung update_check = False). Der Installer startet mit /SILENT, schließt CLAUDIOS und startet es danach neu."""
from __future__ import annotations

import logging
import sys
import threading

from PySide6.QtCore import QProcess, QThread, QTimer, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QApplication, QLabel, QProgressBar, QPushButton

from .. import __version__
from ..core import updater
from ..core.errors import ClaudiosError, ErrorCode as E
from ..i18n.strings import n, t
from ..paths import cache_dir
from ..settings import save as save_settings
from .cardbox import MARGIN, SB, CardDialog, MessageCard
from .dialogs import error_info, show_error

log = logging.getLogger("claudios")
SILENT_ARGS = ["/SILENT", "/CLOSEAPPLICATIONS", "/NORESTART"]  # Inno Setup, Gedächtniswissen


class CheckThread(QThread):
    found = Signal(object)

    def run(self) -> None:
        try:
            self.found.emit(updater.fetch_latest())
        except Exception as exc:  # noqa: BLE001 – die Prüfung darf den Start nie stören
            log.info("update check failed: %r", exc)
            self.found.emit(None)


class DownloadThread(QThread):
    progress = Signal(int, int)
    result = Signal(object, object)

    def __init__(self, info) -> None:
        super().__init__()
        self.info = info
        self.cancel_event = threading.Event()

    def run(self) -> None:
        try:
            path = updater.download_installer(self.info, cache_dir() / "update", cancel=self.cancel_event,
                                              progress=lambda done, total: self.progress.emit(done, total))
        except Exception as exc:  # noqa: BLE001 – jeder Fehler wird mit Grund angezeigt
            self.result.emit(None, exc)
            return
        self.result.emit(path, None)


class UpdateDialog(CardDialog):
    def __init__(self, parent, info) -> None:
        super().__init__(parent, t("upd.title"))
        self.setMinimumWidth(2 * MARGIN + 480)
        self.info, self.path, self.error = info, None, None
        self.label = QLabel(t("upd.downloading", version=info.version, percent=n(0)))
        self.label.setWordWrap(True)
        self.bar = QProgressBar()
        self.bar.setRange(0, 100)
        self.bar.setTextVisible(False)
        self.cancel_btn = QPushButton(t("card.cancel"))
        self.cancel_btn.clicked.connect(self._cancel)
        for widget in (self.label, self.bar, self.cancel_btn):
            self.content.addWidget(widget)
        self.worker = DownloadThread(info)
        self.worker.progress.connect(self._on_progress)
        self.worker.result.connect(self._on_result)

    def _on_progress(self, done: int, total: int) -> None:
        percent = int(done / total * 100) if total else 0
        self.bar.setValue(percent)
        self.label.setText(t("upd.downloading", version=self.info.version, percent=n(percent)))

    def _on_result(self, path, error) -> None:
        self.path, self.error = path, error
        self.accept()

    def _cancel(self) -> None:
        self.worker.cancel_event.set()
        self.cancel_btn.setEnabled(False)

    def reject(self) -> None:
        self._cancel()  # geschlossen wird erst, wenn der Thread sich meldet

    def run(self):
        self.worker.start()
        self.exec()
        self.worker.wait(5000)
        return self.path


def install_update(window, info) -> None:
    if sys.platform == "darwin":  # der Mac hat keinen stillen Installer: die Seite der neuen Version öffnen (dort liegt die Mac-Datei)
        QDesktopServices.openUrl(QUrl(info.page_url))
        return
    dialog = UpdateDialog(window, info)
    path = dialog.run()
    if path is None:
        error = dialog.error
        if error is not None and not (isinstance(error, ClaudiosError) and error.code == E.INSTALL_CANCELLED):
            log.error("update download failed: %r", error)
            show_error(window, error_info(error))
        return
    log.info("starting installer %s", path.name)
    if QProcess.startDetached(str(path), SILENT_ARGS):
        QApplication.quit()
    else:
        MessageCard(window, "warning", t("upd.title"), t("upd.start_failed", path=path)).run()


def offer(window, info, settings: dict) -> None:
    def never() -> None:
        settings["update_check"] = False
        save_settings(settings)
        card.reject()

    card = MessageCard(window, "question", t("upd.title"), t("upd.text", version=info.version, current=__version__),
                       buttons=SB.Yes | SB.No, default=SB.Yes, extra=(t("upd.never"), never))
    if card.run() == SB.Yes:
        install_update(window, info)


def _stop(thread: QThread) -> None:
    if thread.isRunning() and not thread.wait(3000):
        thread.terminate()
        thread.wait(1000)


def start_update_check(window, settings: dict, frozen: bool | None = None) -> CheckThread | None:
    """Nur im installierten Programm und nur, wenn der Nutzer die Prüfung nicht abgeschaltet hat."""
    is_frozen = bool(getattr(sys, "frozen", False)) if frozen is None else frozen
    if not is_frozen or settings.get("update_check") is False:
        return None
    thread = CheckThread(window)

    def found(info) -> None:
        if info is not None and updater.is_newer(info.version, __version__):
            offer(window, info, settings)

    thread.found.connect(found)
    window._update_thread = thread  # noqa: SLF001 – hält den Thread am Leben
    QApplication.instance().aboutToQuit.connect(lambda: _stop(thread))
    QTimer.singleShot(3000, thread.start)
    return thread
