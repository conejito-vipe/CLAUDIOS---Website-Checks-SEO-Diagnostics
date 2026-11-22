"""Takt im Fenster: setzt alle 5 Sekunden den Wächter aus core/crashlog.py zurück.
Bleibt das Fenster länger als WATCHDOG_SECONDS hängen, schreibt der Wächter die Stapel aller Threads in die Absturz-Spur.
Ohne installierte Absturz-Spur (Tests) macht diese Klasse nichts."""
from __future__ import annotations

from PySide6.QtCore import QObject, QTimer
from PySide6.QtWidgets import QApplication

from ..core import crashlog

INTERVAL_MS = 5000


class Heartbeat(QObject):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._timer = QTimer(self)
        self._timer.setInterval(INTERVAL_MS)
        self._timer.timeout.connect(crashlog.arm)
        if crashlog.active():
            crashlog.arm()
            self._timer.start()
            app = QApplication.instance()
            if app is not None:
                app.aboutToQuit.connect(self.stop)

    def stop(self) -> None:
        self._timer.stop()
        crashlog.disarm()
