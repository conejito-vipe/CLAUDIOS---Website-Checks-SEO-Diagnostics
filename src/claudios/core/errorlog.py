"""Protokollierung für das echte Programm (wird nur von app.py aufgerufen, nicht in Tests).

Jeder ClaudiosError wird beim Entstehen mit Code und Angaben ins Protokoll geschrieben, unbehandelte Ausnahmen (auch in
Threads) ebenfalls. So ist die Logdatei nie leer, wenn etwas schiefgeht. Geheimnisse filtert der RedactFilter am Handler."""
from __future__ import annotations

import logging
import platform
import sys
import threading

from .. import __version__
from .errors import ClaudiosError

log = logging.getLogger("claudios.errors")


def _code(value) -> str:
    return str(getattr(value, "value", value))


def install() -> None:
    original = ClaudiosError.__init__
    if getattr(original, "_claudios_logged", False):
        return

    def init(self, *args, **kwargs) -> None:
        original(self, *args, **kwargs)
        log.warning("error %s %s", _code(args[0]) if args else "?", kwargs)

    init._claudios_logged = True  # type: ignore[attr-defined]
    ClaudiosError.__init__ = init  # type: ignore[method-assign]

    def hook(exc_type, exc, tb) -> None:
        log.critical("uncaught exception", exc_info=(exc_type, exc, tb))
        try:
            sys.__excepthook__(exc_type, exc, tb)
        except Exception:  # noqa: BLE001 – ohne Konsole (windowed) gibt es keine Ausgabe
            pass

    def thread_hook(args) -> None:
        name = args.thread.name if args.thread else "?"
        log.critical("uncaught exception in thread %s", name,
                     exc_info=(args.exc_type, args.exc_value, args.exc_traceback))

    sys.excepthook = hook
    threading.excepthook = thread_hook


def log_startup() -> None:
    logging.getLogger("claudios").info("CLAUDIOS %s started (Python %s, frozen=%s, %s)", __version__,
                                       platform.python_version(), bool(getattr(sys, "frozen", False)),
                                       platform.platform())
