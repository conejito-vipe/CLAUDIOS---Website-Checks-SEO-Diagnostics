"""Scan im Hintergrund-Thread, damit die Oberfläche nie einfriert. Abbruch über ein Ereignis.
Ist Stufe 2 eingeschaltet, wird die Google-Berechtigung hier vor jedem Scan live geprüft."""
from __future__ import annotations

import asyncio
import threading

from PySide6.QtCore import QThread, Signal

from ..components.manager import component_checker
from ..core.engine import run_scan
from ..gsc.session import scan_overrides


def _components():
    try:
        return component_checker()
    except (ValueError, KeyError, OSError):
        return lambda _name: False


class ScanThread(QThread):
    progress = Signal(str, int, int)
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
        kwargs = dict(self._kwargs)
        kwargs.setdefault("components", _components())
        kwargs.update(await asyncio.to_thread(scan_overrides, kwargs["raw_url"], bool(kwargs.get("allow_localhost"))))
        return await run_scan(
            **kwargs,
            cancel=self._event,
            progress=lambda stage, cur, total: self.progress.emit(stage, cur, total),
        )

    def cancel(self) -> None:
        self._cancel_requested.set()
        loop, event = self._loop, self._event
        if loop is not None and event is not None:
            loop.call_soon_threadsafe(event.set)
