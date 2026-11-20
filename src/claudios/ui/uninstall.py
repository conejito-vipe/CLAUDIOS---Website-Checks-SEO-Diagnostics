"""Deinstallation aus dem Programm: entfernt Komponenten, Cache, Protokolldateien, Einstellungen, Berichte, den Verlauf
und gespeicherte API-Schlüssel und startet danach den Deinstaller von Inno Setup (unins000.exe im Programmordner).
Das Scan-Protokoll (audit.jsonl) und sein Kontrollwert bleiben bewusst erhalten: sonst würde eine Neuinstallation die
Tageslimits zurücksetzen oder die 3-Stunden-Sperre auslösen."""
from __future__ import annotations

import logging
import sys
from pathlib import Path

from PySide6.QtCore import QProcess
from PySide6.QtWidgets import QApplication, QMessageBox

from ..components import manager
from ..core import apikeys
from ..i18n.strings import t
from ..report import history


def uninstaller_path(exe: Path | None = None, frozen: bool | None = None) -> Path | None:
    is_frozen = bool(getattr(sys, "frozen", False)) if frozen is None else frozen
    if not is_frozen:
        return None
    path = Path(exe or sys.executable).parent / "unins000.exe"
    return path if path.is_file() else None


def perform_removal() -> list[str]:
    """Entfernt alles außer dem Scan-Protokoll. Gibt die Namen der Teile zurück, die nicht entfernt werden konnten."""
    failed: list[str] = []
    try:
        keys = [item.key for item in manager.uninstall_items()]
    except Exception:  # noqa: BLE001
        keys, failed = [], ["components"]
    if keys:
        failed += [key for key, error in manager.uninstall(keys).items() if error]
    try:
        history.delete_all()
    except Exception:  # noqa: BLE001
        failed.append("history")
    for service in apikeys.KNOWN:
        try:
            apikeys.delete(service)
        except Exception:  # noqa: BLE001
            failed.append(f"apikey:{service}")
    return failed


def _close_logging() -> None:
    root = logging.getLogger()
    for handler in list(root.handlers):
        handler.close()
        root.removeHandler(handler)


def run_uninstall(window) -> None:
    answer = QMessageBox.warning(window, t("app.uninstall"), t("app.uninstall.confirm"),
                                 QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                 QMessageBox.StandardButton.No)
    if answer != QMessageBox.StandardButton.Yes:
        return
    for page in getattr(window, "pages", []):
        stop = getattr(page, "shutdown", None)
        if callable(stop):
            stop()
    _close_logging()
    failed = perform_removal()
    if failed:
        QMessageBox.warning(window, t("app.uninstall"), t("app.uninstall.partial", items=", ".join(failed)))
    uninstaller = uninstaller_path()
    if uninstaller is None:
        QMessageBox.information(window, t("app.uninstall"), t("app.uninstall.manual"))
        return
    QProcess.startDetached(str(uninstaller), [])
    QApplication.quit()
