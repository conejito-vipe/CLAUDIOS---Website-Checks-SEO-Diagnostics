"""Öffnet den Ordner mit den Protokolldateien im Explorer (Schaltfläche in Fehlerdialogen)."""
from __future__ import annotations

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices

from ..paths import logs_dir


def open_logs() -> bool:
    return QDesktopServices.openUrl(QUrl.fromLocalFile(str(logs_dir())))
