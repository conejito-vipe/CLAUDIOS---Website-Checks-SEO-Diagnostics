"""Schutz gegen den Doppelstart: Zwei Programme würden dieselben Werkzeuge gleichzeitig einrichten und sich blockieren."""
from __future__ import annotations

from PySide6.QtCore import QLockFile


def acquire(path) -> QLockFile | None:
    """Die Sperre oder None, wenn schon eine andere Instanz läuft. Eine tote Instanz hinterlässt keine Sperre."""
    lock = QLockFile(str(path))
    lock.setStaleLockTime(30000)
    return lock if lock.tryLock(0) else None
