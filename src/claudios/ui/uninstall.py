"""Deinstallation aus dem Programm: entfernt Komponenten, Cache, Protokolldateien, Einstellungen, Berichte, den Verlauf
und gespeicherte API-Schlüssel und startet danach den Deinstaller von Inno Setup (unins000.exe im Programmordner).
Das Scan-Protokoll (audit.jsonl) und sein Kontrollwert bleiben bewusst erhalten: sonst würde eine Neuinstallation die
Tageslimits zurücksetzen oder die 3-Stunden-Sperre auslösen."""
from __future__ import annotations

import logging
import sys
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QProcess
from PySide6.QtWidgets import QApplication, QMessageBox

from ..components import manager
from ..core import apikeys, crashlog
from ..i18n.strings import t
from ..report import history


def display_folder() -> str:
    """Der Datenordner, wie ihn das System nennt (für die Meldung bei nicht entfernten Teilen)."""
    return "~/Library/Application Support/CLAUDIOS" if sys.platform == "darwin" else "%LOCALAPPDATA%\\CLAUDIOS"


def uninstaller_path(exe: Path | None = None, frozen: bool | None = None) -> Path | None:
    is_frozen = bool(getattr(sys, "frozen", False)) if frozen is None else frozen
    if not is_frozen:
        return None
    path = Path(exe or sys.executable).parent / "unins000.exe"
    return path if path.is_file() else None


PERSONAL = frozenset({"config", "reports", "history", "keys"})


@dataclass
class PlanItem:
    key: str          # tool:<name> | cache | logs | config | reports | history | keys | program
    label: str
    why: str
    size: int | None
    default: bool
    personal: bool


def plan() -> list[PlanItem]:
    """Alles, was CLAUDIOS auf dem Computer angelegt hat, zum Auswählen. Eigene Daten sind nicht vorgewählt."""
    items: list[PlanItem] = []
    try:
        found = manager.uninstall_items()
    except Exception:  # noqa: BLE001 – ohne Liste bleiben die übrigen Einträge
        found = []
    for item in found:
        base = "tool" if item.key.startswith("tool:") else item.key
        label = t("uni.item.tool", name=item.title) if base == "tool" else t(f"uni.item.{base}")
        items.append(PlanItem(item.key, label, t(f"uni.why.{base}"), item.size, bool(item.default), base in PERSONAL))
    try:
        has_history = history.count() > 0
    except Exception:  # noqa: BLE001
        has_history = False
    if has_history:
        items.append(PlanItem("history", t("uni.item.history"), t("uni.why.history"), None, False, True))
    try:
        has_keys = any(apikeys.has_key(service) for service in apikeys.KNOWN)
    except Exception:  # noqa: BLE001
        has_keys = False
    if has_keys:
        items.append(PlanItem("keys", t("uni.item.keys"), t("uni.why.keys"), None, False, True))
    if uninstaller_path() is not None:
        items.append(PlanItem("program", t("uni.item.program"), t("uni.why.program"), None, True, False))
    return items


def perform_removal(selected: set[str] | None = None) -> list[str]:
    """Entfernt die gewählten Teile (ohne Auswahl: alles außer dem Scan-Protokoll). Gibt die Namen der Teile zurück, die
    nicht entfernt werden konnten."""
    failed: list[str] = []
    try:
        keys = [item.key for item in manager.uninstall_items()]
    except Exception:  # noqa: BLE001
        keys, failed = [], ["components"]
    if selected is not None:
        keys = [key for key in keys if key in selected]
    if keys:
        failed += [key for key, error in manager.uninstall(keys).items() if error]
    if selected is None or "history" in selected:
        try:
            history.delete_all()
        except Exception:  # noqa: BLE001
            failed.append("history")
    if selected is None or "keys" in selected:
        for service in apikeys.KNOWN:
            try:
                apikeys.delete(service)
            except Exception:  # noqa: BLE001
                failed.append(f"apikey:{service}")
    return failed


def _close_logging() -> None:
    crashlog.shutdown()  # sonst hält Windows die Absturz-Spur offen
    root = logging.getLogger()
    for handler in list(root.handlers):
        handler.close()
        root.removeHandler(handler)


def run_uninstall(window) -> None:
    from .uninstall_dialog import UninstallDialog

    dialog = UninstallDialog(window, plan())
    if dialog.exec() != dialog.DialogCode.Accepted:
        return
    selected = dialog.selected()
    for page in getattr(window, "pages", []):
        stop = getattr(page, "shutdown", None)
        if callable(stop):
            stop()
    _close_logging()
    failed = perform_removal(selected - {"program"})
    if failed:
        QMessageBox.warning(window, t("app.uninstall"), t("app.uninstall.partial", items=", ".join(failed), folder=display_folder()))
    if "program" not in selected:
        return
    uninstaller = uninstaller_path()
    if uninstaller is None:
        QMessageBox.information(window, t("app.uninstall"), t("app.uninstall.manual.mac" if sys.platform == "darwin" else "app.uninstall.manual"))
        return
    QProcess.startDetached(str(uninstaller), [])
    QApplication.quit()
