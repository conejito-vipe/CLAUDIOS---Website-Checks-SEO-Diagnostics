"""Lädt jede Prüfungsdatei in diesem Ordner automatisch. Neue Prüfung = neue Datei, keine Änderung hier."""
from __future__ import annotations

import importlib
import pkgutil

_loaded = False


def load_all() -> None:
    global _loaded
    if not _loaded:
        for info in sorted(pkgutil.iter_modules(__path__), key=lambda i: i.name):
            if not info.name.startswith("_"):
                importlib.import_module(f"{__name__}.{info.name}")
        _loaded = True
