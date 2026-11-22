"""Absturz-Spur und Wächter gegen Einfrieren (wird nur von app.py aufgerufen, nicht in Tests).
Ein Einfrieren löst keine Python-Ausnahme aus, ein Absturz in Qt oder Windows ebenso wenig: das normale Protokoll bleibt dann
leer. Diese Datei (logs/CLAUDIOS-crash.log) bekommt deshalb zwei Spuren: bei einem harten Absturz die Python-Stapel aller
Threads (faulthandler) und, wenn das Fenster länger als WATCHDOG_SECONDS nicht mehr reagiert, ebenfalls alle Stapel.
Der Takt dazu kommt aus ui/heartbeat.py. Es werden nur Dateinamen und Funktionsnamen geschrieben, keine Werte."""
from __future__ import annotations

import faulthandler
import logging
from datetime import datetime
from pathlib import Path

from .. import __version__

NAME = "CLAUDIOS-crash.log"
MAX_BYTES = 500_000
WATCHDOG_SECONDS = 45.0
log = logging.getLogger("claudios")
_STATE: dict = {"file": None, "armed": False, "native": False}


def active() -> bool:
    return _STATE["file"] is not None


def armed() -> bool:
    return bool(_STATE["armed"])


def install(path: Path | str | None = None, *, crash_handler: bool = True) -> bool:
    """Öffnet die Datei und schaltet bei crash_handler die Absturz-Spur ein. Gibt False zurück, wenn das nicht ging."""
    if active():
        return True
    handle = None
    try:
        if path is None:
            from ..paths import logs_dir

            target = logs_dir() / NAME
        else:
            target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        mode = "w" if target.exists() and target.stat().st_size > MAX_BYTES else "a"
        handle = open(target, mode, encoding="utf-8")  # noqa: SIM115 – bleibt bis shutdown() offen
        handle.write(f"\n=== CLAUDIOS {__version__} {datetime.now().isoformat(timespec='seconds')} ===\n")
        handle.flush()
        if crash_handler:
            faulthandler.enable(file=handle, all_threads=True)
    except (OSError, RuntimeError, ValueError) as exc:
        if handle is not None:
            handle.close()
        log.warning("crash log unavailable: %r", exc)
        return False
    _STATE.update(file=handle, armed=False, native=crash_handler)
    return True


def arm(seconds: float = WATCHDOG_SECONDS) -> None:
    """Setzt den Wächter zurück: kommt der nächste Aufruf nicht innerhalb von seconds, werden alle Stapel geschrieben."""
    handle = _STATE["file"]
    if handle is None:
        return
    try:
        faulthandler.dump_traceback_later(seconds, repeat=True, file=handle)
        _STATE["armed"] = True
    except (OSError, RuntimeError, ValueError, OverflowError) as exc:
        log.warning("watchdog unavailable: %r", exc)


def disarm() -> None:
    if _STATE["armed"]:
        try:
            faulthandler.cancel_dump_traceback_later()
        except (OSError, RuntimeError, ValueError):
            pass
    _STATE["armed"] = False


def shutdown() -> None:
    """Schließt die Datei (vor dem Entfernen der Protokolle, sonst sperrt Windows sie)."""
    disarm()
    handle = _STATE["file"]
    if handle is None:
        return
    if _STATE["native"]:
        try:
            faulthandler.disable()
        except (OSError, RuntimeError, ValueError):
            pass
    try:
        handle.close()
    except OSError:
        pass
    _STATE.update(file=None, armed=False, native=False)
