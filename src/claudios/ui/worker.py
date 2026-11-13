"""Scan im Hintergrund-Thread, damit die Oberfläche nie einfriert. Abbruch über ein Ereignis."""
from __future__ import annotations

import asyncio
import threading

from PySide6.QtCore import QThread, Signal

from ..core.engine import run_scan


class ScanThread(QThread):
    progress = Signal(int, int)
    done = Signal(object)
    failed = Signal(object)

    def __init__(self, kwargs: dict) -> None:
        super().__init__()
        self._kwargs = kwargs
        self._loop: asyncio.AbstractEventLoop | None = None
        self._event: asyncio.Event | None = None
        self._cancel_requested = threading.Event()

    def run(self) -> None:
        try:
            result = asyncio.run(self._main())
        except Exception as exc:  # jeder Fehler wird dem Nutzer mit Grund gezeigt
            self.failed.emit(exc)
        else:
            self.done.emit(result)

    async def _main(self):
        self._loop = asyncio.get_running_loop()
        self._event = asyncio.Event()
        if self._cancel_requested.is_set():
            self._event.set()
        return await run_scan(
            **self._kwargs,
            cancel=self._event,
            progress=lambda _stage, cur, total: self.progress.emit(cur, total),
        )

    def cancel(self) -> None:
        self._cancel_requested.set()
        loop, event = self._loop, self._event
        if loop is not None and event is not None:
            loop.call_soon_threadsafe(event.set)
