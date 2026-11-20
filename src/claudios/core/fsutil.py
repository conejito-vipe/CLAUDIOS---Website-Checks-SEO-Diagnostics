"""Windows-Härtung für Dateioperationen (nur das echte Programm ruft harden() auf, app.py).

Unter Windows scheitern Umbenennen und Löschen frisch entpackter Ordner oft mit PermissionError, weil Virenscanner oder
der Explorer Dateien kurz offen halten (im Protokoll als CLA-FS-001). harden() ersetzt shutil.move (nur Ordner),
shutil.rmtree und tempfile.TemporaryDirectory durch Fassungen, die ein paar Sekunden wiederholen. Bleibt das Umbenennen
verweigert, wird der Ordner kopiert. TemporaryDirectory ignoriert Aufräumfehler im Cache. Ungeprüft unter Windows."""
from __future__ import annotations

import os
import shutil
import tempfile
import time

DELAYS = (0.4, 0.8, 1.6, 3.0, 5.0)  # Pausen in Sekunden zwischen den Versuchen
_saved: dict[str, object] = {}


def retry_permission(call, delays=None):
    """Ruft call() auf und wiederholt es nur bei PermissionError; nach dem letzten Versuch wird der Fehler weitergegeben."""
    pauses = DELAYS if delays is None else delays
    last = None
    for pause in (0.0, *pauses):
        if pause:
            time.sleep(pause)
        try:
            return call()
        except PermissionError as exc:
            last = exc
    raise last


def harden() -> bool:
    """Schaltet die Wiederholungen ein. False, wenn sie schon aktiv sind."""
    if _saved:
        return False
    orig_move, orig_rmtree, orig_temp = shutil.move, shutil.rmtree, tempfile.TemporaryDirectory
    _saved.update(move=orig_move, rmtree=orig_rmtree, temp=orig_temp)

    def rmtree(path, *args, **kwargs):
        return retry_permission(lambda: orig_rmtree(path, *args, **kwargs))

    def move(src, dst, copy_function=shutil.copy2):
        src_s, dst_s = os.fspath(src), os.fspath(dst)
        if not os.path.isdir(src_s) or os.path.lexists(dst_s):
            return orig_move(src, dst, copy_function)
        try:
            retry_permission(lambda: os.rename(src_s, dst_s))
            return dst
        except PermissionError:
            pass
        except OSError:
            return orig_move(src, dst, copy_function)
        try:  # letzter Ausweg: kopieren (Lesen ist meist erlaubt, Umbenennen nicht)
            shutil.copytree(src_s, dst_s, symlinks=True)
        except OSError:
            orig_rmtree(dst_s, ignore_errors=True)
            raise
        orig_rmtree(src_s, ignore_errors=True)
        return dst

    class HardenedTemp(orig_temp):
        def __init__(self, *args, **kwargs) -> None:
            if len(args) < 4:
                kwargs.setdefault("ignore_cleanup_errors", True)
            super().__init__(*args, **kwargs)

    shutil.move, shutil.rmtree, tempfile.TemporaryDirectory = move, rmtree, HardenedTemp
    return True


def restore() -> None:
    if not _saved:
        return
    shutil.move, shutil.rmtree, tempfile.TemporaryDirectory = _saved["move"], _saved["rmtree"], _saved["temp"]
    _saved.clear()
