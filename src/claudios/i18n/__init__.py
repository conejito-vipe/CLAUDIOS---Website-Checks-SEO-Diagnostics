"""Lädt jede Datei strings_*.py automatisch (sie ergänzen die UI-Texte). Neue Texte = neue Datei."""
import importlib
import pkgutil

for _info in sorted(pkgutil.iter_modules(__path__), key=lambda i: i.name):
    if _info.name.startswith("strings_"):
        importlib.import_module(f"{__name__}.{_info.name}")
